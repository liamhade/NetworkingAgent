"""The experimental `rescore_jobs` node."""

import logging
from typing import TypeVar

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

import config
import prompts
from pipeline.state import (
    ChosenCompany,
    Job,
    PipelineState,
    Rescoring,
)
from pipeline.steps.common import (
    call,
    dump,
    format_profile,
    name_key,
    plural,
    scored,
    status,
    structured,
)
from pipeline.steps.reading import posting_excerpt, read_pages

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _rescore_targets(chosen: list[ChosenCompany], per_company: int) -> list[Job]:
    return [job for c in chosen for job in c.jobs[:per_company] if job.url]


def apply_rescoring(chosen: list[ChosenCompany], rescoring: Rescoring) -> list[ChosenCompany]:
    """New job and company scores from `rescoring`, for the companies and job ids that exist;
    jobs re-sorted within each company and companies re-sorted by score."""
    by_name = {name_key(c.name): c for c in rescoring.companies}
    out = []
    for company in chosen:
        new = by_name.get(name_key(company.name))
        if new is None:
            out.append(company)
            continue
        known = {j.id for j in company.jobs}
        scores = dict(company.job_scores)
        years = {}
        for js in new.jobs:
            if js.id in known:
                scores[js.id] = scored(js.score)
                years[js.id] = js.years_required.strip()
        jobs = [
            j.model_copy(update={"years_required": years[j.id]}) if years.get(j.id) else j
            for j in company.jobs
        ]
        jobs.sort(key=lambda j: -scores.get(j.id, 0))
        out.append(
            company.model_copy(
                update={"score": scored(new.score), "jobs": jobs, "job_scores": scores}
            )
        )
    out.sort(key=lambda c: (-c.score, -len(c.jobs)))
    return out


def rescore_jobs_node(state: PipelineState, llm: BaseChatModel) -> dict:
    """Experimental (`config.RESCORE_POSTINGS` > 0): read the top postings of every chosen
    company in full, then score them again with their requirements in view."""
    per_company = config.RESCORE_POSTINGS
    chosen = state["chosen"]
    targets = _rescore_targets(chosen, per_company) if per_company else []
    if not targets:
        return {}
    status(f"Reading {plural(len(targets), 'posting')} to check requirements")
    max_chars = max(config.RESCORE_POSTING_MAX_CHARS, config.READ_POSTING_MAX_CHARS)

    postings, trace = read_pages("rescore_jobs", [j.url for j in targets], max_chars)
    if not postings:
        return {"trace": trace}

    blocks = []
    for company in chosen:
        jobs = [
            {
                "id": j.id,
                "title": j.title,
                "current_score": company.job_scores.get(j.id),
                "posting": posting_excerpt(postings[j.url], config.RESCORE_POSTING_MAX_CHARS),
            }
            for j in company.jobs[:per_company]
            if j.url in postings
        ]
        if jobs:
            head = {"name": company.name, "current_score": company.score}
            blocks.append(dump({**head, "jobs": jobs}))
    human = (
        f"{format_profile(state['request'])}\n\n<companies>\n"
        + "\n".join(blocks)
        + "\n</companies>"
    )
    status("Re-checking fit against the full postings")
    rescoring, step = call(
        "rescore_jobs",
        "llm",
        {"postings": len(postings)},
        lambda: structured(llm, Rescoring, prompts.RESCORE_PROMPT, human, "rescore_jobs"),
    )
    trace.append(step)
    if rescoring is None:
        return {"postings": postings, "trace": trace}
    rescored = apply_rescoring(chosen, rescoring)
    status("Top companies: " + ", ".join(f"{c.name} ({c.score})" for c in rescored))
    return {"chosen": rescored, "postings": postings, "trace": trace}
