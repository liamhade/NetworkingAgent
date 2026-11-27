"""The `rank_jobs` step and the graph around it. Fake LLM, no network."""

import json

import pytest
from pipeline_fakes import COMPANIES, REQUEST, FakeSources, compiled, job_url, plan, ranking

import config
import pipeline
from pipeline import steps
from pipeline.state import CompanyKeywords, JobPosting, JobRank, JobRanking, SearchPlan
from schemas import JobResult, ResultEvent, SearchResults, TraceEvent


def posting(i: int, company: str = "Ramp", **fields) -> JobPosting:
    base = {
        "id": f"j{i}",
        "source": "builtin_jobs",
        "title": f"Analyst {i}",
        "url": f"https://example.com/{i}",
        "company": company,
        "requirements": "SQL. " * 400,
    }
    return JobPosting(**(base | fields))


def rank(job_id: str, score: int, **fields) -> JobRank:
    base = {
        "id": job_id,
        "score": score,
        "reason": "Fits.",
        "alignment": "You fit.",
        "years_required": "",
        "company": "",
    }
    return JobRank(**(base | fields))


def keywords(company: str, *words: str) -> CompanyKeywords:
    return CompanyKeywords(company=company, people_keywords=list(words))


def test_ranking_orders_by_score_and_keeps_the_top_max_jobs() -> None:
    jobs = [posting(i) for i in range(1, 6)]
    ranking_ = JobRanking(
        jobs=[rank("j1", 60), rank("j2", 90), rank("j3", 90), rank("j4", 20), rank("j5", 75)],
        companies=[],
    )
    ranked, _, dropped = steps.validate_ranking(ranking_, jobs, 3)
    assert [(r.job.id, r.rank, r.score) for r in ranked] == [
        ("j2", 1, 90),
        ("j3", 2, 90),
        ("j5", 3, 75),
    ]
    assert dropped == ["j1: over the limit of 3", "j4: over the limit of 3"]


def test_there_is_no_per_company_cap() -> None:
    jobs = [posting(i, company="Ramp") for i in range(1, 8)]
    ranking_ = JobRanking(jobs=[rank(j.id, 90 - int(j.id[1:])) for j in jobs], companies=[])
    ranked, _, _ = steps.validate_ranking(ranking_, jobs, 12)
    assert len(ranked) == 7
    chosen = steps.build_chosen(ranked, {}, [], plan())
    assert [(c.name, len(c.jobs)) for c in chosen] == [("Ramp", 7)]


def test_invalid_and_duplicate_ids_are_ignored_and_scores_are_clamped() -> None:
    jobs = [posting(1), posting(2)]
    ranking_ = JobRanking(
        jobs=[rank("j9", 99), rank(" j1 ", 150), rank("j1", 40), rank("j2", -5)], companies=[]
    )
    ranked, _, dropped = steps.validate_ranking(ranking_, jobs, 12)
    assert [(r.job.id, r.score) for r in ranked] == [("j1", 100), ("j2", 0)]
    assert dropped == ["j9: not a gathered job", "j1: duplicate"]


def test_the_rankers_years_and_employer_fill_the_job() -> None:
    jobs = [posting(1, company="", years_required="2 years"), posting(2)]
    ranking_ = JobRanking(
        jobs=[rank("j1", 80, years_required="3+ years", company="Acme"), rank("j2", 70)],
        companies=[],
    )
    ranked, _, _ = steps.validate_ranking(ranking_, jobs, 12)
    first, second = ranked
    assert (first.job.company, first.job.years_required, first.years_required) == (
        "Acme",
        "3+ years",
        "3+ years",
    )
    assert second.years_required == "" and second.job.company == "Ramp"


def test_people_keywords_come_from_the_ranker_with_a_default() -> None:
    jobs = [posting(1, company="Ramp"), posting(2, company="Notion")]
    ranking_ = JobRanking(
        jobs=[rank("j1", 90), rank("j2", 80)],
        companies=[keywords("ramp", "data manager", "recruiter", "extra")],
    )
    ranked, words, _ = steps.validate_ranking(ranking_, jobs, 12)
    chosen = steps.build_chosen(ranked, words, [], plan())
    assert [(c.name, c.score, c.people_keywords) for c in chosen] == [
        ("Ramp", 90, ["data manager", "recruiter"]),  # capped at 2
        ("Notion", 80, ["Data Analyst", "recruiter"]),  # not given: the default
    ]


def test_job_cards_are_compact() -> None:
    card = steps.job_card(posting(1, salary="100K", location="NYC"))
    assert '"id": "j1"' in card and '"salary": "100K"' in card
    assert len(card) < 1000  # requirements truncated (about 250 tokens)
    assert '"url"' not in card  # the company is known


def test_a_job_without_alignment_falls_back_to_its_reason() -> None:
    jobs = [posting(1), posting(2)]
    ranking_ = JobRanking(
        jobs=[rank("j1", 90, reason="Strong SQL match."), rank("j2", 70, alignment="")],
        companies=[],
    )
    ranked, _, _ = steps.validate_ranking(ranking_, jobs, 5)
    assert ranked[0].alignment == "You fit."  # the ranker's own
    assert ranked[1].alignment == "Fits."  # empty alignment: its reason


def test_the_prompt_asks_for_alignment_only_on_the_top_jobs() -> None:
    import prompts

    text = prompts.rank_jobs_prompt(7)
    assert "ONLY for the 7 jobs you score highest" in text and "at most 15 words" in text


def test_card_excerpts_are_cut_at_a_word_and_stay_small() -> None:
    long_text = "Requirements: " + "experience with distributed systems and SQL. " * 100
    card = steps.job_card(posting(1, requirements=long_text))
    assert len(card) < 1000
    requirements = json.loads(card)["requirements"]
    assert requirements.endswith("…") and not requirements.endswith(" …")
    assert requirements[:-1].split()[-1] in {
        "SQL.",
        "SQL",
        "and",
        "systems",
        "with",
        "of",
        "experience",
        "distributed",
    }


# --- the graph -----------------------------------------------------------------------


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> FakeSources:
    monkeypatch.setattr(config, "PEOPLE_AUTO_COMPANIES", 1)
    monkeypatch.setattr(config, "MAX_JOBS", 3)
    return FakeSources(monkeypatch)


def answers(ranked: JobRanking) -> dict:
    return {SearchPlan: plan(), JobRanking: ranked, SearchResults: compiled()}


def test_graph_runs_filter_between_find_jobs_and_rank_jobs(scripted_model, sources) -> None:
    ranked = ranking(("Plaid", 0, [("j5", 90), ("j1", 80)]), ("Ramp", 0, []))
    model = scripted_model(structured=answers(ranked))
    events = list(pipeline.run_search(REQUEST, llm=model))

    assert isinstance(events[-1], ResultEvent)
    names = [s.step for s in next(e for e in events if isinstance(e, TraceEvent)).steps]
    first_seen = [s for i, s in enumerate(names) if s not in names[:i]]
    assert first_seen == [
        "plan",
        "find_jobs",
        "filter",
        "complete",
        "rank_jobs",
        "find_people",
        "compile",
    ]
    assert [c["schema"] for c in model.structured_calls] == [SearchPlan, JobRanking, SearchResults]
    results = events[-1].data
    assert [c.name for c in results.companies] == ["Plaid", "Ramp"]
    assert [j.url for c in results.companies for j in c.jobs] == [job_url(5), job_url(1)]


def test_max_jobs_limits_the_results(scripted_model, sources) -> None:
    ranked = ranking(*[(c, 0, [(f"j{i + 1}", 90 - i)]) for i, c in enumerate(COMPANIES)])
    events = list(pipeline.run_search(REQUEST, llm=scripted_model(structured=answers(ranked))))
    assert [c.name for c in events[-1].data.companies] == COMPANIES[:3]


def test_rank_jobs_runs_on_its_own_model(scripted_model, sources) -> None:
    default = scripted_model(structured={SearchPlan: plan(), SearchResults: compiled()})
    ranker = scripted_model(structured={JobRanking: ranking(("Ramp", 0, [("j1", 80)]))})
    graph = pipeline.build_graph(default, ranker)
    final = graph.invoke({"request": REQUEST, "trace": []})
    assert "results" in final
    assert [c["schema"] for c in ranker.structured_calls] == [JobRanking]
    assert JobRanking not in [c["schema"] for c in default.structured_calls]


def test_config_defaults() -> None:
    assert config.RANK_MODEL == "anthropic:claude-sonnet-5-5"
    assert not hasattr(config, "RESCORE_MODEL") and not hasattr(config, "MAX_COMPANIES")


# --- saved searches ------------------------------------------------------------------


def test_a_saved_job_without_rank_still_loads() -> None:
    old = {
        "title": "Analyst",
        "url": "https://x.example/1",
        "location": "NYC",
        "salary": "",
        "alignment": "You fit.",
        "score": 70,
    }
    job = JobResult.model_validate(old)
    assert (job.rank, job.years_required, job.reason) == (None, None, None)
    assert job.score == 70
