"""The search as a fixed LangGraph graph, and `run_search()`, which streams its events.

    plan -> find_jobs -> rank_companies -> find_people -> read_postings -> compile

`plan`, `rank_companies` and `compile` are structured-output LLM calls; the rest is code,
so every step runs. A node that finds nothing usable sets `error` and the graph ends.
See `docs/langgraph-pipeline/plan.md`.
"""

import logging
from collections.abc import Callable, Iterator

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from llm import get_llm
from pipeline import steps
from pipeline.state import PipelineState
from schemas import AgentEvent, ErrorEvent, ResultEvent, SearchRequest, StatusEvent, TraceEvent

log = logging.getLogger(__name__)


def _next_unless_error(target: str) -> Callable[[PipelineState], str]:
    return lambda state: END if state.get("error") else target


def build_graph(llm: BaseChatModel):
    graph = StateGraph(PipelineState)
    graph.add_node("plan", lambda state: steps.plan_node(state, llm))
    graph.add_node("find_jobs", steps.find_jobs_node)
    graph.add_node("rank_companies", lambda state: steps.rank_companies_node(state, llm))
    graph.add_node("find_people", steps.find_people_node)
    graph.add_node("read_postings", steps.read_postings_node)
    graph.add_node("compile", lambda state: steps.compile_node(state, llm))

    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", _next_unless_error("find_jobs"), ["find_jobs", END])
    graph.add_conditional_edges(
        "find_jobs", _next_unless_error("rank_companies"), ["rank_companies", END]
    )
    graph.add_conditional_edges(
        "rank_companies", _next_unless_error("find_people"), ["find_people", END]
    )
    graph.add_edge("find_people", "read_postings")
    graph.add_edge("read_postings", "compile")
    graph.add_edge("compile", END)
    return graph.compile()


def run_search(request: SearchRequest, llm: BaseChatModel | None = None) -> Iterator[AgentEvent]:
    """Run the pipeline for `request`, yielding progress, then the trace and the results.

    Yields `StatusEvent`s while it runs, then `TraceEvent` + `ResultEvent`, or a single
    `ErrorEvent` if nothing usable was found.
    """
    graph = build_graph(llm or get_llm())
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
