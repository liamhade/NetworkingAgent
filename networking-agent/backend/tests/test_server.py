import json

import pytest
from fastapi.testclient import TestClient
from pdf_utils import make_pdf

import agent
import resume
import server
from schemas import ResultEvent, ResumeProfile, SearchResults, StatusEvent

client = TestClient(server.app)


def test_me_returns_test_user() -> None:
    body = client.get("/api/me").json()
    assert body["id"] == "TEST_USER"
    assert body["display_name"] == "Test User"
    assert "created_at" in body


def test_health() -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_resume_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = ResumeProfile(background="I am an analyst.", location="NYC", looking_for="")
    monkeypatch.setattr(resume, "parse_resume", lambda data: profile)
    response = client.post(
        "/api/resume", files={"file": ("cv.pdf", make_pdf(["Jane"]), "application/pdf")}
    )
    assert response.status_code == 200
    assert response.json() == profile.model_dump()


def test_resume_rejects_non_pdf() -> None:
    response = client.post("/api/resume", files={"file": ("cv.txt", b"hello", "text/plain")})
    assert response.status_code == 415


def test_resume_unreadable_pdf_is_422() -> None:
    response = client.post("/api/resume", files={"file": ("cv.pdf", b"garbage", "application/pdf")})
    assert response.status_code == 422


def test_search_streams_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    results = SearchResults(summary="ok", companies=[])

    def fake_run_search(request):
        assert request.location == "NYC"
        yield StatusEvent(message="Working")
        yield ResultEvent(data=results)

    monkeypatch.setattr(agent, "run_search", fake_run_search)
    body = {"background": "Analyst", "location": "NYC", "looking_for": "Data roles"}
    with client.stream("POST", "/api/search", json=body) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]
    assert events[:2] == [
        {"type": "status", "message": "Working"},
        {"type": "result", "data": {"summary": "ok", "companies": []}},
    ]
    assert len(events) == 3
    saved = events[2]
    assert saved["type"] == "saved"
    assert saved["search"]["title"] == "Data roles · NYC"

    listed = client.get("/api/searches").json()
    assert [entry["id"] for entry in listed] == [saved["search"]["id"]]

    record = client.get(f"/api/searches/{saved['search']['id']}").json()
    assert record["user_id"] == "TEST_USER"
    assert record["request"] == body
    assert record["results"] == {"summary": "ok", "companies": []}


def test_search_error_is_not_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_run_search(request):
        yield StatusEvent(message="Working")
        raise RuntimeError("boom")

    monkeypatch.setattr(agent, "run_search", failing_run_search)
    body = {"background": "Analyst", "location": "", "looking_for": "Data roles"}
    with client.stream("POST", "/api/search", json=body) as response:
        types = [
            json.loads(line.removeprefix("data: "))["type"]
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]
    assert types == ["status", "error"]
    assert client.get("/api/searches").json() == []


def test_get_search_unknown_or_malformed_id_is_404() -> None:
    assert client.get(f"/api/searches/{'0' * 32}").status_code == 404
    assert client.get("/api/searches/..%2F..%2Fsecrets").status_code == 404


def test_search_validates_input() -> None:
    response = client.post("/api/search", json={"background": "", "looking_for": "x"})
    assert response.status_code == 422
