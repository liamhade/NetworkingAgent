"""The owner's Admin tab: whitelist changes and per-user LLM usage (fake Supabase)."""

import pytest
from fastapi.testclient import TestClient
from test_auth import PASSWORD, FakeSupabase, _client, _login, _request, _signed_in
from test_auth import fake as fake  # noqa: F401  (pytest fixture)

import config
import server
from auth import access
from llm_usage import recorder

OWNER_EMAIL = "boss@example.com"


@pytest.fixture
def owner(fake: FakeSupabase, monkeypatch: pytest.MonkeyPatch) -> TestClient:  # noqa: F811
    """A client signed in as the owner, who was never approved by hand."""
    monkeypatch.setattr(config, "OWNER_EMAIL", OWNER_EMAIL)
    client = _client()
    assert _request(client, "Boss@Example.com").status_code == 200  # owner: straight in
    return client


def _usage(user_id: str, cost: float, tokens: int, when: str) -> None:
    recorder.write_row(
        recorder.UsageRow(
            timestamp=when,
            user_id=user_id,
            request_id="r",
            search_id="s",
            purpose="plan",
            provider="anthropic",
            model="claude-haiku-5-5",
            status="ok",
            input_tokens=tokens,
            cache_read_tokens=0,
            cache_write_5m_tokens=0,
            cache_write_1h_tokens=0,
            output_tokens=0,
            total_tokens=tokens,
            cost_usd=cost,
            latency_ms=10,
        )
    )


def test_only_the_owner_is_admin(owner: TestClient) -> None:
    assert owner.get("/api/me").json()["is_admin"] is True
    assert owner.get("/api/admin/users").status_code == 200

    other = _signed_in("alice@x.com")
    assert other.get("/api/me").json()["is_admin"] is False
    assert other.get("/api/admin/users").status_code == 403
    assert other.put("/api/admin/whitelist", json={"email": "eve@x.com"}).status_code == 403
    assert access.get("eve@x.com") is None
    assert _client().get("/api/admin/users").status_code == 401


def test_without_accounts_the_local_user_is_admin() -> None:
    client = TestClient(server.app)
    assert client.get("/api/me").json()["is_admin"] is True
    assert client.get("/api/admin/users").status_code == 200


def test_whitelist_add_lets_a_pending_request_in(owner: TestClient) -> None:
    client = _client()
    assert _request(client, "bob@x.com").status_code == 202
    assert _login(client, "bob@x.com").status_code == 403

    added = owner.put("/api/admin/whitelist", json={"email": " Bob@X.com "})
    assert added.status_code == 200
    assert added.json()["status"] == "approved"
    assert _login(client, "bob@x.com").status_code == 200


def test_whitelist_add_pre_approves_and_rejects_non_emails(owner: TestClient) -> None:
    assert owner.put("/api/admin/whitelist", json={"email": "nope"}).status_code == 422
    assert owner.put("/api/admin/whitelist", json={"email": "new@x.com"}).status_code == 200
    assert _request(_client(), "new@x.com").status_code == 200  # signs straight in


def test_whitelist_remove_blocks_live_sessions(owner: TestClient) -> None:
    alice = _signed_in("alice@x.com")
    assert alice.get("/api/searches").status_code == 200

    removed = owner.delete("/api/admin/whitelist/Alice@x.com")
    assert removed.status_code == 200
    assert removed.json()["status"] == "denied"
    assert alice.get("/api/searches").status_code == 401
    assert _login(_client(), "alice@x.com").status_code == 403


def test_owner_cannot_be_removed_and_is_always_let_in(
    owner: TestClient,
    fake: FakeSupabase,  # noqa: F811
) -> None:
    response = owner.delete(f"/api/admin/whitelist/{OWNER_EMAIL}")
    assert response.status_code == 400
    with pytest.raises(ValueError):
        access.deny(OWNER_EMAIL)
    assert access.status_of("any-id", OWNER_EMAIL) == "approved"
    assert _login(_client(), OWNER_EMAIL, PASSWORD).status_code == 200


def test_users_lists_emails_statuses_and_llm_usage(owner: TestClient) -> None:
    alice = _signed_in("alice@x.com")
    alice_id = alice.get("/api/me").json()["id"]
    _request(_client(), "pending@x.com")
    access.approve("later@x.com")  # pre-approved, never signed up
    _usage(alice_id, 0.25, 1000, "2026-11-20T10:00:00+00:00")
    _usage(alice_id, 0.50, 3000, "2026-11-21T10:00:00+00:00")
    _usage("TEST_USER", 0.01, 10, "2026-11-01T10:00:00+00:00")

    data = owner.get("/api/admin/users").json()
    assert data["owner_email"] == OWNER_EMAIL
    users = {u["email"]: u for u in data["users"]}
    assert data["users"][0]["email"] == OWNER_EMAIL
    assert users[OWNER_EMAIL]["is_owner"] is True
    assert users["alice@x.com"]["status"] == "approved"
    assert users["alice@x.com"]["usage"] == {
        "calls": 2,
        "total_tokens": 4000,
        "cost_usd": 0.75,
        "last_used_at": "2026-11-21T10:00:00+00:00",
    }
    assert users["alice@x.com"]["joined_at"]
    assert users["pending@x.com"]["status"] == "pending"
    assert users["later@x.com"]["usage"]["calls"] == 0
    assert users["TEST_USER"]["status"] is None  # usage with no email: listed by id
    assert data["totals"]["calls"] == 3
    assert data["totals"]["cost_usd"] == pytest.approx(0.76)
