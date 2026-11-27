# pipeline

The search is a fixed LangGraph `StateGraph`, not a free-form tool-calling agent:
`plan → find_jobs → filter → rank_jobs → find_people → compile`
The LLM decides *what* to search for, *how well* each job fits (0-100) and writes the text;
code decides *that* every step runs. Rank design: `docs/job-ranking/plan.md`; trace format
and tradeoffs: `docs/langgraph-pipeline/plan.md` (its node list predates the job ranking).

| Node | Kind | Reads | Writes |
|---|---|---|---|
| `plan` | LLM (`LLM_MODEL`), `SearchPlan` | `request` | `plan` |
| `find_jobs` | code, parallel board calls | `request`, `plan` | `jobs`, `listed_companies` |
| `filter` | code: dedupe (URL, or company + title + location), location, years (`background.user_years`), cap `RANK_MAX_JOBS`, then `complete_jobs` reads the postings and a second years cut | `jobs` | `postings`; ends the graph with `error`, or with empty `results` when only listed companies remain |
| `rank_jobs` | LLM (`RANK_MODEL`), `JobRanking` over compact cards, top `MAX_JOBS`, no per-company cap; alignment notes only for those top jobs | `postings` | `ranked`, `chosen` |
| `find_people` | code, parallel LinkedIn searches for the first `PEOPLE_AUTO_COMPANIES` companies | `chosen` | `people` |
| `compile` | LLM (`LLM_MODEL`), slim `CompileNotes`: company descriptions, people notes, LinkedIn messages; code builds the rest | `ranked`, `chosen`, `people` | `results` |

State keys (`state.py`, `PipelineState`): `request`, `plan`, `jobs`, `listed_companies`,
`postings`, `ranked`, `chosen`, `people`, `results`, `error`, `trace`.

## Layout

- `graph.py`: builds the graph; `run_search()` yields the status/result/error event stream
- `steps/`: one module per node (`plan`, `find_jobs`, `filter`, `rank`, `people`, `compile`), `common` (shared helpers) and `reading` (parallel page reads); `steps/__init__.py` re-exports everything as `steps.<name>`
- `steps/complete.py`: `complete_jobs(jobs, max_reads)` turns `Job`s into `JobPosting`s (full text, `text_source`); called by `filter`
- `backend/src/postings/` (the postings service): `reader_for(url)` picks the reader for a posting URL: Greenhouse, Lever and Ashby per-posting APIs (`text_source=api`), BuiltInNYC and Workable page parsers (`parser`), else the generic `read_page` (`page`); a failed or timed-out read keeps the card text (`none`). `READ_TIMEOUT_S` bounds a batch of reads
- `state.py`: typed graph state and the structured-output models of the LLM steps
- `on_demand.py`: the "Find People To Connect With" flow behind
  `POST /api/searches/{search_id}/people`

## Rules

- Prompts live in `backend/src/prompts.py`, not here: `RANK_JOBS_PROMPT` (`rank_jobs_prompt()`), `COMPILE_PROMPT`, `PEOPLE_NOTES_PROMPT`, `LINKEDIN_MESSAGE_PROMPT` and the plan prompts.
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
- Tests use mocked LLMs and sources only (`backend/tests/pipeline_fakes.py`). To test one node,
  build a `PipelineState` dict and call `steps.<node>_node(state[, llm])` with a fake LLM
  (`test_filter.py`, `test_rank_jobs.py`, `backend/tests/postings/`); run the whole graph with
  `run_search(request, llm)` (`test_pipeline.py`). Run `cd backend; .venv/Scripts/python -m pytest -q`.
