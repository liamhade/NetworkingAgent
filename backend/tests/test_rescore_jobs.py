"""The experimental `rescore_jobs` step (`config.RESCORE_POSTINGS`)."""

import pytest
from pipeline_fakes import COMPANIES, DEFAULT_RANKING, REQUEST, FakeSources, compiled, plan

import config
import pipeline
from pipeline import steps
from pipeline.state import (
    ChosenCompany,
    CompanyRanking,
    CompanyRescore,
    Job,
    JobRescore,
    Rescoring,
    SearchPlan,
)
from schemas import ResultEvent, SearchResults, TraceEvent


@pytest.fixture
def sources(monkeypatch: pytest.MonkeyPatch) -> FakeSources:
    monkeypatch.setattr(config, "PEOPLE_SIMILAR_MAX_QUERIES", 0)
    return FakeSources(monkeypatch)


def rescoring(*companies: tuple[str, int, list[tuple[str, int, str]]]) -> Rescoring:
    return Rescoring(
        companies=[
            CompanyRescore(
                name=name,
                score=score,
                jobs=[JobRescore(id=i, score=s, years_required=y) for i, s, y in jobs],
            )
            for name, score, jobs in companies
        ]
    )


def run(scripted_model, sources: FakeSources, rescored: Rescoring | None) -> list:
    found = {c: sources.found(c, "data manager") for c in COMPANIES[:3]}
    answers = {SearchPlan: plan(), CompanyRanking: DEFAULT_RANKING, SearchResults: compiled(found)}
    if rescored is not None:
        answers[Rescoring] = rescored
    return list(pipeline.run_search(REQUEST, llm=scripted_model(structured=answers)))


def test_off_by_default_reads_only_the_compile_postings(scripted_model, sources) -> None:
    assert config.RESCORE_POSTINGS == 0
    events = run(scripted_model, sources, None)
    assert isinstance(events[-1], ResultEvent)
    reads = [url for name, url in sources.calls if name == "read_page"]
    assert len(reads) == config.READ_POSTINGS


def test_rescoring_reorders_companies_and_reuses_the_postings(
    scripted_model, sources, monkeypatch
) -> None:
    monkeypatch.setattr(config, "RESCORE_POSTINGS", 1)
    # Ramp was ranked first; its posting turns out to need 5+ years, so it drops.
    rescored = rescoring(("Ramp", 30, [("j1", 25, "5+ years")]), ("Plaid", 95, [("j5", 90, "")]))
    events = run(scripted_model, sources, rescored)
    results = events[-1].data
    assert isinstance(results, SearchResults)
    assert [c.name for c in results.companies][:2] == ["Plaid", "Notion"]
    assert results.companies[-1].name == "Ramp"
    assert results.companies[-1].score == 30
    assert results.companies[-1].jobs[0].score == 25
    # One read per company, and read_postings reused them instead of reading again.
    reads = [url for name, url in sources.calls if name == "read_page"]
    assert len(reads) == len(COMPANIES) == len(set(reads))
    trace = next(e for e in events if isinstance(e, TraceEvent)).steps
    assert [s.source for s in trace if s.step == "rescore_jobs"].count("llm") == 1


def test_apply_rescoring_ignores_unknown_companies_and_jobs() -> None:
    jobs = [
        Job(id="j1", source="s", title="A", url="u1"),
        Job(id="j2", source="s", title="B", url="u2"),
    ]
    chosen = [ChosenCompany(name="Acme", score=80, jobs=jobs, job_scores={"j1": 80, "j2": 60})]
    out = steps.apply_rescoring(
        chosen,
        rescoring(("acme", 50, [("j1", 30, "4+ years"), ("j9", 99, "")]), ("Nope", 99, [])),
    )
    (acme,) = out
    assert acme.score == 50
    assert [j.id for j in acme.jobs] == ["j2", "j1"]  # j1 dropped below j2
    assert acme.job_scores == {"j1": 30, "j2": 60}
    assert acme.jobs[1].years_required == "4+ years"


def test_posting_excerpt_jumps_to_requirements() -> None:
    text = "About us. " * 200 + "\n## Requirements\n- 4+ years of Go\n"
    excerpt = steps.posting_excerpt(text, 600)
    assert len(excerpt) <= 600
    assert "4+ years of Go" in excerpt
    assert excerpt.startswith("About us.")
