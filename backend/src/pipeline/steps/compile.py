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
    postings = state.get("postings", {})
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
                        "title": j.title,
                        "url": j.url,
                        "location": j.location,
                        "salary": j.salary,
                        "summary": j.summary,
                        "posting_text": postings.get(j.url, ""),
                    }
                    for j in c.jobs
                ],
                "people_searched": c.name in people,
                "people": [person_data(p) for p in people.get(c.name, [])],
            }
        )
    return data


def match_jobs(written: list[JobResult], company: ChosenCompany) -> list[JobResult]:
    """`written` jobs that were gathered for `company` (by URL, else title), with the
    gathered URL and the ranking score, best first."""
    by_url = {url_key(j.url): j for j in company.jobs}
    by_title = {normalize_text(j.title): j for j in company.jobs}
    kept: dict[str, JobResult] = {}
    for job in written:
        found = by_url.get(url_key(job.url)) or by_title.get(normalize_text(job.title))
        if found is not None and found.id not in kept:
            score = company.job_scores.get(found.id)
            kept[found.id] = job.model_copy(update={"url": found.url, "score": score})
    return sorted(kept.values(), key=lambda j: -(j.score or 0))


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


def _fallback_company(c: ChosenCompany, found: list[Person] | None) -> CompanyResult:
    """A chosen company the compile step left out, built from gathered data only."""
    return CompanyResult(
        name=c.name,
        url=c.url or (c.jobs[0].url if c.jobs else ""),
        description=c.about or c.reason,
        alignment=c.reason,
        jobs=[
            JobResult(
                title=j.title,
                url=j.url,
                location=j.location,
                salary=j.salary,
                alignment="",
                score=c.job_scores.get(j.id),
            )
            for j in c.jobs
        ],
        people=[
            PersonResult(
                name=p.name,
                title=p.title or p.headline,
                profile_url=p.url,
                alignment="",
                shared_background=p.shared_background,
            )
            for p in sorted(found or [], key=lambda p: not p.shared_background)
            if p.at_company
        ][:4],
        score=c.score,
        people_searched=found is not None,
        people_keywords=c.people_keywords,
    )


def restrict_results(
    results: SearchResults, chosen: list[ChosenCompany], people: dict[str, list[Person]]
) -> tuple[SearchResults, dict[str, int]]:
    """Keep only what was gathered: chosen companies, their gathered jobs and found people.

    Companies get their ranking score and are sorted by it; a chosen company the LLM left
    out is added back from gathered data. Returns the results and drop/add counts.
    """
    by_name = {name_key(c.name): c for c in chosen}
    out: dict[str, CompanyResult] = {}
    counts = {"companies_dropped": 0, "jobs_dropped": 0, "people_dropped": 0, "companies_added": 0}
    for company in results.companies:
        key = name_key(company.name)
        c = by_name.get(key)
        if c is None or key in out:
            counts["companies_dropped"] += 1
            continue
        found = people.get(c.name)
        jobs = match_jobs(company.jobs, c)
        persons = match_people(company.people, found or [])
        counts["jobs_dropped"] += len(company.jobs) - len(jobs)
        counts["people_dropped"] += len(company.people) - len(persons)
        allowed = {url_key(u) for u in [c.url, *(j.url for j in c.jobs)] if u}
        url = company.url if url_key(company.url) in allowed else ""
        out[key] = company.model_copy(
            update={
                "name": c.name,
                "url": url or c.url or (c.jobs[0].url if c.jobs else ""),
                "jobs": jobs,
                "people": persons,
                "score": c.score,
                "people_searched": found is not None,
                "people_keywords": c.people_keywords,
            }
        )
    for key, c in by_name.items():
        if key not in out:
            out[key] = _fallback_company(c, people.get(c.name))
            counts["companies_added"] += 1
    companies = sorted(out.values(), key=lambda c: -(c.score or 0))
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
