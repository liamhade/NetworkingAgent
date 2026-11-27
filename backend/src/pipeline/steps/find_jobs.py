"""The `find_jobs` node: board searches into `Job`s."""

import logging
import math
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

import ats
import config
import tools
from boards import BoardsConfig, effective_limit, is_on
from builtin_nyc.models import CompanyFilter, JobFilter
from conservation_jobboard.models import JobFilter as ConservationJobFilter
from experience import years_required
from pipeline.state import (
    Job,
    ListedCompany,
    PipelineState,
    SearchPlan,
)
from pipeline.steps.common import call, plural, short, status, url_key
from pipeline.steps.plan import MIN_JOBS_BEFORE_GOOGLE, google_fallback_query
from schemas import (
    TraceStep,
)
from usajobs.models import JobFilter as UsajobsFilter

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ------------------------------------------------------------------------- find_jobs


def _job_from(source: str, raw: dict[str, Any]) -> Job:
    if source == "google_search":
        return Job(
            id="",
            source=source,
            title=raw.get("title") or "",
            url=raw.get("url") or "",
            summary=f"{raw.get('site') or ''}: {raw.get('snippet') or ''}".strip(": "),
            years_required=years_required(raw.get("title"), raw.get("snippet")),
        )
    details = [raw.get(k) for k in ("job_type", "experience", "deadline", "summary")]
    return Job(
        id="",
        source=source,
        title=raw.get("title") or "",
        url=raw.get("url") or "",
        company=raw.get("company") or "",
        company_url=raw.get("company_url") or "",
        location=raw.get("location") or raw.get("work_arrangement") or "",
        salary=raw.get("salary") or "",
        summary=" · ".join(str(d) for d in details if d),
        level=raw.get("experience_level") or "",
        years_required=raw.get("years_required") or "",
    )


BUILTIN_PER_QUERY = 15
"""Jobs asked of one BuiltInNYC / Conservation Job Board query (the tools' default)."""
GOOGLE_PER_QUERY = 10
"""Results asked of one Google job search (the tool's default)."""

JobSearch = tuple[str, int, str, str, dict, Callable[[int], list]]
"""(board id, most jobs per query, source, label, args, run(n)) of one planned job search."""


def _job_searches(plan: SearchPlan, boards: BoardsConfig) -> list[JobSearch]:
    """Every planned job search of a board that is on, in order. Searches of boards that
    are off (or unavailable) are never built, whatever the plan says."""
    searches: list[JobSearch] = []
    if is_on(boards, "builtin_nyc"):
        for q in plan.builtin_jobs:
            job_filter = JobFilter(
                search=q.search.strip() or None,
                category=q.category,
                experience_levels=q.experience_levels,
                remote_preferences=q.remote_preferences,
            )
            searches.append(
                (
                    "builtin_nyc",
                    BUILTIN_PER_QUERY,
                    "builtin_jobs",
                    f"BuiltInNYC jobs for “{short(q.search or 'all roles')}”",
                    q.model_dump(mode="json"),
                    lambda n, f=job_filter: tools.builtin_jobs(f, n),
                )
            )
    if is_on(boards, "conservation"):
        for q in plan.conservation_jobs:
            conservation_filter = ConservationJobFilter(
                keyword=q.keyword.strip() or None,
                categories=q.categories,
                locations=q.locations,
                experience_levels=q.experience_levels,
            )
            what = q.keyword or ", ".join(q.categories) or "all roles"
            searches.append(
                (
                    "conservation",
                    BUILTIN_PER_QUERY,
                    "conservation_jobs",
                    f"Conservation Job Board for “{short(what)}”",
                    q.model_dump(mode="json"),
                    lambda n, f=conservation_filter: tools.conservation_jobs(f, n),
                )
            )
    if is_on(boards, "usajobs"):
        for uq in plan.usajobs:
            location = uq.location.strip()
            remote = location.lower() == "remote"
            usajobs_filter = UsajobsFilter(
                keyword=uq.keywords.strip() or None,
                location=None if remote else location or None,
                agencies=uq.agencies,
                remote=True if remote else None,
            )
            what = uq.keywords or ", ".join(uq.agencies) or "federal jobs"
            searches.append(
                (
                    "usajobs",
                    config.USAJOBS_RESULTS,
                    "usajobs",
                    f"USAJOBS for “{short(what)}”",
                    uq.model_dump(mode="json"),
                    lambda n, f=usajobs_filter: tools.usajobs_jobs(f, n),
                )
            )
    if is_on(boards, "google"):
        for query in plan.google_queries:
            searches.append(google_job_search(query))
    return searches


def google_job_search(query: str) -> JobSearch:
    return (
        "google",
        GOOGLE_PER_QUERY,
        "google_search",
        f"Google for “{short(query)}”",
        {"query": query},
        lambda n: tools.google_search(query, n),
    )


JobRunner = Callable[[JobSearch], int]
"""Runs one job search within its board's remaining allowance; returns the jobs it added."""


def _ats_allowance(max_jobs: int) -> int:
    """Boards a provider may read for `max_jobs` jobs (`ATS_JOBS_PER_BOARD` jobs each)."""
    return math.ceil(max_jobs / config.ATS_JOBS_PER_BOARD)


def _ats_searches(
    plan: SearchPlan,
    boards: BoardsConfig,
    run: JobRunner,
    budget: dict[str, int],
    trace: list[TraceStep],
) -> None:
    """For every planned ATS query and provider that is on: a Google `site:` search for
    boards, then each new board's postings from its API.

    Every provider has its own allowance from its `max_jobs` (`budget[provider]` jobs and
    `_ats_allowance` boards), so one provider can't use up another's: Greenhouse, searched
    first, no longer starves Lever, Ashby and Workable. Every board search and board read is
    its own trace step; a failing one is skipped.
    """
    providers = [p for p in ats.PROVIDERS.values() if is_on(boards, p.name)]
    allowed = {p.name: _ats_allowance(boards[p.name].max_jobs) for p in providers}
    read = {p.name: 0 for p in providers}
    fetched: set[tuple[str, str]] = set()
    for q in plan.ats_jobs:
        for provider in providers:
            if budget[provider.name] <= 0 or read[provider.name] >= allowed[provider.name]:
                continue
            keywords, location = q.keywords.strip(), q.location.strip()
            label = f"{provider.label} boards for “{short(keywords)}”"
            status(f"Searching Google for {label}")
            args = {"provider": provider.name, "keywords": keywords, "location": location}
            found, step = call(
                "find_jobs",
                "ats_boards",
                args,
                lambda p=provider.name, k=keywords, loc=location: tools.ats_boards(p, k, loc),
            )
            trace.append(step)
            if found is None:
                status(f"{label} failed: {short(step.error, 120)}")
                continue
            new = [b for b in found if (b["provider"], b["slug"].lower()) not in fetched]
            new = new[: allowed[provider.name] - read[provider.name]]
            step.note = f"{len(new)} new boards read"
            for board in new:
                if budget[provider.name] <= 0:
                    break
                fetched.add((board["provider"], board["slug"].lower()))
                read[provider.name] += 1
                run(
                    (
                        provider.name,
                        config.ATS_JOBS_PER_BOARD,
                        "ats_jobs",
                        f"{provider.label} board “{board['slug']}”",
                        {**args, "board": board["slug"], "job_ids": board["job_ids"]},
                        lambda n, b=board, k=keywords, loc=location: tools.ats_jobs(
                            b["provider"], b["slug"], k, loc, job_ids=b["job_ids"], n=n
                        ),
                    )
                )


def find_jobs_node(state: PipelineState) -> dict:
    plan = state["plan"]
    boards = state["request"].boards
    jobs: list[Job] = []
    seen: set[str] = set()
    trace: list[TraceStep] = []
    # Jobs each board may still add; a board that is off (or unavailable) has 0.
    budget = {board_id: effective_limit(boards, board_id) for board_id in boards}

    def run(search: JobSearch) -> int:
        board_id, per_query, source, label, args, fn = search
        remaining = budget[board_id]
        if remaining <= 0:
            trace.append(
                TraceStep(
                    step="find_jobs",
                    source=source,
                    args=args,
                    note=f"skipped: {board_id} reached its limit of {boards[board_id].max_jobs}",
                )
            )
            return 0
        status(f"Searching {label}")
        n = min(per_query, remaining)
        found, step = call("find_jobs", source, args, lambda: fn(n))
        trace.append(step)
        if found is None:
            status(f"{label} failed: {short(step.error, 120)}")
            return 0
        added = 0
        for raw in found:
            if added >= remaining:
                break
            job = _job_from(source, raw)
            key = url_key(job.url)
            if not job.url or not job.title or key in seen:
                continue
            seen.add(key)
            jobs.append(job.model_copy(update={"id": f"j{len(jobs) + 1}"}))
            added += 1
        budget[board_id] -= added
        step.note = f"{added} new"
        status(f"{label}: {plural(len(found), 'job')}")
        return added

    off = [board_id for board_id, setting in boards.items() if not setting.enabled]
    if off:
        trace.append(
            TraceStep(
                step="find_jobs",
                source="boards",
                args={"off": off},
                note="not searched, turned off: " + ", ".join(off),
            )
        )
    if plan.usajobs and boards["usajobs"].enabled and not config.usajobs_configured():
        trace.append(
            TraceStep(
                step="find_jobs",
                source="usajobs",
                args={"queries": len(plan.usajobs)},
                note="skipped: USAJOBS_API_KEY and USAJOBS_EMAIL are not both configured",
            )
        )
    for search in _job_searches(plan, boards):
        run(search)
    _ats_searches(plan, boards, run, budget, trace)
    if (
        len(jobs) < MIN_JOBS_BEFORE_GOOGLE
        and not plan.google_queries
        and is_on(boards, "google")
        and budget["google"] > 0
    ):
        run(google_job_search(google_fallback_query(plan, state["request"])))
        trace[-1].note += "; fallback: too few jobs from the planned sources"

    listed: list[ListedCompany] = []
    for q in plan.builtin_companies if is_on(boards, "builtin_nyc") else []:
        company_filter = CompanyFilter(
            industries=q.industries, tech_stack=q.tech_stack, hiring_only=True
        )
        status(f"Browsing BuiltInNYC companies in {short(', '.join(q.industries) or 'all')}")
        found, step = call(
            "find_jobs",
            "builtin_companies",
            q.model_dump(mode="json"),
            lambda f=company_filter: tools.builtin_companies(f),
        )
        trace.append(step)
        for raw in found or []:
            about = raw.get("mission") or raw.get("description") or ""
            listed.append(ListedCompany(name=raw["name"], url=raw.get("url") or "", about=about))

    update: dict = {"jobs": jobs, "listed_companies": listed, "trace": trace}
    if not jobs and not listed:
        update["error"] = (
            "No job postings found. Every job source failed or returned nothing; "
            "try broadening what you're looking for."
        )
    return update
