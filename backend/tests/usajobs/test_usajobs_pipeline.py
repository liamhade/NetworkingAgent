"""USAJOBS in `tools` and the search pipeline's plan and `find_jobs` steps. Mocked only."""

import json

import pytest
from pipeline_fakes import DEFAULT_RANKING, REQUEST, FakeSources, compiled, plan, slug

import config
import pipeline
import prompts
import tools
from pipeline import steps
from pipeline.state import JobRanking, SearchPlan, UsajobsQuery
from schemas import ResultEvent, SearchResults, TraceEvent
from usajobs import Agency, Job, JobFilter
from usajobs import api as usajobs_api

KEY = "secret-key-123"
EMAIL = "me@example.com"


def query(keywords: str = "wildlife biologist", location: str = "", agencies=()) -> UsajobsQuery:
    return UsajobsQuery(keywords=keywords, location=location, agencies=list(agencies))


def usajob(i: int, agency: str = "National Park Service") -> dict:
    return {
        "title": f"Wildlife Biologist {i}",
        "url": f"https://www.usajobs.gov/job/{i}",
        "company": agency,
        "location": "Denver, Colorado",
        "job_type": "Permanent · Full-time",
        "salary": "$64,957 - $84,447 per year",
        "deadline": "closes 2026-11-24",
        "summary": "One year of specialized experience.",
    }


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "USAJOBS_API_KEY", KEY)
    monkeypatch.setattr(config, "USAJOBS_EMAIL", EMAIL)
    monkeypatch.setattr(config, "USAJOBS_MAX_QUERIES", 2)
    monkeypatch.setattr(config, "USAJOBS_RESULTS", 3)


@pytest.fixture
def unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "USAJOBS_API_KEY", "")
    monkeypatch.setattr(config, "USAJOBS_EMAIL", "")


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> FakeSources:
    monkeypatch.setattr(config, "PEOPLE_AUTO_COMPANIES", 0)
    return FakeSources(monkeypatch)


@pytest.fixture
def run_scripted(scripted_model):
    """`run_scripted(search_plan)`: a whole search with the LLM answering with that plan."""

    def go(search_plan: SearchPlan) -> list:
        model = scripted_model(structured=answers(search_plan))
        return list(pipeline.run_search(REQUEST, llm=model))

    return go


def answers(search_plan: SearchPlan) -> dict:
    return {SearchPlan: search_plan, JobRanking: DEFAULT_RANKING, SearchResults: compiled()}


def usajobs_steps(events: list) -> list:
    steps_ = next(e for e in events if isinstance(e, TraceEvent)).steps
    return [s for s in steps_ if s.source == "usajobs"]


# ------------------------------------------------------------------------------ config


@pytest.mark.parametrize(
    ("key", "email", "queries", "expected"),
    [
        (KEY, EMAIL, 2, True),
        ("", EMAIL, 2, False),
        (KEY, "", 2, False),
        (KEY, EMAIL, 0, False),
    ],
)
def test_usajobs_configured(monkeypatch, key, email, queries, expected) -> None:
    monkeypatch.setattr(config, "USAJOBS_API_KEY", key)
    monkeypatch.setattr(config, "USAJOBS_EMAIL", email)
    monkeypatch.setattr(config, "USAJOBS_MAX_QUERIES", queries)
    assert config.usajobs_configured() is expected


# ------------------------------------------------------------------------------ prompt


def test_plan_prompt_offers_usajobs_only_when_configured(configured) -> None:
    assert "- usajobs:" in prompts.plan_prompt()
    assert "conservation" in prompts.USAJOBS_PLAN_PROMPT
    assert "{usajobs}" not in prompts.plan_prompt()
    assert KEY not in prompts.plan_prompt()


def test_plan_prompt_without_key_has_no_usajobs(unconfigured) -> None:
    prompt = prompts.plan_prompt()
    assert "usajobs" not in prompt.lower()
    assert "{usajobs}" not in prompt


# ------------------------------------------------------------------------------- tools


def test_tool_maps_jobs_and_uses_config(configured, monkeypatch) -> None:
    seen: dict = {}

    def fake_search(job_filter: JobFilter, n: int, api_key: str, email: str) -> list[Job]:
        seen.update(filter=job_filter, n=n, api_key=api_key, email=email)
        return [
            Job(
                title="Park Ranger",
                url="https://www.usajobs.gov/job/1",
                agency=None,
                department="Department of the Interior",
                closes="2026-11-24",
                summary="x" * 1000,
            )
        ]

    monkeypatch.setattr(usajobs_api, "search_jobs", fake_search)
    (out,) = tools.usajobs_jobs(JobFilter(keyword="ranger"))
    assert seen["n"] == 3
    assert (seen["api_key"], seen["email"]) == (KEY, EMAIL)
    assert out["company"] == "Department of the Interior"
    assert out["deadline"] == "closes 2026-11-24"
    assert len(out["summary"]) <= tools.MAX_TEXT


def test_tool_refuses_without_credentials(unconfigured) -> None:
    with pytest.raises(RuntimeError, match="not configured"):
        tools.usajobs_jobs(JobFilter())


# ------------------------------------------------------------------------------ wiring


def test_cap_plan_caps_and_drops_empty_queries(configured) -> None:
    many = plan(usajobs=[query("a"), query("", ""), query("b"), query("c")])
    capped = steps.cap_plan(many, REQUEST)
    assert [q.keywords for q in capped.usajobs] == ["a", "b"]


def test_usajobs_only_plan_needs_no_google_fallback_when_configured(configured) -> None:
    only = plan(builtin_jobs=[], usajobs=[query()])
    assert steps.cap_plan(only, REQUEST).google_queries == []


def test_usajobs_only_plan_falls_back_to_google_without_key(unconfigured) -> None:
    only = plan(builtin_jobs=[], usajobs=[query()])
    assert steps.cap_plan(only, REQUEST).google_queries != []


def test_usajobs_jobs_are_found_and_normalized(configured, sources, run_scripted) -> None:
    sources.usajobs = [usajob(1), usajob(2, "U.S. Fish and Wildlife Service")]
    wanted = plan(
        usajobs=[query("wildlife biologist", "Denver, Colorado", [Agency.NPS, Agency.USFWS])]
    )
    events = run_scripted(wanted)
    (call,) = [c for c in sources.calls if c[0] == "usajobs_jobs"]
    job_filter = call[1]
    assert isinstance(job_filter, JobFilter)
    assert job_filter.keyword == "wildlife biologist"
    assert job_filter.location == "Denver, Colorado"
    assert job_filter.agencies == [Agency.NPS, Agency.USFWS]
    assert job_filter.remote is None
    (step,) = usajobs_steps(events)
    assert (step.count, step.error, step.note) == (2, "", "2 new")
    assert step.args == {
        "keywords": "wildlife biologist",
        "location": "Denver, Colorado",
        "agencies": ["nps", "usfws"],
    }


def test_remote_location_becomes_remote_filter(configured, sources, run_scripted) -> None:
    run_scripted(plan(usajobs=[query(location="Remote")]))
    job_filter = next(c[1] for c in sources.calls if c[0] == "usajobs_jobs")
    assert job_filter.remote is True
    assert job_filter.location is None


def test_job_dict_shape_reaches_the_job_table(configured, sources) -> None:
    sources.usajobs = [usajob(1)]
    job = steps._job_from("usajobs", usajob(1))
    assert job.company == "National Park Service"
    assert job.url == "https://www.usajobs.gov/job/1"
    assert job.salary == "$64,957 - $84,447 per year"
    assert "closes 2026-11-24" in job.summary
    assert slug(job.company)  # a usable company key


def test_failure_is_recorded_and_search_continues(configured, sources, run_scripted) -> None:
    sources.usajobs = usajobs_api.UsajobsError("USAJOBS rate limit reached (HTTP 429)")
    events = run_scripted(plan(usajobs=[query()]))
    (step,) = usajobs_steps(events)
    assert "429" in step.error
    assert isinstance(events[-1], ResultEvent)  # BuiltIn jobs still produced results


# ---------------------------------------------------------------------------- skip path


def test_skipped_without_key_is_a_note_not_an_error(unconfigured, sources, run_scripted) -> None:
    events = run_scripted(plan(usajobs=[query()]))
    (step,) = usajobs_steps(events)
    assert step.error == ""
    assert step.count is None
    assert step.note.startswith("skipped:")
    assert not [c for c in sources.calls if c[0] == "usajobs_jobs"]
    assert isinstance(events[-1], ResultEvent)


def test_no_usajobs_step_when_not_planned(unconfigured, sources, run_scripted) -> None:
    assert usajobs_steps(run_scripted(plan())) == []


def test_no_secret_in_trace_or_events(configured, sources, run_scripted) -> None:
    sources.usajobs = [usajob(1)]
    events = run_scripted(plan(usajobs=[query()]))
    dumped = json.dumps([e.model_dump(mode="json") for e in events], default=str)
    assert KEY not in dumped
    assert EMAIL not in dumped
