"""The LangGraph search pipeline (`pipeline`). Mocked LLM and sources only; no network."""

import pytest
from pipeline_fakes import (
    COMPANIES,
    DEFAULT_RANKING,
    REQUEST,
    FakeSources,
    compiled,
    job_url,
    plan,
    profile,
    ranking,
)

import config
import pipeline
from pipeline import steps
from pipeline.state import CompanyRanking, SearchPlan
from schemas import (
    ErrorEvent,
    JobResult,
    PersonResult,
    ResultEvent,
    SearchResults,
    StatusEvent,
    TraceEvent,
)


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> FakeSources:
    monkeypatch.setattr(config, "PEOPLE_PER_COMPANY", 3)
    monkeypatch.setattr(config, "PEOPLE_AUTO_COMPANIES", 3)
    monkeypatch.setattr(config, "MAX_COMPANIES", 6)
    monkeypatch.setattr(config, "READ_POSTINGS", 2)
    return FakeSources(monkeypatch)


def run(model) -> list:
    return list(pipeline.run_search(REQUEST, llm=model))


def answers(sources: FakeSources, **overrides) -> dict:
    """Structured answers per schema; compile includes everyone the fakes will find."""
    found = {c: sources.found(c, "data manager") for c in COMPANIES[:3]}
    return {SearchPlan: plan(), CompanyRanking: DEFAULT_RANKING, SearchResults: compiled(found)} | {
        {"plan": SearchPlan, "ranking": CompanyRanking, "results": SearchResults}[k]: v
        for k, v in overrides.items()
    }


def result_of(events: list) -> SearchResults:
    assert isinstance(events[-1], ResultEvent), events[-1]
    return events[-1].data


def trace_of(events: list) -> list:
    return next(e for e in events if isinstance(e, TraceEvent)).steps


# --- enforced steps ------------------------------------------------------------------


def test_top_companies_get_a_people_search_and_the_rest_are_marked_not_searched(
    scripted_model, sources
) -> None:
    events = run(scripted_model(structured=answers(sources)))
    results = result_of(events)

    searched = [company for company, _, _ in sources.people_calls]
    assert searched == COMPANIES[:3]  # one rung each: 3 current employees found at once
    assert [c.name for c in results.companies] == COMPANIES
    assert [c.people_searched for c in results.companies] == [True, True, True, False, False]
    assert [len(c.people) for c in results.companies] == [3, 3, 3, 0, 0]
    assert all(c.people_keywords == ["data manager"] for c in results.companies)


def test_every_top_company_is_searched_even_if_the_llm_ranks_one_without_jobs(
    scripted_model, sources, monkeypatch
) -> None:
    monkeypatch.setattr(config, "PEOPLE_AUTO_COMPANIES", 5)
    ranked = ranking(*[(c, 50, []) for c in COMPANIES])  # names only, no job ids
    run(scripted_model(structured=answers(sources, ranking=ranked)))
    assert sorted({c for c, _, _ in sources.people_calls}) == sorted(COMPANIES)


def test_results_are_sorted_by_score_and_jobs_by_job_score(scripted_model, sources) -> None:
    sources.jobs.append(
        {"title": "Lead Analyst", "url": job_url(6), "company": "Plaid", "location": "NYC"}
    )
    ranked = ranking(
        ("Etsy", 40, [("j4", 50)]),
        ("Plaid", 95, [("j5", 60), ("j6", 90)]),
        ("Ramp", 70, [("j1", 70)]),
    )
    written = compiled()
    plaid = written.companies[4]
    plaid.jobs.append(
        JobResult(title="Lead Analyst", url=job_url(6), location="", salary="", alignment="a")
    )
    events = run(scripted_model(structured=answers(sources, ranking=ranked, results=written)))
    results = result_of(events)

    assert [(c.name, c.score) for c in results.companies] == [
        ("Plaid", 95),
        ("Ramp", 70),
        ("Etsy", 40),
    ]
    assert [(j.url, j.score) for j in results.companies[0].jobs] == [
        (job_url(6), 90),
        (job_url(5), 60),
    ]
    # Only the top 3 by score get the automatic people search.
    assert [c for c, _, _ in sources.people_calls] == ["Plaid", "Ramp", "Etsy"]


def test_people_ladder_climbs_when_results_are_empty(scripted_model, sources) -> None:
    sources.people[("Ramp", "data manager")] = []
    sources.people[("Ramp", "recruiter")] = [profile("Ramp", "recruiter", at_company=False)]
    events = run(scripted_model(structured=answers(sources)))

    ramp_calls = [(k, loc) for c, k, loc in sources.people_calls if c == "Ramp"]
    assert ramp_calls == [("data manager", "New York"), ("recruiter", "New York"), ("", "")]
    rungs = [s for s in trace_of(events) if s.step == "find_people" and s.args["company"] == "Ramp"]
    assert [s.count for s in rungs] == [0, 1, 3]
    assert rungs[-1].note == "3 current employees so far"


def test_people_ladder_stops_once_enough_current_employees_are_found(sources) -> None:
    sources.people[("Ramp", "data manager")] = [profile("Ramp", "data manager", 0)]
    found, trace = steps.search_people("Ramp", ["data manager"], "New York")
    # 1 from the planned keywords, then 3 recruiters -> stop before "company only".
    assert [s.args["keywords"] for s in trace] == ["data manager", "recruiter"]
    assert len(found) == 4


def test_people_ladder_records_errors_and_keeps_going(sources) -> None:
    sources.people[("Ramp", "data manager")] = RuntimeError("Google returned job listings")
    found, trace = steps.search_people("Ramp", ["data manager"], "New York")
    assert "Google returned job listings" in trace[0].error
    assert trace[1].args["keywords"] == "recruiter" and not trace[1].error
    assert len(found) == 3


def test_ladder_skips_duplicate_rungs() -> None:
    assert steps.ladder(["Recruiter", " "], "") == [("Recruiter", ""), ("", "")]
    assert steps.ladder([], "NYC") == [("recruiter", "NYC"), ("", "")]


# --- validation: nothing that wasn't gathered ----------------------------------------


def test_compile_cannot_add_companies_jobs_or_people_that_were_not_gathered(
    scripted_model, sources
) -> None:
    real = sources.found("Ramp", "data manager")[0]
    written = compiled()
    ramp = written.companies[0]
    ramp.jobs.append(
        JobResult(
            title="Made-up job", url="https://x.example/1", location="", salary="", alignment=""
        )
    )
    ramp.people = [
        PersonResult(
            name="Invented Person", title="", profile_url="https://x.example/in/a", alignment=""
        ),
        # Right name, mangled URL: matched by name and the found URL is written back.
        PersonResult(
            name=real["name"], title="", profile_url="https://linkedin.com/in/typo", alignment=""
        ),
    ]
    written.companies[1].people = [  # Someone found at Ramp can't be listed under Notion.
        PersonResult(name="x", title="", profile_url=real["url"], alignment="")
    ]
    written.companies[3].people = [  # Etsy was never searched.
        PersonResult(name="y", title="", profile_url="https://www.linkedin.com/in/y", alignment="")
    ]
    written.companies.append(
        written.companies[0].model_copy(update={"name": "Fake Co", "url": "https://fake.example"})
    )
    del written.companies[2]  # Datadog left out: added back from gathered data.
    events = run(scripted_model(structured=answers(sources, results=written)))
    results = result_of(events)

    by_name = {c.name: c for c in results.companies}
    assert set(by_name) == set(COMPANIES)
    assert [j.url for j in by_name["Ramp"].jobs] == [job_url(1)]
    assert [(p.name, p.profile_url) for p in by_name["Ramp"].people] == [
        (real["name"], real["url"])
    ]
    assert by_name["Notion"].people == [] and by_name["Etsy"].people == []
    datadog = by_name["Datadog"]
    assert datadog.people_searched and len(datadog.people) == 3
    assert [j.url for j in datadog.jobs] == [job_url(3)]
    check = next(s for s in trace_of(events) if s.step == "compile" and s.source == "validate")
    assert check.args == {
        "companies_dropped": 1,
        "jobs_dropped": 1,
        "people_dropped": 3,
        "companies_added": 1,
    }


def test_company_url_must_come_from_the_gathered_data(scripted_model, sources) -> None:
    written = compiled()
    written.companies[0].url = "https://invented.example"
    results = result_of(run(scripted_model(structured=answers(sources, results=written))))
    assert results.companies[0].url == "https://www.builtinnyc.com/company/ramp"


def test_ranking_drops_unknown_companies_and_job_ids(scripted_model, sources) -> None:
    ranked = ranking(
        ("Ramp", 90, [("j1", 90), ("j2", 80), ("j99", 70)]),  # j2 is Notion's
        ("Imaginary Inc", 85, [("j42", 90)]),
        ("ramp", 60, []),  # duplicate
    )
    events = run(scripted_model(structured=answers(sources, ranking=ranked)))
    check = next(
        s for s in trace_of(events) if s.step == "rank_companies" and s.source == "validate"
    )
    assert check.args["dropped"] == [
        "Ramp: job j2",
        "Ramp: job j99",
        "Imaginary Inc: job j42",
        "Imaginary Inc: not in the data",
        "ramp: duplicate",
    ]
    assert [c.name for c in result_of(events).companies] == ["Ramp"]


def test_ranking_failure_falls_back_to_posting_counts(scripted_model, sources) -> None:
    sources.jobs.append({"title": "Analyst II", "url": job_url(6), "company": "Plaid"})
    events = run(scripted_model(structured=answers(sources, ranking=RuntimeError("provider down"))))
    results = result_of(events)
    assert results.companies[0].name == "Plaid"  # 2 postings
    assert {c for c, _, _ in sources.people_calls} == {"Plaid", "Ramp", "Notion"}


# --- graceful degradation ------------------------------------------------------------


def test_a_failing_source_is_recorded_and_the_search_continues(scripted_model, sources) -> None:
    two_sources = plan(google_queries=['"data analyst" jobs New York'])
    sources.google = RuntimeError("Chrome not found")
    events = run(scripted_model(structured=answers(sources, plan=two_sources)))
    assert isinstance(events[-1], ResultEvent)
    failed = [s for s in trace_of(events) if s.error]
    assert [(s.step, s.source) for s in failed] == [("find_jobs", "google_search")]
    statuses = [e.message for e in events if isinstance(e, StatusEvent)]
    assert any("failed: RuntimeError: Chrome not found" in m for m in statuses)


def test_few_jobs_adds_a_google_fallback_query(scripted_model, sources) -> None:
    sources.jobs = sources.jobs[:1]
    sources.google = [
        {"title": "Data Analyst - Acme", "url": "https://boards.greenhouse.io/acme/1"}
    ]
    ranked = ranking(("Ramp", 90, [("j1", 90)]), ("Acme", 70, [("j2", 80)]))
    events = run(scripted_model(structured=answers(sources, ranking=ranked)))
    assert ("google_search", '"Data Analyst" jobs New York, NY') in sources.calls
    assert [c.name for c in result_of(events).companies] == ["Ramp", "Acme"]


def test_nothing_found_is_a_single_error(scripted_model, sources) -> None:
    sources.jobs = RuntimeError("BuiltIn is down")
    sources.google = RuntimeError("Chrome not found")
    model = scripted_model(structured=answers(sources))
    events = run(model)
    assert [type(e) for e in events if not isinstance(e, StatusEvent)] == [ErrorEvent]
    assert "No job postings found" in events[-1].message
    assert [c["schema"] for c in model.structured_calls] == [SearchPlan]  # stopped early
    assert sources.people_calls == []


def test_plan_failure_is_an_error(scripted_model, sources) -> None:
    events = run(scripted_model(structured={SearchPlan: RuntimeError("provider down")}))
    assert isinstance(events[-1], ErrorEvent)
    assert "Could not plan the search" in events[-1].message


def test_compile_failure_is_an_error(scripted_model, sources) -> None:
    events = run(scripted_model(structured=answers(sources, results=RuntimeError("bad json"))))
    assert isinstance(events[-1], ErrorEvent)
    assert "Could not compile results" in events[-1].message


def test_plan_without_sources_gets_a_google_query(scripted_model, sources) -> None:
    empty = plan(builtin_jobs=[])
    assert steps.cap_plan(empty, REQUEST).google_queries == ['"Data Analyst" jobs New York, NY']


# --- event stream --------------------------------------------------------------------


def test_event_stream_order(scripted_model, sources) -> None:
    events = run(scripted_model(structured=answers(sources)))
    kinds = [type(e).__name__ for e in events]
    assert kinds[-2:] == ["TraceEvent", "ResultEvent"]
    assert set(kinds[:-2]) == {"StatusEvent"}
    messages = [e.message for e in events if isinstance(e, StatusEvent)]
    expected_order = [
        "Reading your profile",
        "Planning: Data Analyst, Analytics Engineer (mid level)",
        "Searching BuiltInNYC jobs for “data analyst”",
        "BuiltInNYC jobs for “data analyst”: 5 jobs",
        "Ranking companies from 5 jobs",
        "Top companies: Ramp (90), Notion (80), Datadog (70), Etsy (60), Plaid (50)",
        "Looking for data manager at Ramp",
        "Ramp: 3 current employees found",
        "Looking for data manager at Notion",
        "Notion: 3 current employees found",
        "Looking for data manager at Datadog",
        "Datadog: 3 current employees found",
        "Reading builtinnyc.com/job/1",
        "Reading builtinnyc.com/job/2",
        "Compiling your results",
    ]
    assert messages == expected_order
    assert [s.step for s in trace_of(events)] == [
        "plan",
        "find_jobs",
        "rank_companies",
        "rank_companies",
        "find_people",
        "find_people",
        "find_people",
        "read_postings",
        "read_postings",
        "compile",
        "compile",
    ]


def test_compile_input_is_only_gathered_data(scripted_model, sources) -> None:
    model = scripted_model(structured=answers(sources))
    run(model)
    [plan_call, rank_call, compile_call] = model.structured_calls
    assert compile_call["kwargs"] == {"method": "json_schema"}
    research = compile_call["input"][1].content
    assert "<research>" in research and "Posting https://www.builtinnyc.com/job/1" in research
    assert '"people_searched": false' in research  # Etsy / Plaid
    assert '"j1"' in rank_call["input"][1].content
