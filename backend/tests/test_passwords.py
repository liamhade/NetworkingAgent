"""Password resets without email: owner reset, self-service change, and the CLI."""

import pytest
from fastapi.testclient import TestClient
from test_admin import OWNER_EMAIL
from test_admin import owner as owner  # noqa: F401  (pytest fixture)
from test_auth import PASSWORD, FakeSupabase, _client, _login, _request, _signed_in
from test_auth import fake as fake  # noqa: F401  (pytest fixture)

import config
from auth import access


def test_owner_resets_a_users_password(owner: TestClient) -> None:  # noqa: F811
    _signed_in("alice@x.com")
    response = owner.post("/api/admin/users/Alice@x.com/reset-password")
    assert response.status_code == 200
    temporary = response.json()["password"]
    assert response.json()["email"] == "alice@x.com"
    assert len(temporary) >= 12
    assert _login(_client(), "alice@x.com").status_code == 401  # old password is gone
    assert _login(_client(), "alice@x.com", temporary).status_code == 200


def test_reset_needs_an_account_and_the_owner(owner: TestClient) -> None:  # noqa: F811
    access.approve("later@x.com")  # pre-approved, never signed up
    assert owner.post("/api/admin/users/later@x.com/reset-password").status_code == 404
    alice = _signed_in("alice@x.com")
    assert alice.post("/api/admin/users/alice@x.com/reset-password").status_code == 403


def test_reset_finds_accounts_missing_from_the_access_list(
    owner: TestClient,  # noqa: F811
    fake: FakeSupabase,  # noqa: F811
) -> None:
    # An account made in the Supabase dashboard: no access-list entry with its id.
    fake.passwords["solo@x.com"] = ("user-solo", PASSWORD)
    assert access.get("solo@x.com") is None
    response = owner.post("/api/admin/users/solo@x.com/reset-password")
    assert response.status_code == 200
    assert fake.passwords["solo@x.com"][1] == response.json()["password"]


def test_user_changes_their_own_password(fake: FakeSupabase) -> None:  # noqa: F811
    alice = _signed_in("alice@x.com")
    wrong = {"current_password": "nope", "new_password": "a-new-password"}
    response = alice.post("/api/account/password", json=wrong)
    assert response.status_code == 400
    assert "current password" in response.json()["detail"]
    short = {"current_password": PASSWORD, "new_password": "short"}
    assert alice.post("/api/account/password", json=short).status_code == 422

    good = {"current_password": PASSWORD, "new_password": "a-new-password"}
    assert alice.post("/api/account/password", json=good).status_code == 204
    assert alice.get("/api/searches").status_code == 200  # still signed in
    assert _login(_client(), "alice@x.com").status_code == 401
    assert _login(_client(), "alice@x.com", "a-new-password").status_code == 200


def test_change_password_needs_a_session(fake: FakeSupabase) -> None:  # noqa: F811
    body = {"current_password": PASSWORD, "new_password": "a-new-password"}
    assert _client().post("/api/account/password", json=body).status_code == 401


def test_without_accounts_there_is_no_password() -> None:
    from server import app

    body = {"current_password": PASSWORD, "new_password": "a-new-password"}
    assert TestClient(app).post("/api/account/password", json=body).status_code == 404


def test_cli_resets_any_password_including_the_owners(
    fake: FakeSupabase,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(config, "OWNER_EMAIL", OWNER_EMAIL)
    assert _request(_client(), OWNER_EMAIL).status_code == 200
    assert access.main(["reset-password", "Boss@Example.com"]) == 0
    temporary = capsys.readouterr().out.split("new temporary password: ")[1].split()[0]
    assert _login(_client(), OWNER_EMAIL, temporary).status_code == 200

    assert access.main(["reset-password", "nobody@x.com"]) == 1
    assert "no account" in capsys.readouterr().err
