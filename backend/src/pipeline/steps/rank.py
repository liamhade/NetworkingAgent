"""The `rank_jobs` node: one structured-output call over compact cards of the completed jobs."""

import json
import logging
from urllib.parse import urlsplit

from langchain_core.language_models import BaseChatModel

import config
import prompts
from pipeline.state import (
    ChosenCompany,
    JobPosting,
    JobRank,
    JobRanking,
    ListedCompany,
    PipelineState,
    RankedJob,
    SearchPlan,
)
from pipeline.steps.common import (
    call,
    format_profile,
    name_key,
    plural,
    scored,
    status,
    structured,
)
from schemas import TraceStep

log = logging.getLogger(__name__)

MAX_PEOPLE_KEYWORDS = 2
CARD_REQUIREMENTS_CHARS = 700
"""Characters of a posting's requirements excerpt on its card (about 250 tokens per card)."""


def _excerpt(text: str, limit: int) -> str:
    """At most `limit` characters, cut at a word boundary with an ellipsis."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    return (cut.rsplit(" ", 1)[0] if " " in cut[limit // 2 :] else cut).rstrip(" ,;:-") + "…"


def job_card(job: JobPosting) -> str:
    """One compact JSON line per job: what the ranker judges it by."""
    card = {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "salary": job.salary,
        "years_required": job.years_required,
        "level": job.level,
        "requirements": _excerpt(job.requirements or job.summary, CARD_REQUIREMENTS_CHARS),
        "url": job.url if not job.company else "",
    }
    return json.dumps({k: v for k, v in card.items() if v}, ensure_ascii=False)


def _employer(job: JobPosting, named: str = "") -> str:
    """The job's company; else the one the ranker named; else the posting's site."""
    return (
        job.company.strip()
        or named.strip()
        or urlsplit(job.url).netloc.removeprefix("www.")
        or "Unknown employer"
    )


def validate_ranking(
    ranking: JobRanking, jobs: list[JobPosting], max_jobs: int
) -> tuple[list[RankedJob], dict[str, list[str]], list[str]]:
    """Keep only job ids that exist, once each, best score first (the ranker's order breaks
    ties), at most `max_jobs`. Returns the ranked jobs, people keywords by company name key
    and what was dropped. No cap per company."""
    by_id = {j.id: j for j in jobs}
    picked: dict[str, tuple[int, int, JobRank]] = {}
    dropped: list[str] = []
    for position, entry in enumerate(ranking.jobs):
        job_id = entry.id.strip()
        if job_id not in by_id:
            dropped.append(f"{job_id}: not a gathered job")
        elif job_id in picked:
            dropped.append(f"{job_id}: duplicate")
        else:
            picked[job_id] = (scored(entry.score), position, entry)
    order = sorted(picked.values(), key=lambda item: (-item[0], item[1]))
    ranked: list[RankedJob] = []
    for score, _, entry in order[:max_jobs]:
        job = by_id[entry.id.strip()]
        updates = {"company": _employer(job, entry.company)}
        years = entry.years_required.strip()
        if years:
            updates["years_required"] = years
        ranked.append(
            RankedJob(
                job=job.model_copy(update=updates),
                rank=len(ranked) + 1,
                score=score,
                reason=entry.reason.strip(),
                alignment=entry.alignment.strip() or entry.reason.strip(),
                years_required=updates.get("years_required", job.years_required),
            )
        )
    dropped += [f"{e.id.strip()}: over the limit of {max_jobs}" for _, _, e in order[max_jobs:]]
    keywords: dict[str, list[str]] = {}
    for company in ranking.companies:
        words = [k.strip() for k in company.people_keywords if k.strip()]
        keywords.setdefault(name_key(company.company), words[:MAX_PEOPLE_KEYWORDS])
    return ranked, keywords, dropped


def default_ranking(jobs: list[JobPosting], max_jobs: int) -> list[RankedJob]:
    """Used when the ranking call fails: the filter's order, every job at a neutral score."""
    return [
        RankedJob(
            job=job.model_copy(update={"company": _employer(job)}),
            rank=i,
            score=50,
            reason="Not scored: the ranking call failed.",
            years_required=job.years_required,
        )
        for i, job in enumerate(jobs[:max_jobs], start=1)
    ]


def build_chosen(
    ranked: list[RankedJob],
    keywords: dict[str, list[str]],
    listed: list[ListedCompany],
    plan: SearchPlan,
) -> list[ChosenCompany]:
    """Companies in the order of their best job; `score` is that job's score."""
    about = {name_key(c.name): c for c in listed}
    default = [*plan.role_titles[:1], "recruiter"]
    groups: dict[str, ChosenCompany] = {}
    for item in ranked:
        key = name_key(item.job.company)
        company = groups.get(key)
        if company is None:
            info = about.get(key)
            company = groups[key] = ChosenCompany(
                name=item.job.company,
                url=item.job.company_url or (info.url if info else ""),
                about=info.about if info else "",
                score=item.score,
                reason=item.reason,
                people_keywords=keywords.get(key) or default,
            )
        company.jobs.append(item)
    return list(groups.values())


def rank_jobs_node(state: PipelineState, llm: BaseChatModel) -> dict:
    jobs, plan = state["postings"], state["plan"]
    status(f"Ranking {plural(len(jobs), 'job')}")
    parts = [
        format_profile(state["request"]),
        f"<plan>\nRoles: {', '.join(plan.role_titles)}\nSeniority: {plan.seniority}\n"
        f"Industries: {', '.join(plan.industries)}\nLocation: {plan.location}\n</plan>",
        "<jobs>\n" + "\n".join(job_card(j) for j in jobs) + "\n</jobs>",
    ]
    ranking, trace = call(
        "rank_jobs",
        "llm",
        {"jobs": len(jobs), "model": config.RANK_MODEL},
        lambda: structured(
            llm, JobRanking, prompts.rank_jobs_prompt(), "\n\n".join(parts), "rank_jobs"
        ),
    )
    steps = [trace]
    ranked: list[RankedJob] = []
    keywords: dict[str, list[str]] = {}
    if ranking is not None:
        ranked, keywords, dropped = validate_ranking(ranking, jobs, config.MAX_JOBS)
        trace.count = len(ranking.jobs)
        steps.append(
            TraceStep(
                step="rank_jobs", source="validate", args={"dropped": dropped}, count=len(ranked)
            )
        )
    if not ranked:
        ranked = default_ranking(jobs, config.MAX_JOBS)
        steps.append(
            TraceStep(
                step="rank_jobs",
                source="validate",
                count=len(ranked),
                note="fallback: the filter's order, not scored",
            )
        )
    chosen = build_chosen(ranked, keywords, state.get("listed_companies", []), plan)
    status("Top jobs: " + ", ".join(f"{r.job.title} ({r.score})" for r in ranked[:3]))
    return {"ranked": ranked, "chosen": chosen, "trace": steps}
