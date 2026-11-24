"""Cancelling a running search and the cap on searches running at once. Pipelines are fakes."""

import json

import pytest
from fastapi.testclient import TestClient
from test_background_search import REQUEST, RESULTS, gated_pipeline, wait_for

import config
import search_runs
import server
from search_runs import runner
from userdata import history

client = TestClient(server.app)


def events_of(response) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.iter_lines()
        if line.startswith("data: ")
    ]


def test_cancel_saves_a_cancelled_search_and_discards_the_late_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release, reported = gated_pipeline(monkeypatch)
    search_runs.start("TEST_USER", REQUEST, "a" * 32)
    assert reported.wait(5)

    response = client.post(f"/api/searches/{'a' * 32}/cancel")
    assert response.status_code == 200
    assert (response.json()["id"], response.json()["status"]) == ("a" * 32, "cancelled")
    assert history.get_search("TEST_USER", "a" * 32).status == "cancelled"
    assert client.get("/api/searches").json()[0]["status"] == "cancelled"

    release.set()  # The pipeline still produces a result; it must be thrown away.
    wait_for(lambda: not runner._runs)
    record = history.get_search("TEST_USER", "a" * 32)
    assert record.status == "cancelled"
    assert record.results.companies == [] and record.results.summary == ""
    assert client.get("/api/entities/companies").json() == []


def test_cancel_ends_a_followed_stream_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    release, reported = gated_pipeline(monkeypatch)
    search_runs.start("TEST_USER", REQUEST, "b" * 32)
    reported.wait(5)
    stream = search_runs.attach("TEST_USER", "b" * 32)
    assert stream is not None
    search_runs.cancel("TEST_USER", "b" * 32)
    live = [event for event in stream if event is not None]
    assert [event.type for event in live] == ["started", "status", "cancelled"]
    release.set()
    wait_for(lambda: not runner._runs)

    replayed = list(search_runs.attach("TEST_USER", "b" * 32) or [])
    assert [event.type for event in replayed] == ["started", "status", "cancelled"]
    assert replayed[-1].search.status == "cancelled"


def test_cancel_stops_the_pipeline_at_the_next_step(monkeypatch: pytest.MonkeyPatch) -> None:
    release, reported = gated_pipeline(monkeypatch)
    finished_steps: list[str] = []

    import pipeline
    from schemas import StatusEvent

    def steps(request):
        try:
            yield StatusEvent(message="one")
            reported.set()
            assert release.wait(5)
            yield StatusEvent(message="two")
            finished_steps.append("two")  # Must never run once cancelled.
        finally:
            finished_steps.append("closed")

    monkeypatch.setattr(pipeline, "run_search", steps)
    search_runs.start("TEST_USER", REQUEST, "c" * 32)
    reported.wait(5)
    search_runs.cancel("TEST_USER", "c" * 32)
    release.set()
    wait_for(lambda: not runner._runs)
    assert finished_steps == ["closed"]
    assert history.get_search("TEST_USER", "c" * 32).messages == ["one"]


def test_cancel_unknown_search_is_404_and_finished_search_is_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert client.post(f"/api/searches/{'0' * 32}/cancel").status_code == 404
    assert client.post("/api/searches/not-an-id/cancel").status_code == 404

    release, _ = gated_pipeline(monkeypatch)
    release.set()
    search_runs.start("TEST_USER", REQUEST, "d" * 32)
    wait_for(lambda: history.get_search("TEST_USER", "d" * 32).status == "done")
    response = client.post(f"/api/searches/{'d' * 32}/cancel")
    assert response.status_code == 409
    assert "not running" in response.json()["detail"]
    assert history.get_search("TEST_USER", "d" * 32).results == RESULTS

    search_runs_cancelled = history.start_search("TEST_USER", REQUEST, "e" * 32)
    history.cancel_search("TEST_USER", search_runs_cancelled.id)
    assert client.post(f"/api/searches/{'e' * 32}/cancel").status_code == 409


def test_cancelling_twice_is_409(monkeypatch: pytest.MonkeyPatch) -> None:
    release, reported = gated_pipeline(monkeypatch)
    search_runs.start("TEST_USER", REQUEST, "f" * 32)
    reported.wait(5)
    assert client.post(f"/api/searches/{'f' * 32}/cancel").status_code == 200
    assert client.post(f"/api/searches/{'f' * 32}/cancel").status_code == 409
    release.set()
    wait_for(lambda: not runner._runs)


def test_users_cannot_cancel_each_others_searches(monkeypatch: pytest.MonkeyPatch) -> None:
    release, reported = gated_pipeline(monkeypatch)
    search_runs.start("OTHER_USER", REQUEST, "1" * 32)
    reported.wait(5)
    assert client.post(f"/api/searches/{'1' * 32}/cancel").status_code == 404
    release.set()
    wait_for(lambda: not runner._runs)
    assert history.get_search("OTHER_USER", "1" * 32).status == "done"


def test_search_is_refused_with_429_at_the_concurrency_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "MAX_CONCURRENT_SEARCHES", 1)
    release, reported = gated_pipeline(monkeypatch)
    body = REQUEST.model_dump()

    with client.stream("POST", "/api/search", json=body) as first:
        assert first.status_code == 200
        reported.wait(5)
        refused = client.post("/api/search", json=body)
        assert refused.status_code == 429
        assert "limit is 1" in refused.json()["detail"]
        assert len(history.list_searches("TEST_USER")) == 1  # Nothing saved for the refusal.

        # Cancelling frees the slot at once, even while the old pipeline winds down.
        [running] = history.list_searches("TEST_USER")
        assert client.post(f"/api/searches/{running.id}/cancel").status_code == 200
        release.set()
        list(first.iter_lines())

    wait_for(lambda: not runner._runs)
    # A finished search frees its slot too.
    again = client.post("/api/search", json=body)
    assert again.status_code == 200


def test_cap_counts_every_users_searches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "MAX_CONCURRENT_SEARCHES", 2)
    release, reported = gated_pipeline(monkeypatch)
    search_runs.start("TEST_USER", REQUEST, "2" * 32)
    search_runs.start("OTHER_USER", REQUEST, "3" * 32)
    reported.wait(5)
    with pytest.raises(search_runs.TooManySearches):
        search_runs.start("TEST_USER", REQUEST, "4" * 32)
    assert history.get_search("TEST_USER", "4" * 32) is None
    release.set()
    wait_for(lambda: not runner._runs)
