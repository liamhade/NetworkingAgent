import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import agent
import server
from entities import catalog
from schemas import (
    CompanyResult,
    JobResult,
    PersonResult,
    ResultEvent,
    SavedSearch,
    SearchRequest,
    SearchResults,
)
from userdata import history

client = TestClient(server.app)
T0 = datetime(2026, 11, 1, 12, tzinfo=UTC)


def _job(url: str, title: str = "Data Analyst", **extra: str) -> JobResult:
    values = {"location": "", "salary": "", "alignment": "fits"} | extra
    return JobResult(title=title, url=url, **values)


def _person(url: str, name: str = "Jane Doe", **extra: str) -> PersonResult:
    values = {"title": "", "alignment": "connect"} | extra
    return PersonResult(name=name, profile_url=url, **values)


def _company(name: str, jobs=(), people=(), **extra: str) -> CompanyResult:
    values = {"url": "", "description": "", "alignment": ""} | extra
    return CompanyResult(name=name, jobs=list(jobs), people=list(people), **values)


def _search(search_id: str, hours: int, *companies: CompanyResult) -> SavedSearch:
    return SavedSearch(
        id=search_id,
        user_id="TEST_USER",
        title=f"Search {search_id}",
        created_at=T0 + timedelta(hours=hours),
        request=SearchRequest(background="a", looking_for="b"),
        results=SearchResults(summary="s", companies=list(companies)),
    )


def test_empty() -> None:
    assert catalog.companies([]) == []
    assert catalog.jobs([]) == []
    assert catalog.people([]) == []


def test_dedupes_across_searches_newest_data_wins_and_tracks_sightings() -> None:
    old = _search(
        "old",
        0,
        _company(
            "Acme Inc.",
            jobs=[_job("https://www.linkedin.com/jobs/view/123?trk=x", salary="$100k")],
            people=[_person("https://linkedin.com/in/jane-doe", title="Analyst")],
            url="https://acme.com",
            description="Old description",
        ),
    )
    new = _search(
        "new",
        5,
        _company(
            "ACME",
            jobs=[_job("https://uk.linkedin.com/jobs/view/123/", title="Sr Data Analyst")],
            people=[_person("https://www.linkedin.com/in/Jane-Doe/?trk=y")],
            description="New description",
        ),
    )
    # Order of input must not matter.
    for searches in ([old, new], [new, old]):
        [company] = catalog.companies(searches)
        assert company.key == "company:name:acme"
        assert company.name == "ACME"
        assert company.description == "New description"
        assert company.url == "https://acme.com"  # Blank in newest: filled from older.
        assert company.first_seen == old.created_at
        assert company.last_seen == new.created_at
        assert [s.id for s in company.searches] == ["new", "old"]
        assert (company.job_count, company.person_count) == (1, 1)

        [job] = catalog.jobs(searches)
        assert job.key == "job:url:linkedin.com/jobs/view/123"
        assert job.title == "Sr Data Analyst"
        assert job.salary == "$100k"
        assert job.company == "ACME"
        assert job.company_key == "company:name:acme"
        assert [s.id for s in job.searches] == ["new", "old"]

        [person] = catalog.people(searches)
        assert person.key == "person:linkedin:jane-doe"
        assert person.title == "Analyst"
        assert (person.first_seen, person.last_seen) == (old.created_at, new.created_at)


def test_orders_by_last_seen_then_position_and_keeps_distinct_entities() -> None:
    old = _search(
        "old",
        0,
        _company("Zeta", jobs=[_job("https://zeta.com/j/1")]),
        _company("Acme", jobs=[_job("https://acme.com/j/1"), _job("https://acme.com/j/2")]),
    )
    new = _search("new", 1, _company("Beta", jobs=[_job("https://beta.com/j/1")]))
    assert [c.name for c in catalog.companies([old, new])] == ["Beta", "Zeta", "Acme"]
    assert [j.url for j in catalog.jobs([old, new])] == [
        "https://beta.com/j/1",
        "https://zeta.com/j/1",
        "https://acme.com/j/1",
        "https://acme.com/j/2",
    ]
    acme = next(c for c in catalog.companies([old, new]) if c.name == "Acme")
    assert acme.job_count == 2


def test_duplicate_within_one_search_lists_search_once() -> None:
    jane = _person("https://linkedin.com/in/jane")
    search = _search("one", 0, _company("Acme", people=[jane]), _company("Beta", people=[jane]))
    [person] = catalog.people([search])
    assert [s.id for s in person.searches] == ["one"]
    assert person.company == "Acme"  # First sighting in the newest search wins.
    assert len(catalog.companies([search])) == 2


def test_fallback_keys_for_jobs_and_people_without_urls() -> None:
    search = _search(
        "one",
        0,
        _company("Acme", jobs=[_job(""), _job("", title="Data analyst")], people=[_person("")]),
    )
    [job] = catalog.jobs([search])
    assert job.key == "job:name:acme|data analyst"
    [person] = catalog.people([search])
    assert person.key == "person:name:jane doe|acme"


# --- Endpoints -------------------------------------------------------------------------


def _run(monkeypatch: pytest.MonkeyPatch, results: SearchResults) -> list[dict]:
    monkeypatch.setattr(agent, "run_search", lambda request: iter([ResultEvent(data=results)]))
    body = {"background": "Analyst", "location": "", "looking_for": "Data roles"}
    with client.stream("POST", "/api/search", json=body) as response:
        return [
            json.loads(line.removeprefix("data: "))
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]


def test_endpoints_empty_for_new_user() -> None:
    for kind in ("companies", "jobs", "people"):
        response = client.get(f"/api/entities/{kind}")
        assert response.status_code == 200
        assert response.json() == []


def test_unknown_entity_kind_is_404() -> None:
    assert client.get("/api/entities/widgets").status_code == 404


def test_new_search_updates_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    first = _run(
        monkeypatch,
        SearchResults(
            summary="1",
            companies=[
                _company(
                    "Acme",
                    jobs=[_job("https://acme.com/jobs/1")],
                    people=[_person("https://linkedin.com/in/jane")],
                )
            ],
        ),
    )
    assert [e["type"] for e in first] == ["result", "saved"]
    assert [c["name"] for c in client.get("/api/entities/companies").json()] == ["Acme"]
    assert len(client.get("/api/entities/jobs").json()) == 1

    second = _run(
        monkeypatch,
        SearchResults(
            summary="2",
            companies=[
                _company("Beta", jobs=[_job("https://beta.com/jobs/9")]),
                _company("Acme", people=[_person("https://www.linkedin.com/in/jane/")]),
            ],
        ),
    )
    first_id, second_id = first[1]["search"]["id"], second[1]["search"]["id"]

    companies = client.get("/api/entities/companies").json()
    assert [c["name"] for c in companies] == ["Beta", "Acme"]
    acme = companies[1]
    assert [s["id"] for s in acme["searches"]] == [second_id, first_id]
    assert acme["job_count"] == 1 and acme["person_count"] == 1

    jobs = client.get("/api/entities/jobs").json()
    assert [j["key"] for j in jobs] == ["job:url:beta.com/jobs/9", "job:url:acme.com/jobs/1"]
    # Entity keys match the result keys, so APPLIED/CONNECTED toggles line up.
    assert jobs[1]["key"] == first[0]["data"]["companies"][0]["jobs"][0]["key"]

    [person] = client.get("/api/entities/people").json()
    assert person["key"] == "person:linkedin:jane"
    assert [s["id"] for s in person["searches"]] == [second_id, first_id]
    assert person["company"] == "Acme"


def test_corrupt_search_file_is_skipped(isolated_database) -> None:
    history.save_search(
        "TEST_USER",
        SearchRequest(background="a", looking_for="b"),
        SearchResults(summary="s", companies=[_company("Acme")]),
    )
    folder = isolated_database / "users" / "TEST_USER" / "searches"
    (folder / f"{'f' * 32}.json").write_text("{not json", encoding="utf-8")
    assert [c["name"] for c in client.get("/api/entities/companies").json()] == ["Acme"]
