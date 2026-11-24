"""Searches run in the background: they outlive the request, are listed while running and
can be followed again later. The pipeline is always a fake; nothing external is called."""

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

import pipeline
import search_runs
import server
from schemas import ErrorEvent, ResultEvent, SearchRequest, SearchResults, StatusEvent
from userdata import history

REQUEST = SearchRequest(background="Analyst", location="NYC", looking_for="Data roles")
RESULTS = SearchResults(summary="ok", companies=[])


def wait_for(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


def gated_pipeline(monkeypatch: pytest.MonkeyPatch, outcome=None):
    """A pipeline that reports progress, then waits for `release` before finishing."""
    release = threading.Event()
    reported = threading.Event()

    def fake_run_search(request):
        yield StatusEvent(message="Finding jobs")
        reported.set()
        assert release.wait(5), "test never released the pipeline"
        yield outcome or ResultEvent(data=RESULTS)

    monkeypatch.setattr(pipeline, "run_search", fake_run_search)
    return release, reported


def test_search_keeps_running_without_any_client(monkeypatch: pytest.MonkeyPatch) -> None:
    release, reported = gated_pipeline(monkeypatch)
    search_runs.start("TEST_USER", REQUEST, "a" * 32)  # Nobody is listening to it.
    assert reported.wait(5)

    wait_for(lambda: history.get_search("TEST_USER", "a" * 32).messages == ["Finding jobs"])
    [entry] = history.list_searches("TEST_USER")
    assert (entry.id, entry.status) == ("a" * 32, "running")

    release.set()
    wait_for(lambda: history.get_search("TEST_USER", "a" * 32).status == "done")
    assert history.get_search("TEST_USER", "a" * 32).results == RESULTS


def test_attach_follows_a_running_search_then_replays_it_when_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release, reported = gated_pipeline(monkeypatch)
    search_runs.start("TEST_USER", REQUEST, "b" * 32)
    reported.wait(5)
    stream = search_runs.attach("TEST_USER", "b" * 32)
    assert stream is not None
    release.set()
    live = [event for event in stream if event is not None]
    assert [event.type for event in live] == ["started", "status", "result", "saved"]

    wait_for(lambda: history.get_search("TEST_USER", "b" * 32).status == "done")
    replayed = list(search_runs.attach("TEST_USER", "b" * 32) or [])
    assert [event.type for event in replayed] == ["started", "status", "result", "saved"]
    assert replayed[2] == live[2]  # The same results.


def test_unknown_search_cannot_be_attached() -> None:
    assert search_runs.attach("TEST_USER", "c" * 32) is None
    assert search_runs.attach("TEST_USER", "../etc") is None


def test_failed_search_is_replayed_as_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    release, _ = gated_pipeline(monkeypatch, outcome=ErrorEvent(message="No jobs found."))
    search_runs.start("TEST_USER", REQUEST, "d" * 32)
    release.set()
    wait_for(lambda: history.get_search("TEST_USER", "d" * 32).status == "error")
    events = list(search_runs.attach("TEST_USER", "d" * 32) or [])
    assert [event.type for event in events] == ["started", "status", "error"]
    assert events[-1].message == "No jobs found."


def test_endpoints_show_a_running_search_and_its_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(server.app)
    release, reported = gated_pipeline(monkeypatch)
    search_runs.start("TEST_USER", REQUEST, "e" * 32)
    reported.wait(5)
    wait_for(lambda: history.get_search("TEST_USER", "e" * 32).messages)

    [entry] = client.get("/api/searches").json()
    assert (entry["id"], entry["status"], entry["title"]) == (
        "e" * 32,
        "running",
        "Data roles · NYC",
    )
    record = client.get(f"/api/searches/{'e' * 32}").json()
    assert (record["status"], record["messages"]) == ("running", ["Finding jobs"])
    # A running search has no entities yet, and no people can be searched in it.
    assert client.get("/api/entities/companies").json() == []

    release.set()
    wait_for(lambda: history.get_search("TEST_USER", "e" * 32).status == "done")
    with client.stream("GET", f"/api/searches/{'e' * 32}/events") as response:
        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]
    assert [event["type"] for event in events] == ["started", "status", "result", "saved"]
    assert client.get("/api/searches").json()[0]["status"] == "done"


def test_events_of_an_unknown_search_is_404() -> None:
    assert TestClient(server.app).get(f"/api/searches/{'0' * 32}/events").status_code == 404


def test_stale_running_searches_are_marked_interrupted_on_startup() -> None:
    history.start_search("TEST_USER", REQUEST, "f" * 32)  # Left behind by a "crash".
    done = history.start_search("OTHER_USER", REQUEST, "1" * 32)
    history.finish_search("OTHER_USER", done.id, RESULTS, None)

    with TestClient(server.app):  # Startup runs the lifespan.
        pass

    stale = history.get_search("TEST_USER", "f" * 32)
    assert stale.status == "error"
    assert stale.error == history.INTERRUPTED_MESSAGE
    assert history.get_search("OTHER_USER", done.id).status == "done"
    events = list(search_runs.attach("TEST_USER", "f" * 32) or [])
    assert events[-1].type == "error"
