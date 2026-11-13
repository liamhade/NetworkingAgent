"""On-demand people search: `POST /api/searches/{id}/people` (`pipeline.on_demand`).

Mocked LinkedIn search and LLM only; no network.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pipeline_fakes import REQUEST, FakeSources, compiled, notes_for

import config
import server
from entities import catalog, keys
from pipeline import on_demand
from pipeline.state import PeopleNotes
from schemas import SearchResults
from userdata import history

client = TestClient(server.app)


class NotesModel:
    """Stands in for the LLM: writes notes for whoever it is shown, records purposes."""

    def __init__(self, sources: FakeSources, fail: bool = False) -> None:
        self.sources = sources
        self.fail = fail
        self.purposes: list[str] = []

    def with_structured_output(self, schema, method: str):
        assert schema is PeopleNotes and method == "json_schema"
        return self

    def invoke(self, messages, config):
        self.purposes.append(config["metadata"]["llm_purpose"])
        if self.fail:
            raise RuntimeError("provider down")
        text = messages[1].content
        # Every profile URL the fakes can return that appears in the research data.
        people = [
            p
            for (company, keywords) in self.sources.asked
            for p in self.sources.found(company, keywords)
            if p["url"] in text
        ]
        return notes_for(people)


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> FakeSources:
    monkeypatch.setattr(config, "PEOPLE_PER_COMPANY", 2)
    fake = FakeSources(monkeypatch, default_people=2)
    fake.asked = []  # type: ignore[attr-defined]
    original = fake.linkedin_people

    def recording(company: str, keywords: str, location: str = "", n: int = 5):
        fake.asked.append((company, keywords))  # type: ignore[attr-defined]
        return original(company, keywords, location, n)

    monkeypatch.setattr("tools.linkedin_people", recording)
    return fake


@pytest.fixture
def model(sources: FakeSources, monkeypatch: pytest.MonkeyPatch) -> NotesModel:
    fake = NotesModel(sources)
    monkeypatch.setattr(on_demand, "get_llm", lambda: fake)
    return fake


@pytest.fixture
def saved() -> str:
    """A saved search: Ramp searched (with people), the others not searched yet."""
    results = compiled({"Ramp": []})
    companies = []
    for i, company in enumerate(results.companies):
        companies.append(
            company.model_copy(
                update={
                    "people_searched": i == 0,
                    "people_keywords": ["data manager"],
                    "score": 90 - 10 * i,
                }
            )
        )
    data = keys.annotate(SearchResults(summary=results.summary, companies=companies))
    return history.save_search("TEST_USER", REQUEST, data).id


def _post(search_id: str, company: str, job_key: str | None = None):
    body = {"company_key": keys.company_key(company), "job_key": job_key}
    return client.post(f"/api/searches/{search_id}/people", json=body)


def _company(search_id: str, name: str):
    record = history.get_search("TEST_USER", search_id)
    return next(c for c in record.results.companies if c.name == name)


def test_finds_people_merges_them_and_marks_the_company_searched(saved, sources, model) -> None:
    response = _post(saved, "Etsy")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Etsy" and body["people_searched"] is True
    assert len(body["people"]) == 2
    assert all(p["key"].startswith("person:linkedin:") for p in body["people"])
    assert all(p["alignment"] and p["connect_message"] for p in body["people"])

    stored = _company(saved, "Etsy")
    assert stored.people_searched and [p.name for p in stored.people] == [
        p["name"] for p in body["people"]
    ]
    assert sources.people_calls == [("Etsy", "data manager", "New York")]
    assert model.purposes == ["find_people_on_demand"]
    # Other companies are untouched.
    assert not _company(saved, "Plaid").people_searched


def test_a_job_title_is_the_first_keyword_set(saved, sources, model) -> None:
    job_key = keys.job_key(_company(saved, "Notion").jobs[0], "Notion")
    sources.people[("Notion", "Data Analyst at Notion")] = []
    assert _post(saved, "Notion", job_key).status_code == 200
    assert [k for _, k, _ in sources.people_calls] == ["Data Analyst at Notion", "data manager"]


def test_trace_is_appended(saved, sources, model) -> None:
    _post(saved, "Etsy")
    trace = history.get_search("TEST_USER", saved).trace
    assert [(s.step, s.source) for s in trace] == [
        ("find_people_on_demand", "linkedin_people"),
        ("find_people_on_demand", "llm"),
    ]
    assert trace[0].args == {"company": "Etsy", "keywords": "data manager", "location": "New York"}


def test_running_twice_does_not_duplicate_people(saved, sources, model) -> None:
    first = _post(saved, "Etsy").json()["people"]
    second = _post(saved, "Etsy").json()["people"]
    # The second run skips the people already saved, climbs the ladder for new ones.
    assert {p["key"] for p in first} < {p["key"] for p in second}
    assert len({p["key"] for p in second}) == len(second)


def test_llm_failure_still_saves_current_employees(saved, sources, model) -> None:
    model.fail = True
    body = _post(saved, "Etsy").json()
    assert [p["alignment"] for p in body["people"]] == ["", ""]
    assert history.get_search("TEST_USER", saved).trace[-1].error == "RuntimeError: provider down"


def test_nobody_found_marks_the_company_searched(saved, sources, model) -> None:
    for keywords in ("data manager", "recruiter", ""):
        sources.people[("Etsy", keywords)] = []
    body = _post(saved, "Etsy").json()
    assert body["people"] == [] and body["people_searched"] is True
    assert model.purposes == []  # no LLM call without people


def test_unknown_search_company_or_job_is_404(saved, sources, model) -> None:
    assert _post("0" * 32, "Etsy").status_code == 404
    assert _post(saved, "Nobody").status_code == 404
    assert _post(saved, "Etsy", "job:url:nowhere.example").status_code == 404


def test_new_people_show_up_on_the_people_page(saved, sources, model) -> None:
    names = {p["name"] for p in _post(saved, "Plaid").json()["people"]}
    people = catalog.people(history.load_searches("TEST_USER"))
    assert names <= {p.name for p in people}


def test_concurrent_requests_do_not_lose_writes(saved, sources, model, monkeypatch) -> None:
    """Slow people searches and a slow read inside the save: without the per-search lock,
    the later write would drop the earlier company's people."""
    real_get = history.get_search
    real_people = sources.linkedin_people
    active = {"now": 0, "max": 0}
    lock = threading.Lock()

    def slow_get(user_id: str, search_id: str):
        record = real_get(user_id, search_id)
        time.sleep(0.05)
        return record

    def slow_people(company: str, keywords: str, location: str = "", n: int = 5):
        with lock:
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
        time.sleep(0.1)
        with lock:
            active["now"] -= 1
        sources.asked.append((company, keywords))
        return real_people(company, keywords, location, n)

    monkeypatch.setattr(history, "get_search", slow_get)
    monkeypatch.setattr("tools.linkedin_people", slow_people)
    targets = ["Notion", "Datadog", "Etsy", "Plaid", "Etsy"]
    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        responses = list(pool.map(lambda name: _post(saved, name), targets))

    assert [r.status_code for r in responses] == [200] * len(targets)
    assert active["max"] > 1  # the requests really overlapped
    record = real_get("TEST_USER", saved)
    for company in record.results.companies:
        if company.name in targets:
            assert company.people_searched and company.people, company.name
            assert len({p.key for p in company.people}) == len(company.people)
    on_demand_steps = [s for s in record.trace if s.source == "llm"]
    assert len(on_demand_steps) == len(targets)


def test_endpoint_runs_in_the_threadpool() -> None:
    route = next(
        r for r in server.app.routes if getattr(r, "path", "") == "/api/searches/{search_id}/people"
    )
    assert not __import__("inspect").iscoroutinefunction(route.endpoint)
