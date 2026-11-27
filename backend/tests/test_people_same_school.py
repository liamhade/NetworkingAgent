"""The people pane's "only people from my school" checkbox: `same_school` on
`POST /api/searches/{id}/people`. Mocked LinkedIn search and LLM only; no network.
"""

import pytest
from fastapi.testclient import TestClient
from pipeline_fakes import REQUEST, FakeSources, alumnus, compiled, notes_for

import config
import server
from entities import keys
from pipeline import on_demand, steps
from pipeline.state import PeopleNotes
from schemas import SearchResults
from userdata import history

client = TestClient(server.app)
SCHOOL = "Cornell University"


class NotesModel:
    """Stands in for the LLM: writes notes for every fake school profile shown to it."""

    def __init__(self, sources: FakeSources) -> None:
        self.sources = sources
        self.purposes: list[str] = []

    def with_structured_output(self, schema, method: str):
        assert schema is PeopleNotes
        return self

    def invoke(self, messages, config):
        self.purposes.append(config["metadata"]["llm_purpose"])
        text = messages[1].content
        found = [p for people in self.sources.school_people.values() for p in people]
        return notes_for([p for p in found if p["url"] in text])


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> FakeSources:
    monkeypatch.setattr(config, "PEOPLE_PER_COMPANY", 2)
    return FakeSources(monkeypatch, default_people=2)


@pytest.fixture
def model(sources, monkeypatch) -> NotesModel:
    fake = NotesModel(sources)
    monkeypatch.setattr(on_demand, "get_llm", lambda: fake)
    return fake


def _saved(education: list[str]) -> str:
    results = compiled({"Ramp": []})
    data = keys.annotate(SearchResults(summary=results.summary, companies=results.companies))
    request = REQUEST.model_copy(update={"education": education})
    return history.save_search("TEST_USER", request, data).id


def _post(search_id: str, company: str, same_school: bool = True):
    body = {"company_key": keys.company_key(company), "same_school": same_school}
    return client.post(f"/api/searches/{search_id}/people", json=body)


def test_searches_only_the_users_school_and_marks_alumni(sources, model) -> None:
    saved = _saved([SCHOOL, "Other College"])
    sources.school_people[("Etsy", "", "New York")] = [
        alumnus("Etsy", SCHOOL, 0),
        alumnus("Etsy", SCHOOL, 1),
        alumnus("Etsy", SCHOOL, 2, mentions=False),
    ]
    response = _post(saved, "Etsy")
    assert response.status_code == 200
    assert sources.school_calls == [("Etsy", "", "New York", SCHOOL)]  # enough: no relaxing
    assert sources.people_calls == []  # never the usual ladder
    shared = sorted(p["shared_background"] for p in response.json()["people"])
    assert shared == ["", f"Same school: {SCHOOL}", f"Same school: {SCHOOL}"]
    assert model.purposes == ["find_people_on_demand"]
    trace = history.get_search("TEST_USER", saved).trace
    assert trace[0].step == "find_people_same_school"


def test_too_few_alumni_drops_the_location(sources, model) -> None:
    saved = _saved([SCHOOL])
    _post(saved, "Etsy")
    assert sources.school_calls == [
        ("Etsy", "", "New York", SCHOOL),
        ("Etsy", "", "", SCHOOL),
    ]


def test_without_a_school_it_says_so(sources, model) -> None:
    response = _post(_saved([]), "Etsy")
    assert response.status_code == 400
    assert "school" in response.json()["detail"]
    assert sources.school_calls == [] and sources.people_calls == []


def test_unchecked_keeps_the_usual_ladder(sources, model) -> None:
    _post(_saved([SCHOOL]), "Etsy", same_school=False)
    assert sources.people_calls  # the usual keyword ladder ran


def test_no_more_than_the_search_cap(sources) -> None:
    sources.default_people = 0
    _, trace = steps.search_people_by_query(
        "Etsy", ["a", "b", "c", "d"], "New York", "", "find_people_same_school"
    )
    assert len(trace) == steps.QUERY_MAX_SEARCHES
