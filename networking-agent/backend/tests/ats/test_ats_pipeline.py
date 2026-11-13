"""ATS boards in the search pipeline's `find_jobs` step. Mocked LLM and sources only."""

import pytest
from pipeline_fakes import (
    COMPANIES,
    DEFAULT_RANKING,
    REQUEST,
    FakeSources,
    ats_board,
    ats_job,
    compiled,
    plan,
    ranking,
)

import config
import pipeline
from pipeline import steps
from pipeline.state import AtsJobQuery, CompanyRanking, SearchPlan
from schemas import ResultEvent, SearchResults, StatusEvent, TraceEvent

ATS_PLAN = plan(ats_jobs=[AtsJobQuery(keywords="data analyst", location="New York")])


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> FakeSources:
    monkeypatch.setattr(config, "PEOPLE_AUTO_COMPANIES", 0)
    monkeypatch.setattr(config, "READ_POSTINGS", 0)
    monkeypatch.setattr(config, "ATS_MAX_BOARDS", 6)
    monkeypatch.setattr(config, "ATS_JOBS_PER_BOARD", 4)
    return FakeSources(monkeypatch)


def run(model) -> list:
    return list(pipeline.run_search(REQUEST, llm=model))


def answers(search_plan: SearchPlan, ranked: CompanyRanking = DEFAULT_RANKING) -> dict:
    return {SearchPlan: search_plan, CompanyRanking: ranked, SearchResults: compiled()}


def trace_of(events: list) -> list:
    return next(e for e in events if isinstance(e, TraceEvent)).steps


def ats_steps(events: list) -> list:
    return [s for s in trace_of(events) if s.source.startswith("ats_")]


def test_ats_jobs_are_gathered_and_can_be_ranked(scripted_model, sources) -> None:
    sources.ats_boards = [
        ats_board("acme", "7"),
        ats_board("globex"),
        ats_board("plaid", provider="lever"),
    ]
    sources.ats_board_jobs = {"acme": [ats_job("Acme", 7), ats_job("Acme", 8)], "globex": []}
    ranked = ranking(("Acme", 95, [("j6", 90), ("j7", 70)]), ("Ramp", 80, [("j1", 80)]))
    events = run(scripted_model(structured=answers(ATS_PLAN, ranked)))

    assert ("ats_boards", ("greenhouse", "data analyst", "New York")) in sources.calls
    assert ("ats_jobs", ("greenhouse", "acme", "data analyst", "New York", ["7"], 4)) in (
        sources.calls
    )
    # One Google search per registered provider: Greenhouse, then Lever.
    assert ("ats_boards", ("lever", "data analyst", "New York")) in sources.calls
    assert ("ats_jobs", ("lever", "plaid", "data analyst", "New York", [], 4)) in sources.calls
    assert [
        (s.source, s.args["provider"], s.args.get("board"), s.count) for s in ats_steps(events)
    ] == [
        ("ats_boards", "greenhouse", None, 2),
        ("ats_jobs", "greenhouse", "acme", 2),
        ("ats_jobs", "greenhouse", "globex", 0),
        ("ats_boards", "lever", None, 1),
        ("ats_jobs", "lever", "plaid", 0),
    ]
    assert ats_steps(events)[0].note == "2 new boards read"
    results = events[-1].data
    assert isinstance(events[-1], ResultEvent)
    acme = next(c for c in results.companies if c.name == "Acme")
    assert acme.url == "https://job-boards.greenhouse.io/acme"
    assert [j.url for j in acme.jobs] == [
        "https://job-boards.greenhouse.io/acme/jobs/7",
        "https://job-boards.greenhouse.io/acme/jobs/8",
    ]


def test_boards_are_capped_and_deduplicated_across_queries(
    scripted_model, sources, monkeypatch
) -> None:
    monkeypatch.setattr(config, "ATS_MAX_BOARDS", 3)
    two = plan(
        ats_jobs=[
            AtsJobQuery(keywords="data analyst", location="New York"),
            AtsJobQuery(keywords="analytics engineer", location="New York"),
        ]
    )
    sources.ats_boards = [ats_board("acme"), ats_board("globex")]
    events = run(scripted_model(structured=answers(two)))
    read = [s.args["board"] for s in ats_steps(events) if s.source == "ats_jobs"]
    # The second query finds the same two boards: nothing new to read.
    assert read == ["acme", "globex"]
    assert [
        (s.args["provider"], s.note) for s in ats_steps(events) if s.source == "ats_boards"
    ] == [
        ("greenhouse", "2 new boards read"),
        ("lever", "0 new boards read"),
        ("greenhouse", "0 new boards read"),
        ("lever", "0 new boards read"),
    ]

    sources.calls.clear()
    sources.ats_boards = [ats_board(f"b{i}") for i in range(5)]
    events = run(scripted_model(structured=answers(two)))
    assert [s.args["board"] for s in ats_steps(events) if s.source == "ats_jobs"] == [
        "b0",
        "b1",
        "b2",
    ]
    # The cap was reached, so the second query's Google search never ran.
    assert [c for c, _ in sources.calls].count("ats_boards") == 1


def test_ats_turned_off(scripted_model, sources, monkeypatch) -> None:
    monkeypatch.setattr(config, "ATS_MAX_BOARDS", 0)
    sources.ats_boards = [ats_board("acme")]
    events = run(scripted_model(structured=answers(ATS_PLAN)))
    assert ats_steps(events) == []


def test_failing_board_search_and_board_are_recorded_and_skipped(scripted_model, sources) -> None:
    sources.ats_boards = [ats_board("broken"), ats_board("acme")]
    sources.ats_board_jobs = {"broken": RuntimeError("404 Not Found"), "acme": [ats_job("Acme", 1)]}
    events = run(scripted_model(structured=answers(ATS_PLAN)))
    assert isinstance(events[-1], ResultEvent)
    failed = [(s.source, s.args.get("board")) for s in trace_of(events) if s.error]
    assert failed == [("ats_jobs", "broken")]
    assert [s.count for s in ats_steps(events)] == [2, None, 1, 0]  # Lever found none

    sources.ats_boards = RuntimeError("CAPTCHA not solved")
    events = run(scripted_model(structured=answers(ATS_PLAN)))
    assert isinstance(events[-1], ResultEvent)  # BuiltIn jobs still carry the search
    assert [(s.source, s.args["provider"], s.error) for s in ats_steps(events)] == [
        ("ats_boards", "greenhouse", "RuntimeError: CAPTCHA not solved"),
        ("ats_boards", "lever", "RuntimeError: CAPTCHA not solved"),
    ]
    statuses = [e.message for e in events if isinstance(e, StatusEvent)]
    assert any("Greenhouse boards for “data analyst” failed" in m for m in statuses)


def test_ats_jobs_alone_are_enough_to_skip_the_google_fallback(
    scripted_model, sources, monkeypatch
) -> None:
    monkeypatch.setattr(config, "ATS_JOBS_PER_BOARD", 10)
    only_ats = plan(builtin_jobs=[], ats_jobs=ATS_PLAN.ats_jobs)
    sources.ats_boards = [ats_board("acme")]
    sources.ats_board_jobs = {"acme": [ats_job(c, i) for i, c in enumerate(COMPANIES)]}
    events = run(scripted_model(structured=answers(only_ats)))
    assert isinstance(events[-1], ResultEvent)
    assert not any(c == "google_search" for c, _ in sources.calls)


def test_cap_plan_limits_ats_queries() -> None:
    many = plan(
        builtin_jobs=[],
        ats_jobs=[
            AtsJobQuery(keywords=" ", location=""),
            *[AtsJobQuery(keywords=f"role {i}", location="") for i in range(4)],
        ],
    )
    capped = steps.cap_plan(many, REQUEST)
    assert [q.keywords for q in capped.ats_jobs] == ["role 0", "role 1"]
    assert capped.google_queries == []  # ATS counts as a planned source
