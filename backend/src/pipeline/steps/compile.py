"""The `compile` node: people notes and company descriptions, then the results built in code.

Everything the ranker decided (which jobs, their order, scores, reasons, alignment, years) and
everything gathered (companies, URLs, people) is copied by code. The LLM call only writes what
needs writing: each contact's alignment note and LinkedIn connect message, and a one-sentence
description for companies the BuiltInNYC listing did not describe. It sees job titles, never
posting text, and only companies that need a description or have people. If no company does,
the call is skipped.
"""

import logging
from typing import Any

from langchain_core.language_models import BaseChatModel

import prompts
from entities.keys import normalize_text
from pipeline.state import (
    ChosenCompany,
    CompanyNotes,
    CompileNotes,
    Person,
    PipelineState,
    RankedJob,
)
from pipeline.steps.common import (
    call,
    dump,
    format_profile,
    name_key,
    plural,
    short,
    status,
    structured,
    url_key,
)
from schemas import (
    CompanyResult,
    JobResult,
    PersonResult,
    SearchResults,
    TraceStep,
)

log = logging.getLogger(__name__)

MAX_PEOPLE = 4
"""People shown per company."""
MAX_TITLES = 3
"""Job titles sent per company, as context for the connection notes."""
DESCRIPTION_CHARS = 300


def person_data(p: Person) -> dict[str, Any]:
    return p.model_dump(exclude={"keywords"}) | {"found_with": p.keywords}


def _compile_person(p: Person) -> dict[str, Any]:
    """A found person as the compile step sees them (no duplicate or unused fields)."""
    data = person_data(p)
    for unused in ("company", "snippet", "at_company"):
        data.pop(unused)
    return {k: v for k, v in data.items() if v}


def research_data(state: PipelineState) -> list[dict[str, Any]]:
    """The compile step's whole input: for each company that needs a description (the
    listing gave none) or has people, its name, up to `MAX_TITLES` job titles and the current
    employees found there. No posting text, scores or URLs."""
    people = state.get("people", {})
    data = []
    for c in state["chosen"]:
        found = [p for p in people.get(c.name, []) if p.at_company]
        if c.about and not found:
            continue
        data.append(
            {
                "name": c.name,
                "describe": not c.about,
                "job_titles": [r.job.title for r in c.jobs[:MAX_TITLES]],
                "people_searched": c.name in people,
                "people": [_compile_person(p) for p in found],
            }
        )
    return data


def job_result(item: RankedJob) -> JobResult:
    """The result for a ranked job: rank, score, reason, years and alignment are the
    ranker's; a job it wrote no alignment for shows its reason."""
    job = item.job
    return JobResult(
        title=job.title,
        url=job.url,
        location=job.location,
        salary=job.salary,
        alignment=item.alignment or item.reason,
        score=item.score,
        rank=item.rank,
        years_required=item.years_required or None,
        reason=item.reason or None,
    )


def match_people(written: list[PersonResult], found: list[Person]) -> list[PersonResult]:
    """`written` people that were found (by profile URL, else name). Name, title, profile
    URL and shared background are copied from the found person; only the alignment note and
    the connect message are the LLM's."""
    by_url = {url_key(p.url): p for p in found}
    by_name = {normalize_text(p.name): p for p in found}
    kept: dict[str, PersonResult] = {}
    for person in written:
        match = by_url.get(url_key(person.profile_url)) or by_name.get(normalize_text(person.name))
        if match is not None and match.url not in kept:
            kept[match.url] = person.model_copy(
                update={
                    "name": match.name,
                    "title": match.title or match.headline,
                    "profile_url": match.url,
                    "shared_background": match.shared_background,
                }
            )
    return list(kept.values())


def _people_results(found: list[Person]) -> list[PersonResult]:
    """Current employees without notes, for a company the LLM left out."""
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
    ][:MAX_PEOPLE]


def _company_result(
    c: ChosenCompany, found: list[Person] | None, description: str, people: list[PersonResult]
) -> CompanyResult:
    return CompanyResult(
        name=c.name,
        url=c.url or (c.jobs[0].job.url if c.jobs else ""),
        description=short(c.about, DESCRIPTION_CHARS) if c.about else description,
        alignment=c.reason,
        jobs=[job_result(r) for r in c.jobs],
        people=people,
        score=c.score,
        people_searched=found is not None,
        people_keywords=c.people_keywords,
    )


def build_summary(state: PipelineState) -> str:
    """The overview line, from the ranker's output (no LLM)."""
    ranked = state.get("ranked", [])
    plan = state.get("plan")
    chosen = state["chosen"]
    roles = f" for {', '.join(plan.role_titles[:2])}" if plan and plan.role_titles else ""
    companies = f"{len(chosen)} {'company' if len(chosen) == 1 else 'companies'}"
    text = f"Ranked {plural(len(ranked), 'job')} at {companies}{roles}, best fit first."
    if ranked:
        top = ranked[0]
        text += f" Top match: {top.job.title} ({top.score})."
    return text


def assemble_results(
    summary: str,
    notes: CompileNotes | None,
    chosen: list[ChosenCompany],
    people: dict[str, list[Person]],
) -> tuple[SearchResults, dict[str, int]]:
    """Build the results from what was gathered and ranked, taking only wording from `notes`.

    Companies keep the ranker's order (best job first) and score; their jobs are the ranked
    jobs in rank order. From `notes` come each company's description (only if the listing
    gave none) and its people's alignment and messages, kept only for people found at that
    company, at most `MAX_PEOPLE`. A company `notes` left out gets its current employees
    without notes. Returns the results and drop/add counts.
    """
    by_name = {name_key(c.name): c for c in chosen}
    written: dict[str, CompanyNotes] = {}
    counts = {"companies_dropped": 0, "people_dropped": 0, "companies_added": 0}
    for entry in notes.companies if notes else []:
        key = name_key(entry.name)
        if key not in by_name or key in written:
            counts["companies_dropped"] += 1
            continue
        written[key] = entry
    companies: list[CompanyResult] = []
    for key, c in by_name.items():
        found = people.get(c.name)
        entry = written.get(key)
        if entry is None:
            if notes is not None and (found or not c.about):
                counts["companies_added"] += 1
            companies.append(_company_result(c, found, "", _people_results(found or [])))
            continue
        persons = match_people(entry.people, found or [])[:MAX_PEOPLE]
        counts["people_dropped"] += len(entry.people) - len(persons)
        companies.append(_company_result(c, found, entry.description.strip(), persons))
    return SearchResults(summary=summary, companies=companies), counts


def compile_node(state: PipelineState, llm: BaseChatModel) -> dict:
    status("Compiling your results")
    data = research_data(state)
    notes: CompileNotes | None = None
    trace: list[TraceStep] = []
    if data:
        human = f"{format_profile(state['request'])}\n\n<research>\n{dump(data)}\n</research>"
        notes, step = call(
            "compile",
            "llm",
            {"companies": len(data)},
            lambda: structured(
                llm, CompileNotes, prompts.compile_prompt(), human, "compile_results"
            ),
        )
        trace.append(step)
        if notes is None:
            return {"error": f"Could not compile results: {step.error}", "trace": trace}
    else:
        trace.append(
            TraceStep(
                step="compile",
                source="llm",
                count=0,
                note="skipped: no company needs a description and nobody was found to write to",
            )
        )
    results, counts = assemble_results(
        build_summary(state), notes, state["chosen"], state.get("people", {})
    )
    trace.append(
        TraceStep(step="compile", source="validate", args=counts, count=len(results.companies))
    )
    return {"results": results, "trace": trace}
