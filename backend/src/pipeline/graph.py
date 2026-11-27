"""The search as a fixed LangGraph graph, and `run_search()`, which streams its events.

    plan -> find_jobs -> filter -> rank_jobs -> find_people -> compile

`plan`, `rank_jobs` and `compile` are structured-output LLM calls (`rank_jobs` on
`config.RANK_MODEL`); the rest is code, so every step runs. `filter` cuts the jobs found
and reads the postings of those that remain. A node that finds nothing usable sets `error`
and the graph ends. See `docs/langgraph-pipeline/plan.md` and `docs/job-ranking/plan.md`.
"""

import logging
from collections.abc import Callable, Iterator

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

import config
from llm import get_llm
from pipeline import steps
from pipeline.state import PipelineState
from schemas import AgentEvent, ErrorEvent, ResultEvent, SearchRequest, StatusEvent, TraceEvent

log = logging.getLogger(__name__)


def _next_unless_error(target: str) -> Callable[[PipelineState], str]:
    return lambda state: END if state.get("error") else target


def build_graph(llm: BaseChatModel, rank_llm: BaseChatModel | None = None):
    """The graph; `rank_llm` (default: `llm`) runs the `rank_jobs` step."""
    ranker = rank_llm or llm
    graph = StateGraph(PipelineState)
    graph.add_node("plan", lambda state: steps.plan_node(state, llm))
    graph.add_node("find_jobs", steps.find_jobs_node)
    graph.add_node("filter", steps.filter_node)
    graph.add_node("rank_jobs", lambda state: steps.rank_jobs_node(state, ranker))
    graph.add_node("find_people", steps.find_people_node)
    graph.add_node("compile", lambda state: steps.compile_node(state, llm))

    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", _next_unless_error("find_jobs"), ["find_jobs", END])
    graph.add_conditional_edges("find_jobs", _next_unless_error("filter"), ["filter", END])
    graph.add_conditional_edges("filter", _next_unless_error("rank_jobs"), ["rank_jobs", END])
    graph.add_edge("rank_jobs", "find_people")
    graph.add_edge("find_people", "compile")
    graph.add_edge("compile", END)
    return graph.compile()


def run_search(request: SearchRequest, llm: BaseChatModel | None = None) -> Iterator[AgentEvent]:
    """Run the pipeline for `request`, yielding progress, then the trace and the results.

    Yields `StatusEvent`s while it runs, then `TraceEvent` + `ResultEvent`, or a single
    `ErrorEvent` if nothing usable was found.
    """
    # An injected `llm` (tests) runs every step; otherwise ranking uses `RANK_MODEL`.
    if llm is None:
        graph = build_graph(get_llm(), get_llm(config.RANK_MODEL))
    else:
        graph = build_graph(llm)
    yield StatusEvent(message="Reading your profile")
    final: dict = {}
    try:
        for mode, chunk in graph.stream(
            {"request": request, "trace": []}, stream_mode=["custom", "values"]
        ):
            if mode == "custom":
                yield chunk
            else:
                final = chunk
    except Exception as exc:  # noqa: BLE001
        log.exception("Search pipeline failed")
        yield ErrorEvent(message=f"Search failed: {exc}")
        return

    trace = final.get("trace", [])
    if "results" not in final:
        log.info("Search ended without results: %s; trace: %s", final.get("error"), trace)
        yield ErrorEvent(message=final.get("error") or "Search failed.")
        return
    yield TraceEvent(steps=trace)
    yield ResultEvent(data=final["results"])
