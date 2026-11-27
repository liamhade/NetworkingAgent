"""Search board configuration: catalog, endpoint, request validation, prompt and pipeline
enforcement. Mocked LLM and sources only."""

import json

import pytest
from fastapi.testclient import TestClient
from pipeline_fakes import (
    DEFAULT_RANKING,
    REQUEST,
    FakeSources,
    ats_board,
    ats_job,
    compiled,
    plan,
)

import boards
import config
import pipeline
import prompts
import server
import tools
from pipeline import steps
from pipeline.state import (
    AtsJobQuery,
    CompanyRanking,
    ConservationJobQuery,
    SearchPlan,
    UsajobsQuery,
)
from schemas import ErrorEvent, ResultEvent, SearchRequest, SearchResults, StatusEvent, TraceEvent

client = TestClient(server.app)

ALL_IDS = [
    "builtin_nyc",
    "conservation",
    "greenhouse",
    "lever",
    "ashby",
    "workable",
    "usajobs",
    "google",
]


@pytest.fixture(autouse=True)
def pinned_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "ATS_MAX_BOARDS", 6)
    monkeypatch.setattr(config, "ATS_JOBS_PER_BOARD", 4)
    monkeypatch.setattr(config, "USAJOBS_API_KEY", "")
    monkeypatch.setattr(config, "USAJOBS_EMAIL", "")
    monkeypatch.setattr(config, "USAJOBS_MAX_QUERIES", 2)
    monkeypatch.setattr(config, "USAJOBS_RESULTS", 10)
    monkeypatch.setattr(config, "PEOPLE_AUTO_COMPANIES", 0)
    monkeypatch.setattr(config, "READ_POSTINGS", 0)


def with_usajobs_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "USAJOBS_API_KEY", "key")
    monkeypatch.setattr(config, "USAJOBS_EMAIL", "me@example.com")


def request_with(**settings: dict) -> SearchRequest:
    return REQUEST.model_copy(update={"boards": boards.normalize(settings)})


def off(*ids: str) -> dict:
    return {i: {"enabled": False} for i in ids}


# ----------------------------------------------------------------- catalog + endpoint


def test_endpoint_lists_every_board_with_labels_defaults_and_limits() -> None:
    body = client.get("/api/search/boards").json()
    assert [b["id"] for b in body] == ALL_IDS
    by_id = {b["id"]: b for b in body}
    assert by_id["builtin_nyc"]["label"] == "Built In NYC"
    assert by_id["conservation"]["label"] == "Conservation Job Board"
    assert [by_id[i]["label"] for i in ("greenhouse", "lever", "ashby", "workable")] == [
        "Greenhouse",
        "Lever",
        "Ashby",
        "Workable",
    ]
    for board in body:
        assert board["default"]["enabled"] is True
        assert board["min_jobs"] <= board["default"]["max_jobs"] <= board["max_jobs"]
        assert board["description"]
    assert by_id["builtin_nyc"]["available"] is True
    assert by_id["usajobs"]["available"] is False
    assert "API key" in by_id["usajobs"]["unavailable_reason"]


def test_usajobs_is_available_once_configured(monkeypatch) -> None:
    with_usajobs_key(monkeypatch)
    usajobs = next(b for b in client.get("/api/search/boards").json() if b["id"] == "usajobs")
    assert usajobs["available"] is True
    assert usajobs["unavailable_reason"] == ""


def test_ats_providers_unavailable_when_ats_is_off(monkeypatch) -> None:
    monkeypatch.setattr(config, "ATS_MAX_BOARDS", 0)
    body = {b["id"]: b for b in client.get("/api/search/boards").json()}
    assert all(not body[p]["available"] for p in ("greenhouse", "lever", "ashby", "workable"))
    assert boards.on_boards(boards.default_config()) == ["builtin_nyc", "conservation", "google"]


def test_defaults_match_todays_per_source_behaviour() -> None:
    defaults = {b.id: b.default.max_jobs for b in boards.catalog()}
    # Up to 3 queries of 15, 2 Google queries of 10, 2 USAJOBS queries of 10.
    assert defaults["builtin_nyc"] == steps.MAX_JOB_QUERIES * steps.BUILTIN_PER_QUERY
    assert defaults["conservation"] == steps.MAX_JOB_QUERIES * steps.BUILTIN_PER_QUERY
    assert defaults["google"] == steps.MAX_GOOGLE_QUERIES * steps.GOOGLE_PER_QUERY
    assert defaults["usajobs"] == config.USAJOBS_MAX_QUERIES * config.USAJOBS_RESULTS
    # The old shared 6 boards, split between the 4 providers: 2 boards of 4 jobs each.
    assert {defaults[p] for p in ("greenhouse", "lever", "ashby", "workable")} == {8}


# ---------------------------------------------------------------------- validation


def test_missing_boards_fall_back_to_defaults() -> None:
    request = SearchRequest(background="a", looking_for="b")
    assert request.boards == boards.default_config()
    assert list(request.boards) == ALL_IDS


def test_boards_are_clamped_filled_and_unknown_ids_dropped() -> None:
    request = SearchRequest(
        background="a",
        looking_for="b",
        boards={
            "builtin_nyc": {"enabled": False, "max_jobs": 5},
            "conservation": {"enabled": True, "max_jobs": 10_000},
            "lever": {"enabled": True, "max_jobs": -3},
            "ashby": {"max_jobs": "7"},
            "workable": {"enabled": "yes", "max_jobs": "lots"},
            "greenhouse": "nonsense",
            "myspace": {"enabled": True, "max_jobs": 5},
        },
    )
    cfg = request.boards
    assert "myspace" not in cfg
    assert list(cfg) == ALL_IDS
    assert cfg["builtin_nyc"].model_dump() == {"enabled": False, "max_jobs": 5}
    assert cfg["conservation"].max_jobs == 100  # clamped to the board's maximum
    assert cfg["lever"].max_jobs == 1  # clamped to the minimum
    assert cfg["ashby"].model_dump() == {"enabled": True, "max_jobs": 7}
    assert cfg["workable"] == boards.default_config()["workable"]  # malformed: defaults
    assert cfg["greenhouse"] == boards.default_config()["greenhouse"]
    assert cfg["google"] == boards.default_config()["google"]  # missing: default


def test_non_dict_boards_use_defaults() -> None:
    request = SearchRequest(background="a", looking_for="b", boards=["builtin_nyc"])
    assert request.boards == boards.default_config()


def test_config_roundtrips_as_a_self_contained_object() -> None:
    request = request_with(builtin_nyc={"enabled": False, "max_jobs": 9})
    again = SearchRequest.model_validate_json(request.model_dump_json())
    assert again.boards == request.boards


def test_search_endpoint_validates_saves_and_passes_boards(monkeypatch) -> None:
    seen: list[SearchRequest] = []

    def fake_run_search(request):
        seen.append(request)
        yield StatusEvent(message="Working")
        yield ResultEvent(data=SearchResults(summary="ok", companies=[]))

    monkeypatch.setattr(pipeline, "run_search", fake_run_search)
    body = {
        "background": "Analyst",
        "looking_for": "Data roles",
        "boards": {"lever": {"enabled": False, "max_jobs": 999}, "nope": {"enabled": True}},
    }
    with client.stream("POST", "/api/search", json=body) as response:
        events = [
            json.loads(line.removeprefix("data: "))
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]
    assert seen[0].boards["lever"].enabled is False
    assert seen[0].boards["lever"].max_jobs == 40
    assert "nope" not in seen[0].boards
    saved_id = events[-1]["search"]["id"]
    record = client.get(f"/api/searches/{saved_id}").json()
    assert record["request"]["boards"]["lever"] == {"enabled": False, "max_jobs": 40}
    assert set(record["request"]["boards"]) == set(ALL_IDS)


def test_old_saved_searches_without_boards_still_load() -> None:
    saved = {"background": "a", "location": "", "looking_for": "b"}
    assert SearchRequest.model_validate(saved).boards == boards.default_config()


# -------------------------------------------------------------------------- prompt


def test_prompt_by_default_offers_every_available_source() -> None:
    prompt = prompts.plan_prompt()
    for name in ("builtin_jobs", "builtin_companies", "conservation_jobs", "ats_jobs"):
        assert f"- {name}:" in prompt
    assert "- google_queries:" in prompt
    assert "Greenhouse, Lever, Ashby and Workable" in prompt
    assert "- usajobs:" not in prompt  # no key


def test_prompt_omits_disabled_boards() -> None:
    cfg = boards.normalize(off("builtin_nyc", "google", "lever", "workable"))
    prompt = prompts.plan_prompt(cfg)
    assert "- builtin_jobs:" not in prompt
    assert "- builtin_companies:" not in prompt
    assert "- google_queries:" not in prompt
    assert "- conservation_jobs:" in prompt
    assert "Greenhouse and Ashby" in prompt
    assert "Lever" not in prompt
    assert "Workable" not in prompt


def test_prompt_omits_ats_when_every_provider_is_off() -> None:
    cfg = boards.normalize(off("greenhouse", "lever", "ashby", "workable"))
    assert "- ats_jobs:" not in prompts.plan_prompt(cfg)


def test_prompt_offers_usajobs_only_when_on_and_configured(monkeypatch) -> None:
    with_usajobs_key(monkeypatch)
    assert "- usajobs:" in prompts.plan_prompt()
    assert "- usajobs:" not in prompts.plan_prompt(boards.normalize(off("usajobs")))


def test_plan_step_sends_the_filtered_prompt(scripted_model, monkeypatch) -> None:
    FakeSources(monkeypatch)
    request = request_with(**off("builtin_nyc", "conservation"))
    model = scripted_model(structured=answers_for(plan(builtin_jobs=[]), google=["data jobs"]))
    list(pipeline.run_search(request, llm=model))
    plan_call = next(c for c in model.structured_calls if c["schema"] is SearchPlan)
    system = plan_call["input"][0].content
    assert "- builtin_jobs:" not in system
    assert "- conservation_jobs:" not in system
    assert "- google_queries:" in system


# ------------------------------------------------------------------- cap_plan / nodes


def answers_for(search_plan: SearchPlan, google: list[str] | None = None) -> dict:
    if google is not None:
        search_plan = search_plan.model_copy(update={"google_queries": google})
    return {SearchPlan: search_plan, CompanyRanking: DEFAULT_RANKING, SearchResults: compiled()}


def run(model, request: SearchRequest = REQUEST) -> list:
    return list(pipeline.run_search(request, llm=model))


def trace_of(events: list) -> list:
    return next(e for e in events if isinstance(e, TraceEvent)).steps


def everything_plan() -> SearchPlan:
    return plan(
        conservation_jobs=[
            ConservationJobQuery(
                keyword="ecology", categories=[], locations=[], experience_levels=[]
            )
        ],
        usajobs=[UsajobsQuery(keywords="biologist", location="", agencies=[])],
        ats_jobs=[AtsJobQuery(keywords="data analyst", location="New York")],
        google_queries=["data analyst jobs"],
    )


def test_cap_plan_strips_disabled_boards_even_if_planned() -> None:
    request = request_with(**off("builtin_nyc", "conservation", "usajobs", "google"))
    capped = steps.cap_plan(everything_plan(), request)
    assert capped.builtin_jobs == []
    assert capped.builtin_companies == []
    assert capped.conservation_jobs == []
    assert capped.usajobs == []
    assert capped.google_queries == []
    assert len(capped.ats_jobs) == 1  # a provider is still on


def test_cap_plan_strips_ats_only_when_every_provider_is_off() -> None:
    some_on = request_with(**off("greenhouse", "lever", "ashby"))
    assert steps.cap_plan(everything_plan(), some_on).ats_jobs
    all_off = request_with(**off("greenhouse", "lever", "ashby", "workable"))
    assert steps.cap_plan(everything_plan(), all_off).ats_jobs == []


def test_cap_plan_no_google_fallback_when_google_is_off() -> None:
    empty = plan(builtin_jobs=[])
    assert steps.cap_plan(empty, REQUEST).google_queries != []
    assert steps.cap_plan(empty, request_with(**off("google"))).google_queries == []


def test_plan_trace_records_dropped_queries(scripted_model, monkeypatch) -> None:
    FakeSources(monkeypatch)
    request = request_with(**off("google"))
    events = run(scripted_model(structured=answers_for(plan(), google=["x jobs"])), request)
    plan_step = next(s for s in trace_of(events) if s.step == "plan")
    assert plan_step.note == "dropped queries for boards turned off: google_queries"


def test_every_board_off_is_an_error_without_calling_the_llm(scripted_model, monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    request = request_with(**off(*ALL_IDS))
    model = scripted_model(structured=answers_for(plan()))
    events = run(model, request)
    assert isinstance(events[-1], ErrorEvent)
    assert "turned off" in events[-1].message
    assert model.structured_calls == []
    assert sources.calls == []


# ---------------------------------------------------------------- find_jobs: skipping


def test_disabled_boards_are_never_queried_even_if_the_llm_plans_them(
    scripted_model, monkeypatch
) -> None:
    with_usajobs_key(monkeypatch)
    sources = FakeSources(monkeypatch)
    sources.ats_boards = [ats_board("acme")]
    request = request_with(**off("builtin_nyc", "conservation", "usajobs", "google"))
    # Straight to find_jobs: even without cap_plan, the node must not query them.
    state = {"request": request, "plan": everything_plan(), "trace": []}
    update = steps.find_jobs_node(state)
    called = {c for c, _ in sources.calls}
    assert called == {"ats_boards", "ats_jobs"}
    assert update["trace"][0].source == "boards"
    assert "builtin_nyc" in update["trace"][0].note
    assert "usajobs" in update["trace"][0].note


def test_builtin_companies_follow_the_builtin_toggle(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    from pipeline.state import BuiltinCompanyQuery

    queries = [BuiltinCompanyQuery(industries=["fintech"], tech_stack=[])]
    p = plan(builtin_companies=queries)
    steps.find_jobs_node({"request": request_with(**off("builtin_nyc")), "plan": p, "trace": []})
    assert "builtin_companies" not in {c for c, _ in sources.calls}
    steps.find_jobs_node({"request": REQUEST, "plan": p, "trace": []})
    assert "builtin_companies" in {c for c, _ in sources.calls}


def test_usajobs_enabled_but_unconfigured_is_skipped_with_a_note(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    update = steps.find_jobs_node({"request": REQUEST, "plan": everything_plan(), "trace": []})
    assert "usajobs_jobs" not in {c for c, _ in sources.calls}
    assert any(s.source == "usajobs" and "skipped" in s.note for s in update["trace"])


def test_no_google_fallback_when_google_is_off(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    sources.jobs = []
    p = plan()  # BuiltIn finds nothing: fewer than 5 jobs would normally add Google
    request = request_with(**off("google"))
    steps.find_jobs_node({"request": request, "plan": p, "trace": []})
    assert "google_search" not in {c for c, _ in sources.calls}
    steps.find_jobs_node({"request": REQUEST, "plan": p, "trace": []})
    assert "google_search" in {c for c, _ in sources.calls}


# ------------------------------------------------------------ find_jobs: per-board caps


def spy_n(monkeypatch, name: str) -> list[int]:
    """Record the `n` each call to `tools.<name>` was asked for (keeping the fake)."""
    seen: list[int] = []
    inner = getattr(tools, name)

    def wrapper(arg, n=15):
        seen.append(n)
        return inner(arg, n)

    monkeypatch.setattr(tools, name, wrapper)
    return seen


def test_default_config_asks_for_what_the_pipeline_always_did(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    builtin_n = spy_n(monkeypatch, "builtin_jobs")
    google_n = spy_n(monkeypatch, "google_search")
    sources.google = [
        {"title": "g", "url": "https://example.com/g", "site": "example.com", "snippet": ""}
    ]
    p = plan(google_queries=["a jobs", "b jobs"])
    update = steps.find_jobs_node({"request": REQUEST, "plan": p, "trace": []})
    assert builtin_n == [15]
    assert google_n == [10, 10]
    assert len(update["jobs"]) == 5 + 1  # five BuiltIn jobs, the one Google link (deduped)


def test_max_jobs_caps_the_jobs_gathered_and_asked_for(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)  # BuiltIn returns 5 jobs per query regardless of n
    builtin_n = spy_n(monkeypatch, "builtin_jobs")
    request = request_with(builtin_nyc={"enabled": True, "max_jobs": 2})
    update = steps.find_jobs_node({"request": request, "plan": plan(), "trace": []})
    assert builtin_n == [2]
    assert [j.source for j in update["jobs"]] == ["builtin_jobs", "builtin_jobs"]
    assert len(update["jobs"]) == 2
    assert sources.calls[0][0] == "builtin_jobs"


def test_max_jobs_is_a_total_across_a_boards_queries(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    builtin_n = spy_n(monkeypatch, "builtin_jobs")
    sources.jobs = [  # three jobs for the first query...
        {"title": f"Job {i}", "url": f"https://www.builtinnyc.com/job/{i}", "company": f"C{i}"}
        for i in range(3)
    ]
    two_queries = plan().model_copy(update={"builtin_jobs": plan().builtin_jobs * 2})
    request = request_with(builtin_nyc={"enabled": True, "max_jobs": 3})
    update = steps.find_jobs_node({"request": request, "plan": two_queries, "trace": []})
    assert len(update["jobs"]) == 3
    # The second query had no allowance left: it was not run, and the trace says so.
    assert builtin_n == [3]
    skipped = [s for s in update["trace"] if s.note.startswith("skipped:")]
    assert len(skipped) == 1 and "limit of 3" in skipped[0].note


def test_conservation_and_google_limits_apply(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    sources.google = [
        {"title": f"G{i}", "url": f"https://example.com/{i}", "site": "x", "snippet": ""}
        for i in range(6)
    ]
    google_n = spy_n(monkeypatch, "google_search")
    p = plan(builtin_jobs=[], google_queries=["a jobs", "b jobs"])
    request = request_with(google={"enabled": True, "max_jobs": 4})
    update = steps.find_jobs_node({"request": request, "plan": p, "trace": []})
    assert google_n == [4]  # the first query used up the allowance
    assert len(update["jobs"]) == 4


def test_usajobs_limit_applies(monkeypatch) -> None:
    with_usajobs_key(monkeypatch)
    sources = FakeSources(monkeypatch)
    sources.usajobs = [
        {"title": f"Biologist {i}", "url": f"https://www.usajobs.gov/job/{i}", "company": "NPS"}
        for i in range(10)
    ]
    n_seen = spy_n(monkeypatch, "usajobs_jobs")
    p = plan(
        builtin_jobs=[], usajobs=[UsajobsQuery(keywords="biologist", location="", agencies=[])]
    )
    request = request_with(usajobs={"enabled": True, "max_jobs": 3})
    update = steps.find_jobs_node({"request": request, "plan": p, "trace": []})
    assert n_seen == [3]
    assert len(update["jobs"]) == 3


# ------------------------------------------------------------- ATS per-provider limits


ATS_PLAN = plan(builtin_jobs=[], ats_jobs=[AtsJobQuery(keywords="data analyst", location="NYC")])


def ats_state(request: SearchRequest) -> dict:
    return {"request": request, "plan": ATS_PLAN, "trace": []}


def read_boards(update: dict) -> list[tuple[str, str]]:
    return [
        (s.args["provider"], s.args["board"]) for s in update["trace"] if s.source == "ats_jobs"
    ]


def test_every_provider_gets_its_own_allowance(monkeypatch) -> None:
    """Greenhouse used to fill the shared 6-board cap and starve the other providers."""
    sources = FakeSources(monkeypatch)
    sources.ats_boards = [
        *[ats_board(f"gh{i}") for i in range(10)],
        *[ats_board(f"lv{i}", provider="lever") for i in range(10)],
        *[ats_board(f"ab{i}", provider="ashby") for i in range(10)],
        *[ats_board(f"wk{i}", provider="workable") for i in range(10)],
    ]
    update = steps.find_jobs_node(ats_state(REQUEST))
    per_provider: dict[str, list[str]] = {}
    for provider, board in read_boards(update):
        per_provider.setdefault(provider, []).append(board)
    # Default allowance: 8 jobs = 2 boards of 4 for each provider.
    assert per_provider == {
        "greenhouse": ["gh0", "gh1"],
        "lever": ["lv0", "lv1"],
        "ashby": ["ab0", "ab1"],
        "workable": ["wk0", "wk1"],
    }


def test_a_providers_max_jobs_sets_its_board_allowance_and_job_size(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    sources.ats_boards = [
        *[ats_board(f"gh{i}") for i in range(10)],
        *[ats_board(f"lv{i}", provider="lever") for i in range(10)],
    ]
    request = request_with(
        greenhouse={"enabled": True, "max_jobs": 4},  # one board
        lever={"enabled": True, "max_jobs": 12},  # three boards
        **off("ashby", "workable"),
    )
    update = steps.find_jobs_node(ats_state(request))
    assert read_boards(update) == [
        ("greenhouse", "gh0"),
        ("lever", "lv0"),
        ("lever", "lv1"),
        ("lever", "lv2"),
    ]
    searched = {a[0] for c, a in sources.calls if c == "ats_boards"}
    assert searched == {"greenhouse", "lever"}  # no Google search for the providers that are off


def test_ats_max_jobs_below_a_board_shrinks_the_request(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    sources.ats_boards = [ats_board("acme"), ats_board("globex")]
    sources.ats_board_jobs = {
        "acme": [ats_job("Acme", i) for i in range(4)],
        "globex": [ats_job("Globex", i) for i in range(4)],
    }
    request = request_with(
        greenhouse={"enabled": True, "max_jobs": 3}, **off("lever", "ashby", "workable")
    )
    update = steps.find_jobs_node(ats_state(request))
    asked = [a[5] for c, a in sources.calls if c == "ats_jobs"]
    assert asked == [3]  # one board of at most 3 jobs; no second board
    assert len(update["jobs"]) == 3


def test_ats_budget_carries_across_boards_of_one_provider(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    sources.ats_boards = [ats_board("acme"), ats_board("globex"), ats_board("initech")]
    sources.ats_board_jobs = {
        "acme": [ats_job("Acme", i) for i in range(4)],
        "globex": [ats_job("Globex", i) for i in range(4)],
        "initech": [ats_job("Initech", i) for i in range(4)],
    }
    request = request_with(
        greenhouse={"enabled": True, "max_jobs": 6}, **off("lever", "ashby", "workable")
    )
    update = steps.find_jobs_node(ats_state(request))
    asked = [a[5] for c, a in sources.calls if c == "ats_jobs"]
    assert asked == [4, 2]  # 6 jobs: a full board, then the 2 that are left
    assert len(update["jobs"]) == 6


def test_disabled_ats_provider_is_not_searched_but_others_are(monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    sources.ats_boards = [ats_board("acme"), ats_board("plaid", provider="lever")]
    request = request_with(**off("greenhouse"))
    update = steps.find_jobs_node(ats_state(request))
    assert read_boards(update) == [("lever", "plaid")]
    assert ("ats_boards", ("greenhouse", "data analyst", "NYC")) not in sources.calls


def test_full_pipeline_with_a_trimmed_config_still_ranks_and_compiles(
    scripted_model, monkeypatch
) -> None:
    sources = FakeSources(monkeypatch)
    request = request_with(builtin_nyc={"enabled": True, "max_jobs": 3}, **off("google"))
    events = run(scripted_model(structured=answers_for(plan(), google=["x"])), request)
    assert isinstance(events[-1], ResultEvent)
    # The LLM ranked the (fewer) gathered jobs; ranking and ordering stay with the pipeline.
    assert ("google_search", "x") not in sources.calls
    assert len([s for s in trace_of(events) if s.source == "builtin_jobs"]) == 1


@pytest.mark.real_board_defaults
def test_new_searches_default_to_builtin_nyc_ashby_and_google() -> None:
    on = {b.id for b in boards.catalog() if b.default.enabled}
    assert on == {"builtin_nyc", "ashby", "google"}
    assert SearchRequest(background="a", looking_for="b").boards["conservation"].enabled is False
