import json

import pytest
from fastapi.testclient import TestClient
from pdf_utils import make_pdf

import pipeline
import resume
import server
from boards import default_config
from schemas import (
    CompanyResult,
    JobResult,
    PersonResult,
    ResultEvent,
    ResumeProfile,
    SearchRequest,
    SearchResults,
    StatusEvent,
    TraceEvent,
    TraceStep,
)
from userdata import history

client = TestClient(server.app)


def default_boards() -> dict:
    return {k: v.model_dump() for k, v in default_config().items()}


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

    monkeypatch.setattr(pipeline, "run_search", fake_run_search)
    body = {"background": "Analyst", "location": "NYC", "looking_for": "Data roles"}
    with client.stream("POST", "/api/search", json=body) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]
    assert events[0]["type"] == "started"
    assert events[0]["search"]["status"] == "running"
    assert events[1:3] == [
        {"type": "status", "message": "Working"},
        {"type": "result", "data": {"summary": "ok", "companies": []}},
    ]
    assert len(events) == 4
    saved = events[3]
    assert saved["type"] == "saved"
    assert saved["search"]["title"] == "Data roles · NYC"

    listed = client.get("/api/searches").json()
    assert [entry["id"] for entry in listed] == [saved["search"]["id"]]

    record = client.get(f"/api/searches/{saved['search']['id']}").json()
    assert record["user_id"] == "TEST_USER"
    # The boards config the search ran with is saved too (here: the defaults).
    assert record["request"] == {**body, "boards": default_boards()}
    assert record["results"] == {"summary": "ok", "companies": []}


def test_failed_search_is_kept_with_its_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_run_search(request):
        yield StatusEvent(message="Working")
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "run_search", failing_run_search)
    body = {"background": "Analyst", "location": "", "looking_for": "Data roles"}
    with client.stream("POST", "/api/search", json=body) as response:
        types = [
            json.loads(line.removeprefix("data: "))["type"]
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]
    assert types == ["started", "status", "error"]
    [entry] = client.get("/api/searches").json()
    assert entry["status"] == "error"
    record = client.get(f"/api/searches/{entry['id']}").json()
    assert record["error"] == "Search failed: boom"
    assert record["messages"] == ["Working"]
    # A failed search has no entities.
    assert client.get("/api/entities/companies").json() == []


def test_get_search_unknown_or_malformed_id_is_404() -> None:
    assert client.get(f"/api/searches/{'0' * 32}").status_code == 404
    assert client.get("/api/searches/..%2F..%2Fsecrets").status_code == 404


def test_search_validates_input() -> None:
    response = client.post("/api/search", json={"background": "", "looking_for": "x"})
    assert response.status_code == 422


def _company(job_url: str, person_url: str) -> CompanyResult:
    return CompanyResult(
        name="Acme",
        url="https://acme.com",
        description="d",
        alignment="a",
        jobs=[JobResult(title="Data Analyst", url=job_url, location="", salary="", alignment="a")],
        people=[PersonResult(name="Jane Doe", title="", profile_url=person_url, alignment="a")],
    )


def _run(monkeypatch: pytest.MonkeyPatch, results: SearchResults) -> list[dict]:
    monkeypatch.setattr(pipeline, "run_search", lambda request: iter([ResultEvent(data=results)]))
    body = {"background": "Analyst", "location": "", "looking_for": "Data roles"}
    with client.stream("POST", "/api/search", json=body) as response:
        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]
    return [event for event in events if event["type"] != "started"]  # Tested on its own.


def test_applied_job_stays_applied_in_a_new_search(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _run(
        monkeypatch,
        SearchResults(
            summary="1",
            companies=[
                _company(
                    "https://www.linkedin.com/jobs/view/data-analyst-at-acme-123?trk=a",
                    "https://www.linkedin.com/in/jane-doe?trk=a",
                )
            ],
        ),
    )
    company = first[0]["data"]["companies"][0]
    job_key, person_key = company["jobs"][0]["key"], company["people"][0]["key"]
    assert job_key == "job:url:linkedin.com/jobs/view/123"
    assert person_key == "person:linkedin:jane-doe"
    assert client.get("/api/statuses").json() == {"job": {}, "person": {}}

    response = client.put("/api/statuses", json={"kind": "job", "key": job_key, "active": True})
    assert response.status_code == 200
    assert response.json()["active"] is True
    client.put("/api/statuses", json={"kind": "person", "key": person_key, "active": True})

    # A later search returns the same job and person with different tracking junk.
    second = _run(
        monkeypatch,
        SearchResults(
            summary="2",
            companies=[
                _company(
                    "https://uk.linkedin.com/jobs/view/123/?refId=b",
                    "https://linkedin.com/in/Jane-Doe/",
                )
            ],
        ),
    )
    company = second[0]["data"]["companies"][0]
    current = client.get("/api/statuses").json()
    assert current["job"][company["jobs"][0]["key"]] is True
    assert current["person"][company["people"][0]["key"]] is True

    # Reopened saved searches carry the same keys.
    saved = client.get(f"/api/searches/{first[1]['search']['id']}").json()
    assert saved["results"]["companies"][0]["jobs"][0]["key"] == job_key

    client.put("/api/statuses", json={"kind": "job", "key": job_key, "active": False})
    assert client.get("/api/statuses").json()["job"][job_key] is False


def test_saved_search_without_keys_is_rekeyed_on_read() -> None:
    record = history.save_search(
        "TEST_USER",
        SearchRequest(background="a", looking_for="b"),
        SearchResults(summary="s", companies=[_company("https://acme.com/j/1", "")]),
    )
    body = client.get(f"/api/searches/{record.id}").json()
    assert body["results"]["companies"][0]["jobs"][0]["key"] == "job:url:acme.com/j/1"
    assert body["results"]["companies"][0]["people"][0]["key"] == "person:name:jane doe|acme"


def test_set_status_validates_input() -> None:
    bad_kind = client.put("/api/statuses", json={"kind": "company", "key": "x", "active": True})
    assert bad_kind.status_code == 422
    wrong_prefix = client.put(
        "/api/statuses", json={"kind": "job", "key": "person:x", "active": True}
    )
    assert wrong_prefix.status_code == 422
    empty = client.put("/api/statuses", json={"kind": "job", "key": "", "active": True})
    assert empty.status_code == 422


def test_pins_follow_entities_across_searches(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _run(
        monkeypatch,
        SearchResults(
            summary="1",
            companies=[
                _company(
                    "https://www.linkedin.com/jobs/view/data-analyst-at-acme-123?trk=a",
                    "https://www.linkedin.com/in/jane-doe?trk=a",
                )
            ],
        ),
    )
    company = first[0]["data"]["companies"][0]
    company_key = company["key"]
    job_key, person_key = company["jobs"][0]["key"], company["people"][0]["key"]
    assert company_key == "company:name:acme"
    assert client.get("/api/pins").json() == {"company": {}, "job": {}, "person": {}}

    for kind, key in [("company", company_key), ("job", job_key), ("person", person_key)]:
        response = client.put("/api/pins", json={"kind": kind, "key": key, "pinned": True})
        assert response.status_code == 200
        assert response.json()["pinned"] is True

    # A later search returns the same entities; their keys still match the pins.
    second = _run(
        monkeypatch,
        SearchResults(
            summary="2",
            companies=[
                _company(
                    "https://uk.linkedin.com/jobs/view/123/?refId=b",
                    "https://linkedin.com/in/Jane-Doe/",
                )
            ],
        ),
    )
    company = second[0]["data"]["companies"][0]
    current = client.get("/api/pins").json()
    assert current["company"][company["key"]] is True
    assert current["job"][company["jobs"][0]["key"]] is True
    assert current["person"][company["people"][0]["key"]] is True

    # Entity lists and reopened searches carry the same keys.
    assert client.get("/api/entities/companies").json()[0]["key"] == company_key
    saved = client.get(f"/api/searches/{first[1]['search']['id']}").json()
    assert saved["results"]["companies"][0]["key"] == company_key

    client.put("/api/pins", json={"kind": "company", "key": company_key, "pinned": False})
    assert client.get("/api/pins").json()["company"][company_key] is False
    # Pins don't touch APPLIED / CONNECTED.
    assert client.get("/api/statuses").json() == {"job": {}, "person": {}}


def test_set_pin_validates_input() -> None:
    bad_kind = client.put("/api/pins", json={"kind": "search", "key": "x", "pinned": True})
    assert bad_kind.status_code == 422
    wrong_prefix = client.put("/api/pins", json={"kind": "company", "key": "job:x", "pinned": True})
    assert wrong_prefix.status_code == 422
    empty = client.put("/api/pins", json={"kind": "job", "key": "", "pinned": True})
    assert empty.status_code == 422
    missing = client.put("/api/pins", json={"kind": "job", "key": "job:x"})
    assert missing.status_code == 422


def test_trace_is_saved_with_the_search_but_not_streamed(monkeypatch: pytest.MonkeyPatch) -> None:
    results = SearchResults(summary="ok", companies=[])
    trace = [
        TraceStep(step="find_people", source="linkedin_people", args={"company": "Ramp"}, count=0)
    ]

    def fake_run_search(request):
        yield TraceEvent(steps=trace)
        yield ResultEvent(data=results)

    monkeypatch.setattr(pipeline, "run_search", fake_run_search)
    body = {"background": "Analyst", "location": "", "looking_for": "Data roles"}
    with client.stream("POST", "/api/search", json=body) as response:
        types = [
            json.loads(line.removeprefix("data: "))["type"]
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]
    assert types == ["started", "result", "saved"]
    [saved] = history.load_searches("TEST_USER")
    assert saved.trace == trace


def test_old_saved_searches_without_new_fields_still_load(isolated_database) -> None:
    folder = isolated_database / "users" / "TEST_USER" / "searches"
    folder.mkdir(parents=True)
    old = {
        "id": "a" * 32,
        "title": "Old",
        "created_at": "2026-11-01T10:00:00Z",
        "user_id": "TEST_USER",
        "request": {"background": "b", "location": "", "looking_for": "l"},
        "results": {
            "summary": "s",
            "companies": [
                {
                    "name": "Acme",
                    "url": "u",
                    "description": "d",
                    "alignment": "a",
                    "jobs": [
                        {
                            "title": "t",
                            "url": "https://acme.com/j",
                            "location": "",
                            "salary": "",
                            "alignment": "a",
                        }
                    ],
                    "people": [],
                }
            ],
        },
    }
    (folder / f"{'a' * 32}.json").write_text(json.dumps(old), encoding="utf-8")
    record = client.get(f"/api/searches/{'a' * 32}").json()
    assert record["trace"] is None
    company = record["results"]["companies"][0]
    assert (company["score"], company["people_searched"]) == (None, False)
    assert company["jobs"][0]["score"] is None
