# Search board configuration

Task: on the search page, a panel that lets the user choose which job boards a search uses
and how many jobs to gather from each. The bot still decides how to rank and sort.

## Decisions

- **Single source of truth.** New backend sub-package `backend/src/boards/` owns the board
  list (ids, labels, descriptions, defaults, min/max, availability). `GET /api/search/boards`
  serves it; the frontend renders from it and hard-codes no board.
- **One self-contained request object.** `SearchRequest.boards` is
  `{ "<board_id>": { "enabled": bool, "max_jobs": int } }`. It is normalised by a pydantic
  `before` validator (`boards.normalize`): unknown ids dropped, `max_jobs` clamped to the
  board's min/max (strings/floats coerced, junk falls back), missing or malformed entries and
  a missing `boards` get the board's default. After validation it always holds every catalog
  board, so it can be persisted or saved as a named "search configuration" as is.
- **History.** `history.save_search` already stores the whole `SearchRequest`, so the boards
  config is saved with every search. Older saved searches have no `boards` and load with the
  defaults of the day.
- **`enabled` is intent, availability is separate.** Every board defaults to `enabled: true`.
  `available` (USAJOBS needs `USAJOBS_API_KEY` + `USAJOBS_EMAIL`; the ATS providers need
  `ATS_MAX_BOARDS > 0`) is evaluated when the search runs (`boards.is_on` = enabled and
  available). An unavailable board never runs, and the panel shows it off and disabled with
  the reason ("Needs an API key (...)"). The frontend sends `enabled: false` for it.
- **No user-controlled sorting.** Ranking and ordering stay with `rank_companies` and
  `compile`; the panel only decides what is gathered.

## Boards

| id | label | default `max_jobs` | min-max | notes |
|---|---|---|---|---|
| `builtin_nyc` | Built In NYC | 45 | 1-100 | also gates `builtin_companies` |
| `conservation` | Conservation Job Board | 45 | 1-100 | |
| `greenhouse`, `lever`, `ashby`, `workable` | one each | 8 | 1-40 | per-provider allowance |
| `usajobs` | USAJOBS | 20 | 1-100 | needs API key |
| `google` | Google job searches | 20 | 1-50 | the planned `google_queries` and the fallback query |

Google job searches are a distinct source in `find_jobs` (`google_queries` plus the fallback
when fewer than 5 jobs were found), so they get their own board.

`max_jobs` means **the most jobs gathered from that board in one search, across all its
queries**. Defaults equal what the pipeline could gather before (3 queries x 15 for
BuiltIn / Conservation, 2 x 10 for Google, `USAJOBS_MAX_QUERIES` x `USAJOBS_RESULTS`), so the
default config reproduces today's behaviour. Test `test_defaults_match_todays_per_source_behaviour`
ties the defaults to the pipeline constants.

## Enforcement in code (`pipeline/steps.py`)

- **Plan prompt.** `prompts.plan_prompt(boards)` builds the prompt from per-source sections and
  includes only boards that are on (and, for USAJOBS, configured). The ATS paragraph lists
  only the enabled providers ("Greenhouse, Lever and Ashby").
- **`cap_plan`.** Drops the plan's queries for any board the user turned off, even if the LLM
  planned them (`turned_off_queries`). `plan_node` records
  `dropped queries for boards turned off: ...` as the plan trace step's note. The Google
  fallback query is only added when Google is on. If no board is on at all, `plan_node` ends
  the search with an error before calling the LLM.
- **`find_jobs`.** Does not rely on `cap_plan`: `_job_searches` only builds searches of boards
  that are on, so a disabled board is never queried. A `boards` trace step lists what was
  turned off. Each board has a budget (`budget[board_id] = max_jobs`). A query asks its tool
  for `min(per-query size, remaining)` jobs, no more than the remaining budget is kept
  (after de-duplication), and once a board is used up its remaining queries are skipped
  with a `skipped: <board> reached its limit of N` trace step. The Google fallback respects
  the Google toggle and budget. `builtin_companies` follows the Built In NYC toggle.
- **USAJOBS.** On + unconfigured keeps today's `skipped: ... not configured` trace note.

## ATS starvation fix

Before: one shared `ATS_MAX_BOARDS` (6) counted boards of every provider; Greenhouse is
searched first, so it could take all 6 and Lever, Ashby and Workable got none.

Now each provider has its own allowance from its `max_jobs`: it may read
`ceil(max_jobs / ATS_JOBS_PER_BOARD)` boards and gather `max_jobs` jobs (`_ats_searches`;
`budget[provider]`). Each board read asks for `min(ATS_JOBS_PER_BOARD, remaining)` jobs.
A provider that is off, used up or out of boards is skipped, including its Google `site:`
search, without affecting the others. Defaults: `ceil(ATS_MAX_BOARDS / 4) * ATS_JOBS_PER_BOARD`
= 8 jobs = 2 boards per provider, so up to 8 boards / 32 ATS jobs per search with all four
on (was 6 / 24 shared). That small growth is deliberate: it is the price of fairness.

`ATS_MAX_BOARDS` is no longer a shared cap. It only sets the default allowance, and `0` still
turns ATS off (the providers become unavailable). `ATS_JOBS_PER_BOARD` and
`ATS_RESOLVE_LINKS` are unchanged.

## Frontend

- `api.ts`: `BoardInfo`, `BoardSetting`, `BoardsConfig`, `getSearchBoards()`;
  `SearchRequest.boards?`.
- `components/search-boards.tsx`: a collapsed BoardUI `Accordion` item "Search boards" with a
  summary ("N of M boards on"). Each row is a BoardUI `Switch` labelled with the board name
  plus a BoardUI `NumberField` ("Jobs from <board>") with the catalog's min/max, disabled
  when the board is off or unavailable. Installed with `boardui add`: `switch`,
  `number-field`, `accordion`. Helpers in `utils/boards.ts` (`resolveBoards`, `anyBoardOn`).
- `pages/hero.tsx`: the panel sits above the submit button. The search is sent with the
  boards as shown (defaults filled in); it is blocked, with a message, when every board is
  off. If the list cannot load, the panel says so and the search is sent without `boards`
  (server defaults). Reopening a saved search shows its boards.
- Tests (Vitest): the panel renders from the API list, toggles, number limits/clamping,
  unavailable board, and the payload sent by the hero form.

## Not done / deferred

- Persisting the config between searches and named "search configurations" (next tasks).
- A "reset to defaults" control; per-query limits; per-board sort (explicitly out of scope).
- Not checked in a real browser or against live boards.
