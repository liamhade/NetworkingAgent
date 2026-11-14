"""Deleting a saved search. Pipelines are fakes; nothing touches the network."""

import pytest
from fastapi.testclient import TestClient
from test_background_search import REQUEST, RESULTS, gated_pipeline, wait_for

import search_runs
import server
from schemas import CompanyResult, SearchResults
from search_runs import runner
from userdata import history, pins

client = TestClient(server.app)


def _done(search_id: str, user: str = "TEST_USER", company: str = "Acme"):
    results = SearchResults(
        summary="s",
        companies=[
            CompanyResult(
                name=company,
                url="https://acme.test",
                description="",
                alignment="",
                jobs=[],
                people=[],
            )
        ],
    )
    return history.save_search(user, REQUEST, results, search_id=search_id)


def test_deleting_removes_the_search_and_its_entities_but_keeps_pins() -> None:
    _done("a" * 32)
    key = client.get("/api/entities/companies").json()[0]["key"]
    pin = {"kind": "company", "key": key, "pinned": True}
    assert client.put("/api/pins", json=pin).status_code == 200

    assert client.delete(f"/api/searches/{'a' * 32}").status_code == 204
    assert client.get("/api/searches").json() == []
    assert client.get(f"/api/searches/{'a' * 32}").status_code == 404
    assert client.get("/api/entities/companies").json() == []
    assert pins.get_pins("TEST_USER")["company"] == {key: True}


def test_entities_in_another_search_survive() -> None:
    _done("a" * 32)
    _done("b" * 32)
    assert client.delete(f"/api/searches/{'a' * 32}").status_code == 204
    assert [c["name"] for c in client.get("/api/entities/companies").json()] == ["Acme"]


def test_deletes_failed_and_cancelled_searches() -> None:
    history.start_search("TEST_USER", REQUEST, "c" * 32)
    history.fail_search("TEST_USER", "c" * 32, "boom")
    history.start_search("TEST_USER", REQUEST, "d" * 32)
    history.cancel_search("TEST_USER", "d" * 32)
    for search_id in ("c" * 32, "d" * 32):
        assert client.delete(f"/api/searches/{search_id}").status_code == 204
    assert client.get("/api/searches").json() == []


def test_unknown_malformed_and_repeat_deletes_are_404() -> None:
    _done("a" * 32)
    assert client.delete(f"/api/searches/{'9' * 32}").status_code == 404
    assert client.delete("/api/searches/not-an-id").status_code == 404
    assert client.delete(f"/api/searches/{'a' * 32}").status_code == 204
    assert client.delete(f"/api/searches/{'a' * 32}").status_code == 404


def test_cannot_delete_another_users_search() -> None:
    _done("a" * 32, user="OTHER_USER")
    assert client.delete(f"/api/searches/{'a' * 32}").status_code == 404
    assert history.get_search("OTHER_USER", "a" * 32) is not None


def test_running_search_is_409_until_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    release, reported = gated_pipeline(monkeypatch)
    search_runs.start("TEST_USER", REQUEST, "e" * 32)
    assert reported.wait(5)
    response = client.delete(f"/api/searches/{'e' * 32}")
    assert response.status_code == 409
    assert "Cancel" in response.json()["detail"]
    assert history.get_search("TEST_USER", "e" * 32) is not None

    assert client.post(f"/api/searches/{'e' * 32}/cancel").status_code == 200
    assert client.delete(f"/api/searches/{'e' * 32}").status_code == 204

    release.set()  # The cancelled worker winds down and must not bring the record back.
    wait_for(lambda: not runner._runs)
    assert history.get_search("TEST_USER", "e" * 32) is None
    assert client.get("/api/searches").json() == []


def test_late_writes_do_not_resurrect_a_deleted_search() -> None:
    _done("a" * 32)
    history.delete_search("TEST_USER", "a" * 32)
    assert history.add_message("TEST_USER", "a" * 32, "late") is None
    assert history.finish_search("TEST_USER", "a" * 32, RESULTS, None) is None
    assert history.load_searches("TEST_USER") == []
