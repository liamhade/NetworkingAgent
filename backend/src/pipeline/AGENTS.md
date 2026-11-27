# pipeline

The search is a fixed LangGraph `StateGraph`, not a free-form tool-calling agent:
`plan → find_jobs → filter → rank_jobs → find_people → compile`
(`filter` is code: dedupe, location, experience, cap, then reads the postings; `rank_jobs`
scores jobs on `RANK_MODEL`; `compile` only writes people notes and company descriptions, and code assembles the results; see `docs/job-ranking/plan.md`). The LLM decides
*what* to search for, *how well* jobs fit (0-100 score) and writes the text; code decides
*that* every step runs. Design, trace format and tradeoffs:
`docs/langgraph-pipeline/plan.md`.

## Layout

- `graph.py`: builds the graph; `run_search()` yields the status/result/error event stream
- `steps/`: one module per node (`plan`, `find_jobs`, `filter`, `rank`, `people`, `compile`), `common` (shared helpers) and `reading` (parallel page reads); `steps/__init__.py` re-exports everything as `steps.<name>`
- `steps/complete.py`: `complete_jobs(jobs, max_reads)` turns `Job`s into `JobPosting`s (full text, `text_source`); called by `filter`. Site readers live in `backend/src/postings/`
- `state.py`: typed graph state and the structured-output models of the LLM steps
- `on_demand.py`: the "Find People To Connect With" flow behind
  `POST /api/searches/{search_id}/people`

## Rules

- Prompts live in `backend/src/prompts.py`, not here.
- Every LLM step uses `run_config("<purpose>")` so token usage is logged (purposes: `plan`,
  `rank_jobs`, `compile_results`, `find_people_on_demand`).
- Sources are called through the plain functions in `tools.py`. Google calls all queue in the
  one shared Chrome worker; never start a second browser for parallelism.
- `compile` (`CompileNotes`) is skipped when no company needs a description and nobody was found; job text, scores, links and the summary never come from it.
- Code, not the LLM, enforces what reaches the results: only gathered companies, jobs and
  people, with URLs copied from the gathered data.
- Every source call and validation is recorded in the search's `trace` (saved with the search,
  not streamed). Check it first when a result list is unexpectedly empty.
- Knobs are in `config.py`: `MAX_JOBS`, `RANK_MAX_JOBS`, `RANK_MODEL`, `PEOPLE_AUTO_COMPANIES`, `READ_TIMEOUT_S`,
  `PEOPLE_PER_COMPANY`, and for the shared-school people search `PEOPLE_SIMILAR_MAX_QUERIES`
  (extra Google searches per company; 0 turns it off) and `PEOPLE_SIMILAR_PER_COMPANY`.
- Tests use mocked LLMs and sources only (`backend/tests/pipeline_fakes.py`).
