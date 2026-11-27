"""The search pipeline: a fixed LangGraph graph instead of a free-form tool-calling agent.

- `run_search(request)`: plan -> find_jobs -> filter -> rank_jobs ->
  find_people (companies of the top jobs) -> compile, streamed as `StatusEvent`s, then
  `TraceEvent` and `ResultEvent` (or one `ErrorEvent`). See `graph.py`.
- `find_people(user_id, search_id, company_key, job_key)`: the on-demand people search for
  one company of a saved search. See `on_demand.py`.

Nodes and shared helpers are in the `steps/` package, the typed state and LLM schemas in `state.py`.
Plan: `docs/langgraph-pipeline/plan.md`.
"""

from pipeline.graph import build_graph, run_search
from pipeline.on_demand import NoSchool, NotFound, find_people

__all__ = ["NoSchool", "NotFound", "build_graph", "find_people", "run_search"]
