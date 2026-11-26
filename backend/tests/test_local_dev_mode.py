"""LOCAL_DEV_MODE: the sign-in page stays, any credentials sign in as TEST_USER."""

import pytest
from fastapi.testclient import TestClient
from test_auth import FakeSupabase
from test_auth import fake as fake  # noqa: F401  (pytest fixture)

import config
import server


@pytest.fixture
def dev(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(config, "LOCAL_DEV_MODE", True)
    return TestClient(server.app)


def test_config_asks_for_a_sign_in(dev: TestClient) -> None:
    assert dev.get("/api/auth/config").json() == {
        "enabled": True,
        "request_email": "",
        "local_dev": True,
    }
    assert dev.get("/api/me").status_code == 401
    assert dev.get("/api/searches").status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        {"email": "anyone@x.com", "password": "wrong"},
        {"email": "", "password": ""},
        {"email": "not an email"},
        None,
    ],
)
def test_any_credentials_sign_in_as_test_user(dev: TestClient, body: object) -> None:
    response = dev.post("/api/auth/login", json=body)
    assert response.status_code == 200
    assert response.json()["id"] == "TEST_USER"
    me = dev.get("/api/me").json()
    assert me["id"] == "TEST_USER"
    assert me["is_admin"] is True
    assert dev.get("/api/searches").status_code == 200
    assert dev.get("/api/admin/users").status_code == 200


def test_request_access_also_signs_in(dev: TestClient) -> None:
    assert (
        dev.post("/api/auth/signup", json={"email": "a@x.com", "password": "x"}).json()["id"]
        == "TEST_USER"
    )


def test_sign_out_brings_the_sign_in_page_back(dev: TestClient) -> None:
    dev.post("/api/auth/login", json={})
    assert dev.post("/api/auth/logout").status_code == 204
    assert dev.get("/api/me").status_code == 401


def test_no_passwords_in_dev_mode(dev: TestClient) -> None:
    dev.post("/api/auth/login", json={})
    body = {"current_password": "a", "new_password": "longer-password"}
    assert dev.post("/api/account/password", json=body).status_code == 404
    assert dev.post("/api/admin/users/a@x.com/reset-password").status_code == 404


def test_overrides_supabase_without_calling_it(
    dev: TestClient,
    fake: FakeSupabase,  # noqa: F811
) -> None:
    response = dev.post("/api/auth/login", json={"email": "who@x.com", "password": "nope"})
    assert response.status_code == 200
    assert response.json()["id"] == "TEST_USER"
    assert fake.n == 0  # no Supabase session was made
    assert dev.get("/api/me").json()["id"] == "TEST_USER"


def test_refused_through_a_proxy_or_from_another_machine(dev: TestClient) -> None:
    proxied = {"X-Forwarded-For": "203.0.113.9"}
    assert dev.post("/api/auth/login", json={}, headers=proxied).status_code == 403
    remote = TestClient(server.app, client=("203.0.113.9", 5000))
    assert remote.post("/api/auth/login", json={}).status_code == 403
    # A hand-made dev cookie doesn't help from outside either.
    remote.cookies.set("na_dev", "1")
    assert remote.get("/api/me").status_code == 401
    dev.cookies.set("na_dev", "1")
    assert dev.get("/api/me", headers=proxied).status_code == 401


def test_off_means_real_validation(fake: FakeSupabase) -> None:  # noqa: F811
    client = TestClient(server.app)
    assert client.post("/api/auth/login", json={"email": "bad"}).status_code == 422
    assert client.post("/api/auth/login", json={}).status_code == 422
