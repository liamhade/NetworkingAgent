"""The people pane's search box: `POST /api/searches/{id}/people` with a typed `query`.

Mocked LinkedIn search and LLM only; no network.
"""

import pytest
from fastapi.testclient import TestClient
from pipeline_fakes import REQUEST, FakeSources, alumnus, compiled, notes_for

import config
import server
from entities import keys
from pipeline import on_demand, steps
from pipeline.state import PeopleNotes, PeopleQuery
from schemas import SearchResults
from userdata import history

client = TestClient(server.app)
SCHOOL = "Cornell University"


class QueryModel:
    """Stands in for the LLM: answers the query step with `terms` (or fails), and writes
    notes for every fake profile shown to it."""

    def __init__(self, sources: FakeSources, terms: PeopleQuery | None) -> None:
        self.sources = sources
        self.terms = terms
        self.purposes: list[str] = []
        self.typed: list[str] = []
        self._schema = None

    def with_structured_output(self, schema, method: str):
        self._schema = schema
        return self

    def invoke(self, messages, config):
        self.purposes.append(config["metadata"]["llm_purpose"])
        text = messages[1].content
        if self._schema is PeopleQuery:
            self.typed.append(text)
            if self.terms is None:
                raise RuntimeError("provider down")
            return self.terms
        assert self._schema is PeopleNotes
        candidates = [
            *(p for c, k, _ in self.sources.people_calls for p in self.sources.found(c, k)),
            *(p for found in self.sources.school_people.values() for p in found),
        ]
        return notes_for([p for p in candidates if p["url"] in text])


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> FakeSources:
    monkeypatch.setattr(config, "PEOPLE_PER_COMPANY", 2)
    return FakeSources(monkeypatch, default_people=2)


def use_model(monkeypatch, sources, terms: PeopleQuery | None) -> QueryModel:
    model = QueryModel(sources, terms)
    monkeypatch.setattr(on_demand, "get_llm", lambda: model)
    return model


@pytest.fixture
def saved() -> str:
    results = compiled({"Ramp": []})
    data = keys.annotate(SearchResults(summary=results.summary, companies=results.companies))
    return history.save_search("TEST_USER", REQUEST, data).id


def _post(search_id: str, company: str, query: str | None):
    body = {"company_key": keys.company_key(company), "query": query}
    return client.post(f"/api/searches/{search_id}/people", json=body)


def test_typed_query_becomes_the_search_terms(saved, sources, monkeypatch) -> None:
    terms = PeopleQuery(keywords=["data engineer"], location="New York")
    model = use_model(monkeypatch, sources, terms)
    response = _post(saved, "Etsy", "data engineers please")
    assert response.status_code == 200
    assert len(response.json()["people"]) == 2
    assert sources.people_calls == [("Etsy", "data engineer", "New York")]  # enough: no relaxing
    assert model.purposes == ["find_people_by_query", "find_people_on_demand"]
    assert "<typed>data engineers please</typed>" in model.typed[0]
    assert "<company>Etsy</company>" in model.typed[0]
    trace = history.get_search("TEST_USER", saved).trace
    assert [(s.step, s.source) for s in trace][:2] == [
        ("find_people_by_query", "llm"),
        ("find_people_by_query", "linkedin_people"),
    ]


def test_too_few_found_drops_the_location(saved, sources, monkeypatch) -> None:
    use_model(monkeypatch, sources, PeopleQuery(keywords=["designer"], location="New York"))
    sources.people[("Etsy", "designer")] = []
    _post(saved, "Etsy", "designers")
    assert sources.people_calls == [("Etsy", "designer", "New York"), ("Etsy", "designer", "")]


def test_my_school_searches_with_the_school_and_marks_alumni(saved, sources, monkeypatch) -> None:
    use_model(monkeypatch, sources, PeopleQuery(school=SCHOOL, location="New York"))
    sources.school_people[("Etsy", "", "New York")] = [
        alumnus("Etsy", SCHOOL, 0),
        alumnus("Etsy", SCHOOL, 1, mentions=False),
    ]
    body = _post(saved, "Etsy", "people who went to my school").json()
    assert sources.school_calls == [("Etsy", "", "New York", SCHOOL)]
    assert sources.people_calls == []
    shared = {p["name"]: p["shared_background"] for p in body["people"]}
    assert sorted(shared.values()) == ["", f"Same school: {SCHOOL}"]


def test_failed_interpretation_searches_the_raw_text(saved, sources, monkeypatch) -> None:
    use_model(monkeypatch, sources, None)
    assert _post(saved, "Etsy", "data folks").status_code == 200
    assert sources.people_calls == [("Etsy", "data folks", "New York")]
    trace = history.get_search("TEST_USER", saved).trace
    assert trace[0].error


def test_no_more_than_the_search_cap(sources) -> None:
    sources.default_people = 0
    _, trace = steps.search_people_by_query(
        "Etsy", ["a", "b", "c", "d"], "New York", "", "find_people_by_query"
    )
    assert len(trace) == steps.QUERY_MAX_SEARCHES


def test_blank_query_keeps_the_usual_ladder(saved, sources, monkeypatch) -> None:
    model = use_model(monkeypatch, sources, PeopleQuery(keywords=["never used"]))
    _post(saved, "Etsy", "   ")
    assert model.purposes == ["find_people_on_demand"]
    assert all(k != "never used" for _, k, _ in sources.people_calls)


def test_query_is_length_limited(saved) -> None:
    assert _post(saved, "Etsy", "x" * 301).status_code == 422
