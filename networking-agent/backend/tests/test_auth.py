"""Accounts: invite-gated sign-up, password sign-in, session cookies (fake Supabase)."""

import pytest
from fastapi.testclient import TestClient

import config
import server
from auth import invites, session, supabase
from auth.supabase import AuthError, Session, SupabaseUser


class FakeSupabase:
    """Accounts and tokens in memory; patched over the `auth.supabase` calls."""

    def __init__(self) -> None:
        self.passwords: dict[str, tuple[str, str]] = {}  # email -> (user id, password)
        self.access: dict[str, SupabaseUser] = {}
        self.refresh_tokens: dict[str, SupabaseUser] = {}
        self.fail_create = False
        self.n = 0

    def _session(self, user: SupabaseUser) -> Session:
        self.n += 1
        access, refresh = f"access-{self.n}", f"refresh-{self.n}"
        self.access[access] = user
        self.refresh_tokens[refresh] = user
        return Session(access, refresh, 3600, user)

    def admin_create_user(self, email: str, password: str) -> SupabaseUser:
        if self.fail_create:
            raise AuthError(502, "Sign-in is unavailable right now.")
        if email in self.passwords:
            raise AuthError(409, "An account with this email already exists.")
        user_id = f"user-{len(self.passwords) + 1}"
        self.passwords[email] = (user_id, password)
        return SupabaseUser(user_id, email)

    def password_login(self, email: str, password: str) -> Session:
        found = self.passwords.get(email)
        if found is None or found[1] != password:
            raise AuthError(401, "Wrong email or password.")
        return self._session(SupabaseUser(found[0], email))

    def get_user(self, token: str) -> SupabaseUser | None:
        return self.access.get(token)

    def refresh(self, token: str) -> Session:
        user = self.refresh_tokens.pop(token, None)
        if user is None:
            raise AuthError(401, "Your session has ended.")
        return self._session(user)

    def logout(self, token: str) -> None:
        self.access.pop(token, None)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "anon")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "service")
    f = FakeSupabase()
    for name in ("admin_create_user", "password_login", "get_user", "refresh", "logout"):
        monkeypatch.setattr(supabase, name, getattr(f, name))
    session._verified.clear()
    return f


def _client() -> TestClient:
    return TestClient(server.app)


def _signup(client: TestClient, email: str, code: str, password: str = "hunter2hunter2"):
    return client.post(
        "/api/auth/signup", json={"email": email, "password": password, "invite_code": code}
    )


def test_without_supabase_everyone_is_test_user() -> None:
    client = _client()
    assert client.get("/api/auth/config").json() == {"enabled": False}
    assert client.get("/api/me").json()["id"] == "TEST_USER"


def test_signed_out_requests_get_401_but_health_works(fake: FakeSupabase) -> None:
    client = _client()
    assert client.get("/api/auth/config").json() == {"enabled": True}
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/searches").status_code == 401
    assert client.get("/api/health").status_code == 200


def test_signup_needs_a_valid_invite_and_uses_it_up(fake: FakeSupabase) -> None:
    client = _client()
    assert _signup(client, "a@x.com", "NOPE-NOPE").status_code == 400

    code = invites.create(max_uses=1, note="alice").code
    response = _signup(client, "a@x.com", code.lower().replace("-", " "))  # forgiving input
    assert response.status_code == 200
    assert response.json()["display_name"] == "a@x.com"
    assert {"na_access", "na_refresh"} <= set(response.cookies.keys())
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/me").json()["id"] == "user-1"

    (invite,) = invites.list_all()
    assert (invite.uses, invite.used_by) == (1, ["user-1"])
    assert _signup(_client(), "b@x.com", code).status_code == 400  # used up


def test_failed_account_creation_gives_the_invite_back(fake: FakeSupabase) -> None:
    code = invites.create().code
    fake.fail_create = True
    assert _signup(_client(), "a@x.com", code).status_code == 502
    fake.fail_create = False
    assert _signup(_client(), "a@x.com", code).status_code == 200


def test_duplicate_email_is_409_and_keeps_the_code(fake: FakeSupabase) -> None:
    code = invites.create(max_uses=2).code
    assert _signup(_client(), "a@x.com", code).status_code == 200
    assert _signup(_client(), "a@x.com", code).status_code == 409
    assert invites.list_all()[0].uses == 1


def test_login_wrong_password_and_users_are_separate(fake: FakeSupabase) -> None:
    code = invites.create(max_uses=2).code
    alice, bob = _client(), _client()
    _signup(alice, "alice@x.com", code)
    _signup(bob, "bob@x.com", code)

    params = {"background": "Alice's background", "location": "", "looking_for": "SWE"}
    assert alice.put("/api/search/params", json=params).status_code in (200, 204)
    assert bob.get("/api/search/params").json() is None  # can't see Alice's data

    stranger = _client()
    bad = {"email": "alice@x.com", "password": "wrong-password"}
    assert stranger.post("/api/auth/login", json=bad).status_code == 401
    good = {"email": "alice@x.com", "password": "hunter2hunter2"}
    assert stranger.post("/api/auth/login", json=good).status_code == 200
    assert stranger.get("/api/search/params").json()["background"] == "Alice's background"


def test_expired_access_token_is_refreshed_from_the_cookie(fake: FakeSupabase) -> None:
    client = _client()
    _signup(client, "a@x.com", invites.create().code)
    old_access = client.cookies["na_access"]
    fake.access.clear()  # the access token expired
    session._verified.clear()

    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json()["id"] == "user-1"
    assert client.cookies["na_access"] != old_access  # new cookies came back


def test_dead_refresh_token_signs_out_and_clears_cookies(fake: FakeSupabase) -> None:
    client = _client()
    _signup(client, "a@x.com", invites.create().code)
    fake.access.clear()
    fake.refresh_tokens.clear()
    session._verified.clear()

    response = client.get("/api/me")
    assert response.status_code == 401
    assert 'na_refresh=""' in response.headers.get("set-cookie", "")


def test_logout_clears_the_session(fake: FakeSupabase) -> None:
    client = _client()
    _signup(client, "a@x.com", invites.create().code)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/me").status_code == 401


def test_invite_codes_cli_and_revoke(capsys: pytest.CaptureFixture[str]) -> None:
    assert invites.main(["create", "--uses", "3", "--note", "beta"]) == 0
    code = capsys.readouterr().out.strip()
    assert len(code) == 9 and code[4] == "-"
    assert invites.main(["revoke", code]) == 0
    with pytest.raises(invites.InvalidInvite):
        invites.reserve(code)
    assert invites.main(["list"]) == 0
    assert "revoked" in capsys.readouterr().out
    assert invites.main(["revoke", "ZZZZ-ZZZZ"]) == 1


class _Response:
    def __init__(self, status: int, body: dict) -> None:
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self) -> dict:
        return self._body


def test_supabase_error_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    exists = _Response(422, {"code": 422, "error_code": "email_exists", "msg": "already"})
    monkeypatch.setattr(supabase.requests, "post", lambda *a, **k: exists)
    with pytest.raises(AuthError) as err:
        supabase.admin_create_user("a@x.com", "pw")
    assert err.value.status == 409

    bad_login = _Response(400, {"error_code": "invalid_credentials", "msg": "Invalid"})
    monkeypatch.setattr(supabase.requests, "post", lambda *a, **k: bad_login)
    with pytest.raises(AuthError) as err:
        supabase.password_login("a@x.com", "pw")
    assert (err.value.status, err.value.message) == (401, "Wrong email or password.")
