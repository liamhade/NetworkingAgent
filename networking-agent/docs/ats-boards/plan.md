# ATS job boards: Greenhouse (shared `ats` layer)

Goal: find employer-direct postings by running Google `site:` searches for Greenhouse boards
(e.g. `site:job-boards.greenhouse.io OR site:boards.greenhouse.io "data analyst" "New York"`),
then pull each company's open jobs from Greenhouse's public JSON board API. Build it as a
shared `ats` layer so Lever, Ashby and Workable are each one new module + one registry entry.

## Findings (2026-11-13, 5 requests to the public board API, spaced 5 s, none limited)

- `GET https://boards-api.greenhouse.io/v1/boards/<slug>/jobs` returns
  `{"jobs": [...], "meta": {"total": N}}`. Each job has `id`, `title`, `absolute_url`,
  `location.name`, `company_name`, `first_published`, `updated_at`, `requisition_id`,
  `metadata`, `language`. (Discord: 25 jobs, 20 KB.)
- `?content=true` adds `content` (HTML-escaped description), `departments` and `offices`,
  but the same board was 245 KB (~12x). Not used: titles + locations are enough to match,
  and the pipeline later reads the chosen postings in full through `read_page`'s
  `greenhouse_api` method.
- `GET .../boards/<slug>` returns `{"name", "content"}` (board/company name and about).
- Unknown board: `404 {"status":404,"error":"Job not found"}`.
- `boards-api.eu.greenhouse.io` does not resolve: EU boards (`job-boards.eu.greenhouse.io`)
  are queried on the main API host, as `read_page` already did (unverified for a real EU
  board; see caveats).
- Google result links are opaque `/goto` redirects, but the breadcrumb
  (`https://job-boards.greenhouse.io › discord › jobs › 8917177002`) shows the board slug
  and often the posting id, so resolving is only needed for embeds
  (`boards.greenhouse.io/embed/job_app?for=<slug>&token=<id>`) and truncated crumbs.

## Design

### `backend/src/ats/` (new sub-package)

- `base.py`: `Provider` ABC: `name`, `label`, `site_domains` (for `site:`), `host_pattern`,
  `owns(url)`, `parse_url(url) -> BoardRef | None`, `board_url(slug)`,
  `list_jobs(slug) -> list[AtsJob]`. Shared `get_json` (requests, desktop UA, 20 s timeout).
- `models.py`: `BoardRef(provider, slug, job_id)`, `Board(provider, slug, job_ids)`,
  `AtsJob(provider, board, id, title, url, company, location, departments, posted)`.
- `greenhouse.py`: `Greenhouse` provider. Parses `boards.`, `job-boards.`, `.eu.` hosts,
  `/<slug>`, `/<slug>/jobs/<id>`, and `/embed/job_app|job_board?for=<slug>&token=<id>`.
  `list_jobs` normalizes the list endpoint; if a posting lacks `company_name`, the board's
  name (else the slug) fills it.
- `registry.py`: `PROVIDERS` (Greenhouse only for now), `get_provider`, `parse_url`.
- `search.py`: pure helpers: `site_query`, `breadcrumb_url`, `board_ref` (resolved URL
  first, else breadcrumb), `needs_resolving`, `merge_boards`/`boards_from_results`,
  `matches_keywords`, `matches_location`, `filter_jobs`.

### `tools.py`

- `ats_boards(provider, keywords, location)`: one `site:` search through
  `run_google_search` (the one shared Chrome worker and its 15-minute cache). Its `pick`
  callback returns only results that need resolving (capped by `ATS_RESOLVE_LINKS`); all
  other boards are read from breadcrumbs. A page with no result on the provider's hosts
  (Google ignored `site:`) is not cached. Returns `{provider, slug, job_ids}` per board.
- `ats_jobs(provider, board, keywords, location, job_ids, n)`: the board's postings,
  filtered, as job dicts like the other sources (`title, url, company, company_url,
  location, summary`). `company_url` is the board page.

### Pipeline

- `SearchPlan.ats_jobs: list[AtsJobQuery]` (`keywords`: 1-3 word role phrase, `location`:
  city / "remote" / ""). `cap_plan` keeps at most 2 non-empty queries; a plan with only
  ATS queries no longer gets the Google fallback query.
- `find_jobs`: after BuiltIn/Conservation/Google searches, `_ats_searches` runs, for every
  ATS query and every registered provider, `ats_boards` (trace source `ats_boards`) and
  then `ats_jobs` for each new board (trace source `ats_jobs`, args include `board` and
  `job_ids`), until `ATS_MAX_BOARDS` boards are read. Boards are deduplicated across
  queries. Errors are recorded per step and skipped. ATS jobs count towards
  `MIN_JOBS_BEFORE_GOOGLE`.
- `PLAN_PROMPT` describes `ats_jobs`; the `google_queries` example now points at Lever /
  Ashby instead of Greenhouse.
- `read_page.methods.greenhouse_ids` now delegates to `GREENHOUSE.parse_url` (one set of
  Greenhouse URL rules).

### Config knobs (`config.py`)

| Knob | Default | Meaning |
| --- | --- | --- |
| `ATS_MAX_BOARDS` | 6 | Boards read per search across all ATS queries (0 turns ATS off) |
| `ATS_JOBS_PER_BOARD` | 4 | Matching postings kept per board |
| `ATS_RESOLVE_LINKS` | 3 | Google `/goto` links resolved per board search (hidden boards only) |

## Decisions and tradeoffs

- **Breadcrumbs instead of resolving.** Resolving `/goto` links is ~95% of a Google
  search's time. Reading the slug from the breadcrumb makes a board search a single page
  load in the common case; only embeds/truncated crumbs are resolved, capped.
- **One Google search per (query, provider).** Simpler and gives each provider its own
  10 results; the cost is one extra Google search per provider per query once Lever/Ashby
  are added. Alternative: one OR-ed query over all providers' hosts.
- **Code, not the LLM, picks the postings.** The LLM gives a role phrase + location;
  matching is deterministic: every keyword (stopwords aside) must start a word of the
  title or a department, with a crude stem (`analyst` -> `analy-` also matches
  `analytics`). A city matches postings naming it or a small alias set (NYC, Bay Area, DC);
  "remote" matches postings saying remote. Postings Google linked to directly come first
  even if they fail the filter, since Google already matched them to the query.
- **No `?content=true`.** 12x smaller responses; descriptions come later via `read_page`.
- **`url` = the API's `absolute_url`** (employer-direct; sometimes the company's own careers
  page with `gh_jid`). `read_page` handles Greenhouse-hosted URLs through the API; custom
  careers-page URLs fall back to its generic methods.
- **Failure isolation.** Each board search and each board read is its own `call()` in the
  trace, so a 404 board or a CAPTCHA skips only that step.

## Tests (offline)

`backend/tests/ats/`: `test_ats_greenhouse.py` (URL forms, normalization from a trimmed
live fixture, gaps, 404), `test_ats_search.py` (query, breadcrumbs, board merging,
resolve selection, matching, caps), `test_ats_tools.py` (fake Google worker: only hidden
boards resolved, resolve cap, cache rejection, errors; fake API), `test_ats_pipeline.py`
(jobs gathered and ranked, board cap + dedupe across queries, ATS off, failing board /
board search recorded and skipped, Google fallback skipped, plan caps).
`pipeline_fakes.FakeSources` gained `ats_boards` / `ats_board_jobs` fakes.

## Caveats / deferred

- EU boards are assumed to be served by `boards-api.greenhouse.io` (no EU API host exists);
  not verified with a real EU board.
- Breadcrumb format is Google's and may change; resolution remains the fallback.
- Location matching is substring/alias based; postings listing only a region ("US East")
  won't match a city.
- No board-level cache: a board read twice in one process is fetched twice (Google pages
  are cached).
- No live Google run was done; first real searches should check the `ats_boards` trace
  steps (count and note) for how many boards come from breadcrumbs.
