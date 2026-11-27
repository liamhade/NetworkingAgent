"""The `filter` node: cheap code-only cuts before any posting is read or ranked.

Drops duplicates, jobs far from the user and jobs that ask for far more experience than the
user has; keeps the most recent, best title-matched `config.RANK_MAX_JOBS`; then completes
those with `complete_jobs` (boards such as builtinnyc.com answer a burst of reads with HTTP
429, so only jobs that survive are read) and drops, again, jobs whose real requirements turn
out to be far above the user's level. Every cut is conservative: a job with an unknown
location or experience is kept, and so is every remote job.
"""

import re

import config
from entities.keys import normalize_text
from pipeline.state import Job, JobPosting, PipelineState
from pipeline.steps.background import user_years
from pipeline.steps.common import name_key, plural, status, url_key
from pipeline.steps.complete import complete_jobs
from schemas import SearchRequest, SearchResults, TraceStep

FAR_YEARS = 4
"""A job is dropped when it asks for at least this many years more than the user has."""

_STATE = re.compile(r",\s*([A-Z]{2})\b")
_WORD = re.compile(r"[a-z]{2,}")
_GENERIC = {
    "remote", "hybrid", "onsite", "site", "office", "in", "on", "or", "and", "the", "of", "area",
    "metro", "greater", "united", "states", "usa", "us", "anywhere", "nationwide", "north",
    "america", "city", "county", "flexible", "multiple", "locations", "location",
}  # fmt: skip
_STATES = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar", "california": "ca",
    "colorado": "co", "connecticut": "ct", "delaware": "de", "florida": "fl", "georgia": "ga",
    "hawaii": "hi", "idaho": "id", "illinois": "il", "indiana": "in", "iowa": "ia",
    "kansas": "ks", "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md",
    "massachusetts": "ma", "michigan": "mi", "minnesota": "mn", "mississippi": "ms",
    "missouri": "mo", "montana": "mt", "nebraska": "ne", "nevada": "nv", "new hampshire": "nh",
    "new jersey": "nj", "new mexico": "nm", "new york": "ny", "north carolina": "nc",
    "north dakota": "nd", "ohio": "oh", "oklahoma": "ok", "oregon": "or", "pennsylvania": "pa",
    "rhode island": "ri", "south carolina": "sc", "south dakota": "sd", "tennessee": "tn",
    "texas": "tx", "utah": "ut", "vermont": "vt", "virginia": "va", "washington": "wa",
    "west virginia": "wv", "wisconsin": "wi", "wyoming": "wy",
}  # fmt: skip
_NYC_AREA = {"nyc", "ny", "nj", "brooklyn", "manhattan", "queens", "bronx", "hoboken", "jersey"}


def _places(text: str) -> set[str]:
    """Place tokens of a location: state codes (names and ", NY" forms), cities, NYC aliases."""
    lowered = text.lower()
    tokens = {t.lower() for t in _STATE.findall(text)}
    for name, code in _STATES.items():
        if name in lowered:
            tokens.add(code)
    tokens |= {w for w in _WORD.findall(lowered) if w not in _GENERIC}
    if tokens & _NYC_AREA or "new york" in lowered:
        tokens |= _NYC_AREA | {"ny"}
    return tokens


def far_from(user_location: str, job_location: str) -> bool:
    """True only when `job_location` names a place and shares nothing with the user's."""
    if not job_location.strip() or "remote" in job_location.lower():
        return False
    if not user_location.strip() or "remote" in user_location.lower():
        return False
    job, user = _places(job_location), _places(user_location)
    return bool(job) and bool(user) and not (job & user)


def min_years(label: str) -> int | None:
    """The first number of "3+ years" / "2-4 years", or None."""
    match = re.search(r"\d+", label)
    return int(match.group()) if match else None


def too_senior(job: Job, years: int | None) -> bool:
    required = min_years(job.years_required) if years is not None else None
    return required is not None and years is not None and required - years >= FAR_YEARS


def dedupe(jobs: list[Job]) -> list[Job]:
    """First of each URL, and of each company + title + location (the same job on two boards)."""
    seen_urls: set[str] = set()
    seen_titles: set[tuple[str, str, str]] = set()
    kept = []
    for job in jobs:
        url = url_key(job.url)
        title = (name_key(job.company), normalize_text(job.title), normalize_text(job.location))
        if url in seen_urls or (title[0] and title in seen_titles):
            continue
        seen_urls.add(url)
        seen_titles.add(title)
        kept.append(job)
    return kept


def order_jobs(jobs: list[Job], role_titles: list[str]) -> list[Job]:
    """Most recent first, then (stable) the best title match to the planned roles first."""
    words = {w for t in role_titles for w in _WORD.findall(t.lower()) if len(w) > 2}
    by_date = sorted(jobs, key=lambda j: j.posted_at, reverse=True)
    return sorted(by_date, key=lambda j: -len(words & set(_WORD.findall(j.title.lower()))))


def filter_jobs(
    jobs: list[Job], request: SearchRequest, role_titles: list[str], location: str, limit: int
) -> tuple[list[Job], dict[str, int]]:
    """The jobs worth reading and ranking, and how many each cut dropped."""
    years = user_years(request)
    unique = dedupe(jobs)
    near = [j for j in unique if not far_from(location, j.location)]
    fitting = [j for j in near if not too_senior(j, years)]
    kept = order_jobs(fitting, role_titles)[:limit]
    counts = {
        "jobs": len(jobs),
        "duplicates": len(jobs) - len(unique),
        "far_away": len(unique) - len(near),
        "too_senior": len(near) - len(fitting),
        "over_limit": len(fitting) - len(kept),
    }
    return kept, counts


def no_jobs_update(state: PipelineState, reason: str, trace: list[TraceStep]) -> dict:
    """The update when no posting is left to rank. If a BuiltInNYC company search listed
    companies, those are not an error (before job ranking such a search returned them):
    the results are empty, with a summary that says why and names the companies. Otherwise
    it is an error, which ends the graph."""
    listed = state.get("listed_companies", [])
    if not listed:
        return {
            "postings": [],
            "error": f"{reason} Try broadening what you're looking for.",
            "trace": trace,
        }
    names = ", ".join(c.name for c in listed[:8]) + (", and more" if len(listed) > 8 else "")
    summary = (
        f"{reason} BuiltInNYC listed {len(listed)} companies that "
        f"are hiring ({names}), but none of their job postings could be ranked for you. "
        "Try broadening what you're looking for, or search again."
    )
    trace.append(
        TraceStep(
            step="filter",
            source="filter",
            count=0,
            note=f"no jobs to rank; empty results because {len(listed)} listed companies",
        )
    )
    return {
        "postings": [],
        "results": SearchResults(summary=summary, companies=[]),
        "trace": trace,
    }


def filter_node(state: PipelineState) -> dict:
    request, plan = state["request"], state["plan"]
    jobs = state["jobs"]
    status(f"Filtering {plural(len(jobs), 'job')}")
    kept, counts = filter_jobs(
        jobs, request, plan.role_titles, request.location or plan.location, config.RANK_MAX_JOBS
    )
    trace = [
        TraceStep(
            step="filter",
            source="filter",
            args={**counts, "user_years": user_years(request), "limit": config.RANK_MAX_JOBS},
            count=len(kept),
        )
    ]
    if not kept:
        return no_jobs_update(
            state,
            "No job postings were left to rank after filtering by location and experience.",
            trace,
        )
    status(f"Reading {plural(len(kept), 'posting')}")
    completed, read_trace = complete_jobs(kept, max_reads=len(kept))
    trace += read_trace
    years = user_years(request)
    postings: list[JobPosting] = [p for p in completed if not too_senior(p, years)]
    trace.append(
        TraceStep(
            step="filter",
            source="filter",
            args={"stage": "completed", "too_senior": len(completed) - len(postings)},
            count=len(postings),
            note="years_required re-checked on the posting text",
        )
    )
    if not postings:
        return no_jobs_update(
            state, "Every posting asked for far more experience than you have.", trace
        )
    return {"postings": postings, "trace": trace}
