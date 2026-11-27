"""The `rank_companies` node."""

import json
import logging
from typing import TypeVar

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

import config
import prompts
from pipeline.state import (
    ChosenCompany,
    CompanyRanking,
    Job,
    ListedCompany,
    PipelineState,
    SearchPlan,
)
from pipeline.steps.common import (
    call,
    dump,
    format_profile,
    name_key,
    plural,
    scored,
    short,
    status,
    structured,
)
from schemas import (
    TraceStep,
)

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_JOBS_PER_COMPANY = 4
MAX_PEOPLE_KEYWORDS = 2


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
            "level": j.level,
            "years_required": j.years_required,
            "summary": short(j.summary, 160),
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
            known.setdefault(name_key(j.company), {"name": j.company, "url": j.company_url})
    for c in listed:
        entry = known.setdefault(name_key(c.name), {"name": c.name, "url": c.url})
        entry["url"] = entry["url"] or c.url
        entry["about"] = c.about

    chosen: dict[str, ChosenCompany] = {}
    dropped: list[str] = []
    for pick in ranking.companies:
        key = name_key(pick.name)
        if not key:
            continue
        picked: list[Job] = []
        scores: dict[str, int] = {}
        for js in pick.jobs:
            job = by_id.get(js.id.strip())
            if job is None or (job.company and name_key(job.company) != key):
                dropped.append(f"{pick.name}: job {js.id}")
                continue
            if job.id not in scores:
                picked.append(job)
                scores[job.id] = scored(js.score)
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
            score=scored(pick.score),
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
            groups.setdefault(name_key(j.company), []).append(j)
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
    status(f"Ranking companies from {plural(len(jobs), 'job')}")
    parts = [
        format_profile(state["request"]),
        f"<plan>\nRoles: {', '.join(plan.role_titles)}\nSeniority: {plan.seniority}\n"
        f"Industries: {', '.join(plan.industries)}\nLocation: {plan.location}\n</plan>",
        f"<jobs>\n{_jobs_table(jobs)}\n</jobs>",
    ]
    if listed:
        rows = [{"name": c.name, "about": short(c.about, 160)} for c in listed]
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
