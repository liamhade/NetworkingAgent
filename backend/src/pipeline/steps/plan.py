"""The `plan` node: profile to role titles and board queries."""

import logging
from typing import TypeVar

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

import ats
import config
import prompts
from boards import on_boards
from pipeline.state import (
    PipelineState,
    SearchPlan,
    UsajobsQuery,
)
from pipeline.steps.common import call, format_profile, short, status, structured
from schemas import (
    SearchRequest,
)

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


MAX_JOB_QUERIES = 3
MAX_GOOGLE_QUERIES = 2
MAX_ATS_QUERIES = 2
MIN_JOBS_BEFORE_GOOGLE = 5
"""Fewer jobs than this from the planned sources (and no Google query planned) adds one."""

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
    role = plan.role_titles[0] if plan.role_titles else short(request.looking_for, 50)
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
