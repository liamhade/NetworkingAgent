"""The `compile` node and result building."""

import logging
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

import prompts
from entities.keys import normalize_text
from pipeline.state import (
    ChosenCompany,
    Person,
    PipelineState,
    RankedJob,
)
from pipeline.steps.common import call, dump, format_profile, name_key, status, structured, url_key
from schemas import (
    CompanyResult,
    JobResult,
    PersonResult,
    SearchResults,
    TraceStep,
)

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# --------------------------------------------------------------------------- compile


def person_data(p: Person) -> dict[str, Any]:
    return p.model_dump(exclude={"keywords"}) | {"found_with": p.keywords}


def research_data(state: PipelineState) -> list[dict[str, Any]]:
    """The compile step's whole input: chosen companies with what was found for them."""
    people = state.get("people", {})
    data = []
    for c in state["chosen"]:
        data.append(
            {
                "name": c.name,
                "url": c.url,
                "about": c.about,
                "ranking_note": c.reason,
                "jobs": [
                    {
                        "title": r.job.title,
                        "url": r.job.url,
                        "location": r.job.location,
                        "salary": r.job.salary,
                        "years_required": r.years_required,
                        "posting_text": r.job.requirements,
                    }
                    for r in c.jobs
                ],
                "people_searched": c.name in people,
                "people": [person_data(p) for p in people.get(c.name, [])],
            }
        )
    return data


def job_result(item: RankedJob, written: JobResult | None = None) -> JobResult:
    """The result for a ranked job. Rank, score, reason, years and alignment are the
    ranker's; the compile step's own wording only fills an alignment the ranker left empty."""
    job = item.job
    return JobResult(
        title=job.title,
        url=job.url,
        location=job.location,
        salary=job.salary,
        alignment=item.alignment or (written.alignment if written else ""),
        score=item.score,
        rank=item.rank,
        years_required=item.years_required or None,
        reason=item.reason or None,
    )


def count_matched(written: list[JobResult], company: ChosenCompany) -> int:
    """How many of the compile step's jobs are ranked jobs of `company` (by URL, else title)."""
    urls = {url_key(r.job.url) for r in company.jobs}
    titles = {normalize_text(r.job.title) for r in company.jobs}
    return sum(url_key(j.url) in urls or normalize_text(j.title) in titles for j in written)


def _written_job(written: list[JobResult], item: RankedJob) -> JobResult | None:
    for job in written:
        if url_key(job.url) == url_key(item.job.url):
            return job
    return None


def match_people(written: list[PersonResult], found: list[Person]) -> list[PersonResult]:
    """`written` people that were found (by profile URL, else name), with the found URL."""
    by_url = {url_key(p.url): p for p in found}
    by_name = {normalize_text(p.name): p for p in found}
    kept: dict[str, PersonResult] = {}
    for person in written:
        match = by_url.get(url_key(person.profile_url)) or by_name.get(normalize_text(person.name))
        if match is not None and match.url not in kept:
            kept[match.url] = person.model_copy(
                update={"profile_url": match.url, "shared_background": match.shared_background}
            )
    return list(kept.values())


def _people_results(found: list[Person]) -> list[PersonResult]:
    return [
        PersonResult(
            name=p.name,
            title=p.title or p.headline,
            profile_url=p.url,
            alignment="",
            shared_background=p.shared_background,
        )
        for p in sorted(found, key=lambda p: not p.shared_background)
        if p.at_company
    ][:4]


def _fallback_company(c: ChosenCompany, found: list[Person] | None) -> CompanyResult:
    """A chosen company the compile step left out, built from gathered data only."""
    return CompanyResult(
        name=c.name,
        url=c.url or (c.jobs[0].job.url if c.jobs else ""),
        description=c.about or c.reason,
        alignment=c.reason,
        jobs=[job_result(r) for r in c.jobs],
        people=_people_results(found or []),
        score=c.score,
        people_searched=found is not None,
        people_keywords=c.people_keywords,
    )


def restrict_results(
    results: SearchResults, chosen: list[ChosenCompany], people: dict[str, list[Person]]
) -> tuple[SearchResults, dict[str, int]]:
    """Build the results from what was gathered, taking only wording from the compile step.

    Companies keep the ranker's order (best job first) and score (that job's score); their
    jobs are the ranked jobs in rank order with the ranker's score, reason and alignment;
    people are the compile step's, kept only if found. A chosen company the LLM left out is
    added back from gathered data. Returns the results and drop/add counts.
    """
    by_name = {name_key(c.name): c for c in chosen}
    written_by_key: dict[str, CompanyResult] = {}
    counts = {"companies_dropped": 0, "jobs_dropped": 0, "people_dropped": 0, "companies_added": 0}
    for company in results.companies:
        key = name_key(company.name)
        c = by_name.get(key)
        if c is None or key in written_by_key:
            counts["companies_dropped"] += 1
            continue
        written_by_key[key] = company
        found = people.get(c.name)
        persons = match_people(company.people, found or [])
        counts["jobs_dropped"] += len(company.jobs) - count_matched(company.jobs, c)
        counts["people_dropped"] += len(company.people) - len(persons)
    companies: list[CompanyResult] = []
    for key, c in by_name.items():
        company = written_by_key.get(key)
        found = people.get(c.name)
        if company is None:
            counts["companies_added"] += 1
            companies.append(_fallback_company(c, found))
            continue
        allowed = {url_key(u) for u in [c.url, *(r.job.url for r in c.jobs)] if u}
        url = company.url if url_key(company.url) in allowed else ""
        companies.append(
            company.model_copy(
                update={
                    "name": c.name,
                    "url": url or c.url or (c.jobs[0].job.url if c.jobs else ""),
                    "jobs": [job_result(r, _written_job(company.jobs, r)) for r in c.jobs],
                    "people": match_people(company.people, found or []),
                    "score": c.score,
                    "people_searched": found is not None,
                    "people_keywords": c.people_keywords,
                }
            )
        )
    return SearchResults(summary=results.summary, companies=companies), counts


def compile_node(state: PipelineState, llm: BaseChatModel) -> dict:
    status("Compiling your results")
    data = research_data(state)
    human = f"{format_profile(state['request'])}\n\n<research>\n{dump(data)}\n</research>"
    results, trace = call(
        "compile",
        "llm",
        {"companies": len(data)},
        lambda: structured(llm, SearchResults, prompts.compile_prompt(), human, "compile_results"),
    )
    if results is None:
        return {"error": f"Could not compile results: {trace.error}", "trace": [trace]}
    results, counts = restrict_results(results, state["chosen"], state.get("people", {}))
    check = TraceStep(step="compile", source="validate", args=counts, count=len(results.companies))
    return {"results": results, "trace": [trace, check]}
