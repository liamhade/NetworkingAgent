"""Accounts: owner-approved access requests, sign-in, session cookies (fake Supabase)."""

import json

import pytest
from fastapi.testclient import TestClient

import config
import server
from auth import access, session, supabase
from auth.supabase import AuthError, Session, SupabaseUser

OWNER = "owner@example.com"
PASSWORD = "hunter2hunter2"


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
        access_token, refresh = f"access-{self.n}", f"refresh-{self.n}"
        self.access[access_token] = user
        self.refresh_tokens[refresh] = user
        return Session(access_token, refresh, 3600, user)

    def admin_create_user(self, email: str, password: str) -> SupabaseUser:
        if self.fail_create:
            raise AuthError(502, "Sign-in is unavailable right now.")
        if email in self.passwords:
            raise AuthError(409, "An account with this email already exists.")
        user_id = f"user-{len(self.passwords) + 1}"
        self.passwords[email] = (user_id, password)
        return SupabaseUser(user_id, email)

    def password_login(self, email: str, password: str) -> Session:
        found = self.passwords.get(email.lower())
        if found is None or found[1] != password:
            raise AuthError(401, "Wrong email or password.")
        return self._session(SupabaseUser(found[0], email.lower()))

    def get_user(self, token: str) -> SupabaseUser | None:
        return self.access.get(token)

    def refresh(self, token: str) -> Session:
        user = self.refresh_tokens.pop(token, None)
        if user is None:
            raise AuthError(401, "Your session has ended.")
        return self._session(user)

    def logout(self, token: str) -> None:
        self.access.pop(token, None)

    def admin_set_password(self, user_id: str, password: str) -> None:
        for email, (uid, _) in self.passwords.items():
            if uid == user_id:
                self.passwords[email] = (uid, password)
                return
        raise AuthError(404, "There is no account with this email.")

    def admin_find_user(self, email: str) -> SupabaseUser | None:
        found = self.passwords.get(email.strip().lower())
        return SupabaseUser(found[0], email.strip().lower()) if found else None


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    monkeypatch.setattr(config, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "anon")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "service")
    monkeypatch.setattr(config, "ACCESS_REQUEST_EMAIL", OWNER)
    f = FakeSupabase()
    for name in (
        "admin_create_user",
        "password_login",
        "get_user",
        "refresh",
        "logout",
        "admin_set_password",
        "admin_find_user",
    ):
        monkeypatch.setattr(supabase, name, getattr(f, name))
    session._verified.clear()
    return f


def _client() -> TestClient:
    return TestClient(server.app)


def _request(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/api/auth/signup", json={"email": email, "password": password})


def _login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _signed_in(email: str) -> TestClient:
    """A client signed in as `email`, approved in advance."""
    access.approve(email)
    client = _client()
    assert _request(client, email).status_code == 200
    return client


def test_without_supabase_everyone_is_test_user() -> None:
    client = _client()
    assert client.get("/api/auth/config").json() == {
        "enabled": False,
        "request_email": "",
        "local_dev": False,
    }
    assert client.get("/api/me").json()["id"] == "TEST_USER"


def test_signed_out_requests_get_401_but_health_works(fake: FakeSupabase) -> None:
    client = _client()
    assert client.get("/api/auth/config").json() == {
        "enabled": True,
        "request_email": OWNER,
        "local_dev": False,
    }
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/searches").status_code == 401
    assert client.get("/api/health").status_code == 200


def test_request_waits_for_approval_then_signs_in(fake: FakeSupabase) -> None:
    client = _client()
    response = _request(client, "Alice@X.com")
    assert response.status_code == 202
    assert response.json() == {"access": "pending"}
    assert "na_access" not in response.cookies  # no session before approval
    assert [(e.email, e.status, e.user_id) for e in access.list_all()] == [
        ("alice@x.com", "pending", "user-1")
    ]

    refused = _login(client, "alice@x.com")
    assert refused.status_code == 403
    assert refused.json()["access"] == "pending"
    assert not fake.access  # the session Supabase issued was revoked
    assert client.get("/api/me").status_code == 401

    access.approve("ALICE@x.com")
    assert _login(client, "alice@x.com").status_code == 200
    assert client.get("/api/me").json()["id"] == "user-1"


def test_pre_approved_email_signs_straight_in(fake: FakeSupabase) -> None:
    access.approve("bob@x.com")
    client = _client()
    response = _request(client, "bob@x.com")
    assert response.status_code == 200
    assert response.json()["display_name"] == "bob@x.com"
    assert {"na_access", "na_refresh"} <= set(response.cookies.keys())
    assert "httponly" in response.headers["set-cookie"].lower()


def test_deny_blocks_requests_and_live_sessions(fake: FakeSupabase) -> None:
    access.deny("spam@x.com")
    denied = _request(_client(), "spam@x.com")
    assert (denied.status_code, denied.json()["access"]) == (403, "denied")
    assert "spam@x.com" not in fake.passwords  # no account made

    client = _signed_in("carol@x.com")
    assert client.get("/api/me").status_code == 200
    access.deny("carol@x.com")
    assert client.get("/api/me").status_code == 401  # at once, despite the token cache
    assert _login(_client(), "carol@x.com").json()["access"] == "denied"


def test_supabase_token_alone_is_not_enough(fake: FakeSupabase) -> None:
    """An account made straight at Supabase (anon key) can't use the app unapproved."""
    fake.admin_create_user("sneaky@x.com", PASSWORD)
    token = fake.password_login("sneaky@x.com", PASSWORD).access_token
    client = _client()
    client.cookies.set(session.ACCESS_COOKIE, token)
    assert client.get("/api/me").status_code == 401

    assert _login(_client(), "sneaky@x.com").status_code == 403
    assert access.get("sneaky@x.com").status == "pending"  # now shows up for the owner


def test_invite_code_accounts_stay_approved(fake: FakeSupabase) -> None:
    fake.admin_create_user("old@x.com", PASSWORD)  # user-1, from the invite-code days
    db = config.DATABASE_DIR
    db.mkdir(parents=True, exist_ok=True)
    invites = {"ABCD-EFGH": {"code": "ABCD-EFGH", "used_by": ["user-1"]}}
    (db / "invite_codes.json").write_text(json.dumps(invites), encoding="utf-8")

    client = _client()
    assert _login(client, "old@x.com").status_code == 200
    assert access.get("old@x.com").status == "approved"


def test_failed_creation_records_nothing_and_duplicates_are_409(fake: FakeSupabase) -> None:
    fake.fail_create = True
    assert _request(_client(), "a@x.com").status_code == 502
    assert access.list_all() == []
    fake.fail_create = False
    assert _request(_client(), "a@x.com").status_code == 202
    assert _request(_client(), "a@x.com").status_code == 409


def test_short_password_is_rejected(fake: FakeSupabase) -> None:
    assert _request(_client(), "a@x.com", password="short").status_code == 422


def test_login_wrong_password_and_users_are_separate(fake: FakeSupabase) -> None:
    alice, bob = _signed_in("alice@x.com"), _signed_in("bob@x.com")

    params = {"background": "Alice's background", "location": "", "looking_for": "SWE"}
    assert alice.put("/api/search/params", json=params).status_code in (200, 204)
    assert bob.get("/api/search/params").json() is None  # can't see Alice's data

    stranger = _client()
    assert _login(stranger, "alice@x.com", "wrong-password").status_code == 401
    assert _login(stranger, "alice@x.com").status_code == 200
    assert stranger.get("/api/search/params").json()["background"] == "Alice's background"


def test_expired_access_token_is_refreshed_from_the_cookie(fake: FakeSupabase) -> None:
    client = _signed_in("a@x.com")
    old_access = client.cookies["na_access"]
    fake.access.clear()  # the access token expired
    session._verified.clear()

    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json()["id"] == "user-1"
    assert client.cookies["na_access"] != old_access  # new cookies came back


def test_dead_refresh_token_signs_out_and_clears_cookies(fake: FakeSupabase) -> None:
    client = _signed_in("a@x.com")
    fake.access.clear()
    fake.refresh_tokens.clear()
    session._verified.clear()

    response = client.get("/api/me")
    assert response.status_code == 401
    assert 'na_refresh=""' in response.headers.get("set-cookie", "")


def test_logout_clears_the_session(fake: FakeSupabase) -> None:
    client = _signed_in("a@x.com")
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/me").status_code == 401


def test_access_cli(capsys: pytest.CaptureFixture[str]) -> None:
    assert access.main(["list"]) == 0
    assert "No access requests" in capsys.readouterr().out

    access.request("pending@x.com", "user-9")
    assert access.main(["approve", "New@X.com"]) == 0
    assert "new@x.com: approved (no account yet" in capsys.readouterr().out
    assert access.main(["deny", "pending@x.com"]) == 0
    assert capsys.readouterr().out.strip() == "pending@x.com: denied"
    assert access.main(["approve", "not-an-email"]) == 1

    access.request("waiting@x.com", "user-10")
    assert access.main(["list"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[:2] for line in lines] == [
        ["pending", "waiting@x.com"],
        ["approved", "new@x.com"],
        ["denied", "pending@x.com"],
    ]


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
