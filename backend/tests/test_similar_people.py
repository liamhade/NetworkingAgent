"""People with the user's school: the extra search, its relaxation ladder, cap and merge.

Mocked LinkedIn search only; no network.
"""

import pytest
from pipeline_fakes import FakeSources, alumnus, notes_for, plan, profile

import config
from pipeline import steps
from pipeline.state import ChosenCompany
from schemas import SearchRequest

SCHOOL = "Cornell University"


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> FakeSources:
    monkeypatch.setattr(config, "PEOPLE_PER_COMPANY", 1)
    monkeypatch.setattr(config, "PEOPLE_SIMILAR_MAX_QUERIES", 2)
    monkeypatch.setattr(config, "PEOPLE_SIMILAR_PER_COMPANY", 2)
    return FakeSources(monkeypatch, default_people=1)


def search(education=(SCHOOL,), location="New York"):
    return steps.search_people("Ramp", ["data manager"], location, education=list(education))


def test_similar_ladder_relaxes_keywords_then_location_and_is_capped() -> None:
    assert steps.similar_ladder(["data manager", "recruiter"], "NYC", 5) == [
        ("data manager", "NYC"),
        ("", "NYC"),
        ("", ""),
    ]
    assert steps.similar_ladder(["data manager"], "NYC", 2) == [
        ("data manager", "NYC"),
        ("", "NYC"),
    ]
    assert steps.similar_ladder(["data manager"], "NYC", 0) == []


def test_similar_ladder_drops_duplicate_rungs() -> None:
    assert steps.similar_ladder([], "", 3) == [("", "")]
    assert steps.similar_ladder([" "], "NYC", 3) == [("", "NYC"), ("", "")]


def test_school_search_merges_marked_people_after_the_normal_search(sources) -> None:
    sources.school_people[("Ramp", "data manager", "New York")] = [
        alumnus("Ramp", SCHOOL, 0),
        alumnus("Ramp", SCHOOL, 1),
    ]
    people, trace = search()
    label = f"Same school: {SCHOOL}"
    assert [p.shared_background for p in people] == ["", label, label]
    assert sources.school_calls == [("Ramp", "data manager", "New York", SCHOOL)]
    similar = [s for s in trace if s.args.get("school")]
    assert len(similar) == 1 and similar[0].step == "find_people"
    assert similar[0].count == 2 and "2 people with a shared school" in similar[0].note


def test_too_few_similar_people_relaxes_and_retries_up_to_the_cap(sources, monkeypatch) -> None:
    monkeypatch.setattr(config, "PEOPLE_SIMILAR_MAX_QUERIES", 3)
    monkeypatch.setattr(config, "PEOPLE_SIMILAR_PER_COMPANY", 3)
    sources.school_people[("Ramp", "data manager", "New York")] = []
    sources.school_people[("Ramp", "", "New York")] = [alumnus("Ramp", SCHOOL, 0)]
    sources.school_people[("Ramp", "", "")] = [alumnus("Ramp", SCHOOL, 1)]
    people, _ = search()
    assert [(k, loc) for _, k, loc, _ in sources.school_calls] == [
        ("data manager", "New York"),
        ("", "New York"),
        ("", ""),
    ]
    assert sum(bool(p.shared_background) for p in people) == 2


def test_extra_searches_never_exceed_the_cap(sources, monkeypatch) -> None:
    monkeypatch.setattr(config, "PEOPLE_SIMILAR_PER_COMPANY", 5)
    _, trace = search()
    assert len(sources.school_calls) == 2
    assert len([s for s in trace if s.args.get("school")]) == 2


def test_stops_once_enough_similar_people_were_found(sources) -> None:
    sources.school_people[("Ramp", "data manager", "New York")] = [
        alumnus("Ramp", SCHOOL, 0),
        alumnus("Ramp", SCHOOL, 1),
    ]
    search()
    assert len(sources.school_calls) == 1


def test_a_person_found_both_ways_appears_once_and_is_marked(sources) -> None:
    same = profile("Ramp", "data manager", 0)
    sources.people[("Ramp", "data manager")] = [same]
    sources.school_people[("Ramp", "data manager", "New York")] = [
        {**same, "snippet": f"{SCHOOL} · Economics"}
    ]
    people, _ = search()
    assert [p.url for p in people] == [same["url"]]
    assert people[0].shared_background == f"Same school: {SCHOOL}"


def test_a_known_url_is_not_added_again(sources) -> None:
    known = alumnus("Ramp", SCHOOL, 0)
    sources.school_people[("Ramp", "data manager", "New York")] = [known]
    people, _ = steps.search_people(
        "Ramp", ["data manager"], "New York", known_urls=[known["url"]], education=[SCHOOL]
    )
    assert known["url"] not in [p.url for p in people]


def test_a_school_that_is_not_on_the_result_is_not_claimed(sources) -> None:
    sources.school_people[("Ramp", "data manager", "New York")] = [
        alumnus("Ramp", SCHOOL, 0, mentions=False)
    ]
    people, _ = search()
    assert any(p.url.endswith("ramp-cornell-university-alumni-0") for p in people)
    assert not any(p.shared_background for p in people)


def test_a_former_employee_is_not_marked(sources) -> None:
    gone = {**alumnus("Ramp", SCHOOL, 0), "at_company": False}
    sources.school_people[("Ramp", "data manager", "New York")] = [gone]
    people, _ = search()
    assert not any(p.shared_background for p in people)


def test_a_failing_school_search_is_recorded_and_the_next_rung_runs(sources) -> None:
    sources.school_people[("Ramp", "data manager", "New York")] = RuntimeError("blocked")
    sources.school_people[("Ramp", "", "New York")] = [alumnus("Ramp", SCHOOL, 0)]
    people, trace = search()
    similar = [s for s in trace if s.args.get("school")]
    assert "blocked" in similar[0].error and not similar[1].error
    assert any(p.shared_background for p in people)


@pytest.mark.parametrize("education", [[], [""], ["  "]])
def test_no_education_skips_the_school_search(sources, education) -> None:
    people, trace = search(education)
    assert sources.school_calls == []
    assert all(not s.args.get("school") for s in trace)
    assert not any(p.shared_background for p in people)


def test_knob_zero_turns_the_school_search_off(sources, monkeypatch) -> None:
    monkeypatch.setattr(config, "PEOPLE_SIMILAR_MAX_QUERIES", 0)
    search()
    assert sources.school_calls == []


def test_profile_lists_the_cleaned_schools() -> None:
    request = SearchRequest(
        background="b", looking_for="l", education=[SCHOOL, f" {SCHOOL.lower()} ", "MIT"]
    )
    assert "<education>Cornell University; MIT</education>" in steps.format_profile(request)
    plain = SearchRequest(background="b", looking_for="l")
    assert "<education>" not in steps.format_profile(plain)


def test_marked_people_keep_their_mark_through_compile_matching(sources) -> None:
    sources.school_people[("Ramp", "data manager", "New York")] = [alumnus("Ramp", SCHOOL, 0)]
    people, _ = search()
    written = notes_for([{"name": p.name, "title": p.title, "url": p.url} for p in people])
    kept = steps.match_people(written.people, people)
    assert [p.shared_background for p in kept] == ["", f"Same school: {SCHOOL}"]


def test_the_pipeline_node_passes_the_users_school(sources) -> None:
    sources.school_people[("Ramp", "data manager", "New York")] = [alumnus("Ramp", SCHOOL, 0)]
    state = {
        "request": SearchRequest(background="b", looking_for="l", education=[SCHOOL]),
        "plan": plan(),
        "chosen": [ChosenCompany(name="Ramp", score=90, people_keywords=["data manager"])],
    }
    update = steps.find_people_node(state)
    assert any(p.shared_background for p in update["people"]["Ramp"])
    assert sum(1 for t in update["trace"] if t.args.get("school")) == 2
