"""The graph's nodes and the helpers they share with the on-demand people search.

Each node takes the `PipelineState`, returns a partial update, appends `TraceStep`s and
reports progress through `status()`. Source errors are recorded and skipped; a node only
sets `error` when nothing usable is left.
"""

import json
import logging
import math
import time
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel

import ats
import config
import linkedin
import prompts
import tools
from boards import BoardsConfig, effective_limit, is_on, on_boards
from builtin_nyc.models import CompanyFilter, JobFilter
from conservation_jobboard.models import JobFilter as ConservationJobFilter
from entities.keys import normalize_company_name, normalize_text, normalize_url
from llm_usage import run_config
from pipeline.state import (
    ChosenCompany,
    CompanyRanking,
    Job,
    ListedCompany,
    Person,
    PipelineState,
    SearchPlan,
    UsajobsQuery,
)
from schemas import (
    CompanyResult,
    JobResult,
    PersonResult,
    SearchRequest,
    SearchResults,
    StatusEvent,
    TraceStep,
)
from usajobs.models import JobFilter as UsajobsFilter

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_JOB_QUERIES = 3
MAX_GOOGLE_QUERIES = 2
MAX_ATS_QUERIES = 2
MIN_JOBS_BEFORE_GOOGLE = 5
"""Fewer jobs than this from the planned sources (and no Google query planned) adds one."""
MAX_JOBS_PER_COMPANY = 4
MAX_PEOPLE_KEYWORDS = 2


# --------------------------------------------------------------------------- helpers


def status(message: str) -> None:
    """Report progress as a `StatusEvent` (a no-op outside a running graph)."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        return
    writer(StatusEvent(message=message))


def call(
    step: str, source: str, args: dict[str, Any], fn: Callable[[], Any]
) -> tuple[Any, TraceStep]:
    """Run `fn`, timing it; an exception becomes the trace step's `error` (value None)."""
    started = time.perf_counter()
    value, error = None, ""
    try:
        value = fn()
    except Exception as exc:  # noqa: BLE001
        log.warning("%s/%s failed: %s", step, source, exc)
        error = f"{type(exc).__name__}: {exc}"
    trace = TraceStep(
        step=step,
        source=source,
        args=args,
        count=len(value) if isinstance(value, list) else None,
        error=error,
        duration_ms=round((time.perf_counter() - started) * 1000),
    )
    return value, trace


def structured(llm: BaseChatModel, schema: type[T], system: str, human: str, purpose: str) -> T:
    """One structured-output call, logged under `purpose` in the LLM usage CSV."""
    model = llm.with_structured_output(schema, method="json_schema")
    result = model.invoke([SystemMessage(system), HumanMessage(human)], config=run_config(purpose))
    return result if isinstance(result, schema) else schema.model_validate(result)


def clean_schools(education: Iterable[str]) -> list[str]:
    """School names with blanks and repeats (any case) removed, order kept."""
    schools: list[str] = []
    for name in education:
        name = " ".join(name.split())
        if name and name.lower() not in {s.lower() for s in schools}:
            schools.append(name)
    return schools


def format_profile(request: SearchRequest) -> str:
    schools = clean_schools(request.education)
    education = f"<education>{'; '.join(schools)}</education>\n" if schools else ""
    return (
        f"<background>\n{request.background.strip()}\n</background>\n"
        f"{education}"
        f"<location>{request.location.strip() or 'not specified'}</location>\n"
        f"<looking_for>\n{request.looking_for.strip()}\n</looking_for>"
    )


def _short(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _url_key(url: str) -> str:
    return normalize_url(url) or url.strip()


def _name_key(name: str) -> str:
    return normalize_company_name(name)


def dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1)


def _scored(value: int) -> int:
    return max(0, min(100, int(value)))


# ------------------------------------------------------------------------------ plan


def _usajobs_wanted(q: UsajobsQuery) -> bool:
    return bool(q.keywords.strip() or q.location.strip() or q.agencies)


def _user_off(request: SearchRequest, board_id: str) -> bool:
    """True when the user turned the board off (an unavailable board is a different case)."""
    return not request.boards[board_id].enabled


def _ats_user_off(request: SearchRequest) -> bool:
    return all(_user_off(request, name) for name in ats.PROVIDERS)


def turned_off_queries(plan: SearchPlan, request: SearchRequest) -> list[str]:
    """Plan fields that hold queries for boards the user turned off (they get dropped)."""
    planned = {
        "builtin_jobs": bool(plan.builtin_jobs) and _user_off(request, "builtin_nyc"),
        "builtin_companies": bool(plan.builtin_companies) and _user_off(request, "builtin_nyc"),
        "conservation_jobs": bool(plan.conservation_jobs) and _user_off(request, "conservation"),
        "usajobs": bool(plan.usajobs) and _user_off(request, "usajobs"),
        "ats_jobs": bool(plan.ats_jobs) and _ats_user_off(request),
        "google_queries": bool(plan.google_queries) and _user_off(request, "google"),
    }
    return [field for field, dropped in planned.items() if dropped]


def cap_plan(plan: SearchPlan, request: SearchRequest) -> SearchPlan:
    """Enforce the plan's limits and the search's board config (queries for boards the user
    turned off are dropped, even if the LLM planned them); with no source at all, fall back
    to one Google query (when Google is on)."""
    off = turned_off_queries(plan, request)
    plan = plan.model_copy(
        update={
            "role_titles": [t.strip() for t in plan.role_titles if t.strip()][:3],
            "builtin_jobs": plan.builtin_jobs[:MAX_JOB_QUERIES],
            "builtin_companies": plan.builtin_companies[:1],
            "conservation_jobs": plan.conservation_jobs[:MAX_JOB_QUERIES],
            "usajobs": [q for q in plan.usajobs if _usajobs_wanted(q)][
                : config.USAJOBS_MAX_QUERIES
            ],
            "ats_jobs": [q for q in plan.ats_jobs if q.keywords.strip()][:MAX_ATS_QUERIES],
            "google_queries": [q.strip() for q in plan.google_queries if q.strip()][
                :MAX_GOOGLE_QUERIES
            ],
        }
    )
    plan = plan.model_copy(update={field: [] for field in off})
    usajobs_usable = bool(plan.usajobs) and config.usajobs_configured()
    if not _user_off(request, "google") and not (
        plan.builtin_jobs
        or plan.conservation_jobs
        or usajobs_usable
        or plan.ats_jobs
        or plan.google_queries
    ):
        plan.google_queries = [google_fallback_query(plan, request)]
    return plan


def google_fallback_query(plan: SearchPlan, request: SearchRequest) -> str:
    role = plan.role_titles[0] if plan.role_titles else _short(request.looking_for, 50)
    location = plan.location or request.location
    return f'"{role}" jobs {location}'.strip()


def plan_node(state: PipelineState, llm: BaseChatModel) -> dict:
    request = state["request"]
    if not on_boards(request.boards):
        return {
            "error": "Every job board is turned off (or unavailable). Turn at least one on "
            "in the search boards panel.",
            "trace": [],
        }
    system = prompts.plan_prompt(request.boards)
    plan, trace = call(
        "plan",
        "llm",
        {},
        lambda: structured(llm, SearchPlan, system, format_profile(request), "plan"),
    )
    if plan is None:
        return {"error": f"Could not plan the search: {trace.error}", "trace": [trace]}
    dropped = turned_off_queries(plan, request)
    plan = cap_plan(plan, request)
    trace.args = plan.model_dump(mode="json")
    if dropped:
        trace.note = f"dropped queries for boards turned off: {', '.join(dropped)}"
    roles = ", ".join(plan.role_titles) or "your target roles"
    status(f"Planning: {roles}" + (f" ({plan.seniority})" if plan.seniority else ""))
    return {"plan": plan, "trace": [trace]}


# ------------------------------------------------------------------------- find_jobs


def _job_from(source: str, raw: dict[str, Any]) -> Job:
    if source == "google_search":
        return Job(
            id="",
            source=source,
            title=raw.get("title") or "",
            url=raw.get("url") or "",
            summary=f"{raw.get('site') or ''}: {raw.get('snippet') or ''}".strip(": "),
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
                    f"BuiltInNYC jobs for “{_short(q.search or 'all roles')}”",
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
                    f"Conservation Job Board for “{_short(what)}”",
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
                    f"USAJOBS for “{_short(what)}”",
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
        f"Google for “{_short(query)}”",
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
            label = f"{provider.label} boards for “{_short(keywords)}”"
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
                status(f"{label} failed: {_short(step.error, 120)}")
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
            status(f"{label} failed: {_short(step.error, 120)}")
            return 0
        added = 0
        for raw in found:
            if added >= remaining:
                break
            job = _job_from(source, raw)
            key = _url_key(job.url)
            if not job.url or not job.title or key in seen:
                continue
            seen.add(key)
            jobs.append(job.model_copy(update={"id": f"j{len(jobs) + 1}"}))
            added += 1
        budget[board_id] -= added
        step.note = f"{added} new"
        status(f"{label}: {_plural(len(found), 'job')}")
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
        status(f"Browsing BuiltInNYC companies in {_short(', '.join(q.industries) or 'all')}")
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


# -------------------------------------------------------------------- rank_companies


def _jobs_table(jobs: list[Job]) -> str:
    rows = [
        {
            "id": j.id,
            "source": j.source,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "salary": j.salary,
            "summary": _short(j.summary, 160),
            "url": j.url if not j.company else "",
        }
        for j in jobs
    ]
    return "\n".join(
        json.dumps({k: v for k, v in r.items() if v}, ensure_ascii=False) for r in rows
    )


def validate_ranking(
    ranking: CompanyRanking,
    jobs: list[Job],
    listed: list[ListedCompany],
    max_companies: int,
) -> tuple[list[ChosenCompany], list[str]]:
    """Keep only companies and job ids that exist in the gathered data; sort by score.

    A job id must exist and, if the job names its company, match the pick. A pick needs at
    least one valid job or a name that appears in the data. The data's spelling wins.
    Returns the chosen companies (best first) and what was dropped.
    """
    by_id = {j.id: j for j in jobs}
    known: dict[str, dict[str, str]] = {}
    for j in jobs:
        if j.company:
            known.setdefault(_name_key(j.company), {"name": j.company, "url": j.company_url})
    for c in listed:
        entry = known.setdefault(_name_key(c.name), {"name": c.name, "url": c.url})
        entry["url"] = entry["url"] or c.url
        entry["about"] = c.about

    chosen: dict[str, ChosenCompany] = {}
    dropped: list[str] = []
    for pick in ranking.companies:
        key = _name_key(pick.name)
        if not key:
            continue
        picked: list[Job] = []
        scores: dict[str, int] = {}
        for js in pick.jobs:
            job = by_id.get(js.id.strip())
            if job is None or (job.company and _name_key(job.company) != key):
                dropped.append(f"{pick.name}: job {js.id}")
                continue
            if job.id not in scores:
                picked.append(job)
                scores[job.id] = _scored(js.score)
        info = known.get(key)
        if info is None and not picked:
            dropped.append(f"{pick.name}: not in the data")
            continue
        if key in chosen:
            dropped.append(f"{pick.name}: duplicate")
            continue
        picked.sort(key=lambda j: -scores[j.id])
        keywords = [k.strip() for k in pick.people_keywords if k.strip()]
        chosen[key] = ChosenCompany(
            name=info["name"] if info else pick.name.strip(),
            url=(info or {}).get("url") or "",
            about=(info or {}).get("about") or "",
            score=_scored(pick.score),
            reason=pick.reason,
            jobs=picked[:MAX_JOBS_PER_COMPANY],
            job_scores=scores,
            people_keywords=keywords[:MAX_PEOPLE_KEYWORDS],
        )
    # The LLM's score decides; the number of relevant jobs breaks ties.
    ranked = sorted(chosen.values(), key=lambda c: (-c.score, -len(c.jobs)))
    return ranked[:max_companies], dropped


def default_ranking(
    jobs: list[Job], listed: list[ListedCompany], plan: SearchPlan, max_companies: int
) -> list[ChosenCompany]:
    """Used when the ranking call fails: companies with the most postings first."""
    groups: dict[str, list[Job]] = {}
    for j in jobs:
        if j.company:
            groups.setdefault(_name_key(j.company), []).append(j)
    keywords = [*plan.role_titles[:1], "recruiter"]
    chosen = [
        ChosenCompany(
            name=group[0].company,
            url=group[0].company_url,
            score=min(80, 40 + 10 * len(group)),
            reason="Ranked by number of matching postings.",
            jobs=group[:MAX_JOBS_PER_COMPANY],
            job_scores={j.id: 50 for j in group},
            people_keywords=keywords,
        )
        for group in sorted(groups.values(), key=len, reverse=True)
    ]
    if not chosen:
        chosen = [
            ChosenCompany(name=c.name, url=c.url, about=c.about, score=40, people_keywords=keywords)
            for c in listed
        ]
    return chosen[:max_companies]


def rank_companies_node(state: PipelineState, llm: BaseChatModel) -> dict:
    jobs, listed, plan = state["jobs"], state["listed_companies"], state["plan"]
    status(f"Ranking companies from {_plural(len(jobs), 'job')}")
    parts = [
        format_profile(state["request"]),
        f"<plan>\nRoles: {', '.join(plan.role_titles)}\nSeniority: {plan.seniority}\n"
        f"Industries: {', '.join(plan.industries)}\nLocation: {plan.location}\n</plan>",
        f"<jobs>\n{_jobs_table(jobs)}\n</jobs>",
    ]
    if listed:
        rows = [{"name": c.name, "about": _short(c.about, 160)} for c in listed]
        parts.append(f"<companies>\n{dump(rows)}\n</companies>")
    ranking, trace = call(
        "rank_companies",
        "llm",
        {"jobs": len(jobs), "listed_companies": len(listed)},
        lambda: structured(
            llm, CompanyRanking, prompts.rank_prompt(), "\n\n".join(parts), "rank_companies"
        ),
    )
    steps = [trace]
    chosen: list[ChosenCompany] = []
    if ranking is not None:
        chosen, dropped = validate_ranking(ranking, jobs, listed, config.MAX_COMPANIES)
        trace.count = len(ranking.companies)
        steps.append(
            TraceStep(
                step="rank_companies",
                source="validate",
                args={"dropped": dropped},
                count=len(chosen),
            )
        )
    if not chosen:
        chosen = default_ranking(jobs, listed, plan, config.MAX_COMPANIES)
        steps.append(
            TraceStep(
                step="rank_companies",
                source="validate",
                count=len(chosen),
                note="fallback: ranked by number of postings",
            )
        )
    if not chosen:
        return {
            "chosen": [],
            "error": "No companies could be chosen from the jobs found.",
            "trace": steps,
        }
    status("Top companies: " + ", ".join(f"{c.name} ({c.score})" for c in chosen))
    return {"chosen": chosen, "trace": steps}


# ----------------------------------------------------------------------- find_people


def ladder(keywords: Iterable[str], location: str) -> list[tuple[str, str]]:
    """The people-search fallback ladder: planned keywords, then "recruiter", then the
    company name only (no keywords, no location)."""
    rungs = [(k.strip(), location) for k in keywords if k.strip()]
    rungs += [("recruiter", location), ("", "")]
    unique: list[tuple[str, str]] = []
    for rung in rungs:
        if (rung[0].lower(), rung[1].lower()) not in {
            (k.lower(), loc.lower()) for k, loc in unique
        }:
            unique.append(rung)
    return unique


def similar_ladder(
    keywords: Iterable[str], location: str, max_queries: int
) -> list[tuple[str, str]]:
    """The similar-background relaxation ladder, at most `max_queries` rungs, each one
    also requiring the user's school: the first planned keywords and the location, then
    the company and location only, then the company only (no keywords, no location)."""
    first = next((k.strip() for k in keywords if k.strip()), "")
    rungs: list[tuple[str, str]] = []
    for rung in [(first, location), ("", location), ("", "")]:
        if rung not in rungs:
            rungs.append(rung)
    return rungs[: max(0, max_queries)]


def search_similar_people(
    company: str,
    education: Iterable[str],
    keywords: Iterable[str],
    location: str,
    step: str,
    people: list[Person],
    seen: set[str],
) -> list[TraceStep]:
    """Find people at `company` who share the user's school, merging them into `people`.

    Searches for the user's first school only, climbing `similar_ladder` until
    `PEOPLE_SIMILAR_PER_COMPANY` people with a visible shared school were found, and never
    running more than `PEOPLE_SIMILAR_MAX_QUERIES` Google searches. A person already in
    `people` (by profile URL) is not added again, but is marked if the result shows the
    school. Skipped (no query) when the user has no school or the knob is 0.
    """
    schools = clean_schools(education)
    rungs = similar_ladder(keywords, location, config.PEOPLE_SIMILAR_MAX_QUERIES)
    if not schools or not rungs:
        return []
    school = schools[0]
    label = f"Same school: {school}"
    by_key = {_url_key(p.url): p for p in people}
    trace: list[TraceStep] = []
    for words, where in rungs:
        status(f"Looking for {school} alumni at {company}")
        args = {"company": company, "keywords": words, "location": where, "school": school}
        found, rung = call(
            step,
            "linkedin_people",
            args,
            lambda w=words, loc=where: tools.linkedin_people(
                company, w, loc, n=config.PEOPLE_SEARCH_N, school=school
            ),
        )
        trace.append(rung)
        for raw in found or []:
            if not raw.get("url"):
                continue
            key = _url_key(raw["url"])
            shared = bool(raw.get("at_company")) and linkedin.mentions_school(raw, school)
            person = by_key.get(key)
            if person is None and key in seen:
                continue  # already known (e.g. saved earlier): don't add it again
            if person is None:
                person = Person.model_validate({**raw, "keywords": words})
                by_key[key] = person
                seen.add(key)
                people.append(person)
            if shared and not person.shared_background:
                person.shared_background = label
        shared_count = sum(bool(p.shared_background) for p in people)
        rung.note = f"similar background: {shared_count} people with a shared school so far"
        if shared_count >= config.PEOPLE_SIMILAR_PER_COMPANY:
            break
    return trace


def search_people(
    company: str,
    keywords: Iterable[str],
    location: str,
    step: str = "find_people",
    known_urls: Iterable[str] = (),
    education: Iterable[str] = (),
) -> tuple[list[Person], list[TraceStep]]:
    """Climb the ladder until `PEOPLE_PER_COMPANY` new current employees are found, then
    search for people with the user's school (`education`), if they have one.

    Every rung is a trace step; an error on one rung is recorded and the next one runs.
    People already in `known_urls` (or found by an earlier rung) are skipped.
    """
    keywords = list(keywords)
    seen = {_url_key(u) for u in known_urls}
    people: list[Person] = []
    trace: list[TraceStep] = []
    for words, where in ladder(keywords, location):
        status(f"Looking for {words or 'anyone'} at {company}")
        args = {"company": company, "keywords": words, "location": where}
        found, rung = call(
            step,
            "linkedin_people",
            args,
            lambda w=words, loc=where: tools.linkedin_people(
                company, w, loc, n=config.PEOPLE_SEARCH_N
            ),
        )
        trace.append(rung)
        for raw in found or []:
            key = _url_key(raw.get("url") or "")
            if not raw.get("url") or key in seen:
                continue
            seen.add(key)
            people.append(Person.model_validate({**raw, "keywords": words}))
        current = sum(p.at_company for p in people)
        rung.note = f"{current} current employees so far"
        if current >= config.PEOPLE_PER_COMPANY:
            break
    trace += search_similar_people(company, education, keywords, location, step, people, seen)
    return people, trace


QUERY_MAX_SEARCHES = 3
"""Most Google searches for one `search_people_by_query` call."""


def search_people_by_query(
    company: str,
    keywords: Iterable[str],
    location: str,
    school: str,
    step: str,
    known_urls: Iterable[str] = (),
) -> tuple[list[Person], list[TraceStep]]:
    """People at `company` for given search terms (the people pane's "only people from my
    school" search).

    One search per keyword phrase (or one with no keywords), then, while fewer than
    `PEOPLE_PER_COMPANY` current employees were found, the first one again without the
    location. At most `QUERY_MAX_SEARCHES` searches. With `school`, people whose result
    shows it are marked `shared_background`. Profiles in `known_urls` are skipped.
    """
    phrases = [k.strip() for k in keywords if k.strip()] or [""]
    rungs = [(words, location) for words in phrases]
    if location:
        rungs.append((phrases[0], ""))
    rungs = list(dict.fromkeys(rungs))[:QUERY_MAX_SEARCHES]
    label = f"Same school: {school}" if school else ""
    seen = {_url_key(u) for u in known_urls}
    people: list[Person] = []
    trace: list[TraceStep] = []
    for i, (words, where) in enumerate(rungs):
        if i >= len(phrases) and sum(p.at_company for p in people) >= config.PEOPLE_PER_COMPANY:
            break  # the relaxed (no location) rung only runs when too few were found
        status(f"Looking for {words or 'people'}{f' from {school}' if school else ''} at {company}")
        args = {"company": company, "keywords": words, "location": where}
        if school:
            args["school"] = school
        found, rung = call(
            step,
            "linkedin_people",
            args,
            lambda w=words, loc=where: tools.linkedin_people(
                company, w, loc, n=config.PEOPLE_SEARCH_N, school=school
            ),
        )
        trace.append(rung)
        for raw in found or []:
            key = _url_key(raw.get("url") or "")
            if not raw.get("url") or key in seen:
                continue
            seen.add(key)
            person = Person.model_validate({**raw, "keywords": words})
            if school and person.at_company and linkedin.mentions_school(raw, school):
                person.shared_background = label
            people.append(person)
        rung.note = f"{sum(p.at_company for p in people)} current employees so far"
    return people, trace


def find_people_node(state: PipelineState) -> dict:
    """People search for every one of the top `PEOPLE_AUTO_COMPANIES` companies."""
    location = state["plan"].people_location
    people: dict[str, list[Person]] = {}
    trace: list[TraceStep] = []
    for company in state["chosen"][: config.PEOPLE_AUTO_COMPANIES]:
        found, steps = search_people(
            company.name,
            company.people_keywords,
            location,
            education=state["request"].education,
        )
        people[company.name] = found
        trace += steps
        current = sum(p.at_company for p in found)
        similar = sum(bool(p.shared_background) for p in found)
        extra = f" ({similar} with a shared school)" if similar else ""
        status(f"{company.name}: {_plural(current, 'current employee')} found{extra}")
    return {"people": people, "trace": trace}


# --------------------------------------------------------------------- read_postings


def read_postings_node(state: PipelineState) -> dict:
    """read_page on the best posting of the top companies (`READ_POSTINGS` of them)."""
    postings: dict[str, str] = {}
    trace: list[TraceStep] = []
    urls = [c.jobs[0].url for c in state["chosen"] if c.jobs][: config.READ_POSTINGS]
    for url in urls:
        status(f"Reading {_short(url.split('://', 1)[-1].removeprefix('www.'))}")
        page, step = call(
            "read_postings",
            "read_page",
            {"url": url},
            lambda u=url: tools.read_page(u, max_chars=config.READ_POSTING_MAX_CHARS),
        )
        trace.append(step)
        if page is not None:
            postings[url] = page.markdown
            step.count = len(page.markdown)
            step.note = "count = characters"
    return {"postings": postings, "trace": trace}


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
    by_url = {_url_key(j.url): j for j in company.jobs}
    by_title = {normalize_text(j.title): j for j in company.jobs}
    kept: dict[str, JobResult] = {}
    for job in written:
        found = by_url.get(_url_key(job.url)) or by_title.get(normalize_text(job.title))
        if found is not None and found.id not in kept:
            score = company.job_scores.get(found.id)
            kept[found.id] = job.model_copy(update={"url": found.url, "score": score})
    return sorted(kept.values(), key=lambda j: -(j.score or 0))


def match_people(written: list[PersonResult], found: list[Person]) -> list[PersonResult]:
    """`written` people that were found (by profile URL, else name), with the found URL."""
    by_url = {_url_key(p.url): p for p in found}
    by_name = {normalize_text(p.name): p for p in found}
    kept: dict[str, PersonResult] = {}
    for person in written:
        match = by_url.get(_url_key(person.profile_url)) or by_name.get(normalize_text(person.name))
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
    by_name = {_name_key(c.name): c for c in chosen}
    out: dict[str, CompanyResult] = {}
    counts = {"companies_dropped": 0, "jobs_dropped": 0, "people_dropped": 0, "companies_added": 0}
    for company in results.companies:
        key = _name_key(company.name)
        c = by_name.get(key)
        if c is None or key in out:
            counts["companies_dropped"] += 1
            continue
        found = people.get(c.name)
        jobs = match_jobs(company.jobs, c)
        persons = match_people(company.people, found or [])
        counts["jobs_dropped"] += len(company.jobs) - len(jobs)
        counts["people_dropped"] += len(company.people) - len(persons)
        allowed = {_url_key(u) for u in [c.url, *(j.url for j in c.jobs)] if u}
        url = company.url if _url_key(company.url) in allowed else ""
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
