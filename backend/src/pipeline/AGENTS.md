# pipeline

The search is a fixed LangGraph `StateGraph`, not a free-form tool-calling agent:
`plan → find_jobs → rank_companies → find_people → read_postings → compile`. The LLM decides
*what* to search for, *how well* companies fit (0-100 score) and writes the text; code decides
*that* every step runs. Design, trace format and tradeoffs:
`docs/langgraph-pipeline/plan.md`.

## Layout

- `graph.py`: builds the graph; `run_search()` yields the status/result/error event stream
- `steps.py`: one function per node, plus the people-search fallback ladder
- `state.py`: typed graph state and the structured-output models of the LLM steps
- `on_demand.py`: the "Find People To Connect With" flow behind
  `POST /api/searches/{search_id}/people`

## Rules

- Prompts live in `backend/src/prompts.py`, not here.
- Every LLM step uses `run_config("<purpose>")` so token usage is logged (purposes: `plan`,
  `rank_companies`, `compile_results`, `find_people_on_demand`).
- Sources are called through the plain functions in `tools.py`. Google calls all queue in the
  one shared Chrome worker; never start a second browser for parallelism.
- Code, not the LLM, enforces what reaches the results: only gathered companies, jobs and
  people, with URLs copied from the gathered data.
- Every source call and validation is recorded in the search's `trace` (saved with the search,
  not streamed). Check it first when a result list is unexpectedly empty.
- Knobs are in `config.py`: `MAX_COMPANIES`, `PEOPLE_AUTO_COMPANIES`, `READ_POSTINGS`,
  `PEOPLE_PER_COMPANY`, and for the shared-school people search `PEOPLE_SIMILAR_MAX_QUERIES`
  (extra Google searches per company; 0 turns it off) and `PEOPLE_SIMILAR_PER_COMPANY`.
- Tests use mocked LLMs and sources only (`backend/tests/pipeline_fakes.py`).
