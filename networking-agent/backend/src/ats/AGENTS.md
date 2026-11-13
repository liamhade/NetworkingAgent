# ats

Employer-direct job postings from applicant tracking systems (ATS). Used by the search
pipeline through `tools.ats_boards` and `tools.ats_jobs`; the plan's `ats_jobs` queries drive
it. Design and tradeoffs: `networking-agent/docs/ats-boards/plan.md`.

Flow per planned query and provider:

1. `tools.ats_boards`: one Google `site:` search (`search.site_query`) through the shared
   Google worker (`tools.run_google_search`, cached). Board slugs are read from each
   result's breadcrumb (`job-boards.greenhouse.io › acme › jobs › 123`), so most results
   need no `/goto` resolving. Only results whose breadcrumb hides the board (embeds,
   truncated crumbs) are resolved, at most `config.ATS_RESOLVE_LINKS`.
2. `tools.ats_jobs`: the board's public JSON API (`Provider.list_jobs`), then
   `search.filter_jobs`: postings Google linked to first, then title/department keyword
   matches in the wanted location, at most `config.ATS_JOBS_PER_BOARD`.
3. `pipeline.steps._ats_searches` reads at most `config.ATS_MAX_BOARDS` boards per search
   (deduplicated across queries). Each board search and board read is its own trace step
   (`ats_boards`, `ats_jobs`); a failing one is recorded and skipped.

## Layout

- `base.py`: `Provider` interface and the shared `get_json` (patched in tests)
- `models.py`: `BoardRef` (parsed URL), `Board` (found through Google), `AtsJob`
- `greenhouse.py`: the Greenhouse provider (`GREENHOUSE`)
- `registry.py`: `PROVIDERS`, `get_provider()`, `parse_url()`
- `search.py`: pure helpers: `site_query`, breadcrumbs -> boards, keyword/location matching

`read_page.methods.greenhouse_ids` uses `GREENHOUSE.parse_url`, so the Greenhouse URL rules
live only here. `ats` must not import `read_page` (that would be an import cycle).

## Adding a provider (Lever, Ashby, Workable, ...)

1. New module `ats/<name>.py` with a `Provider` subclass: `name`, `label`, `site_domains`
   (hosts for `site:`), `host_pattern` (every board host), `parse_url` (board slug and
   posting id; return None for anything else), `board_url`, and `list_jobs` (fetch the
   public API with `get_json`, normalize to `AtsJob`, raise on HTTP errors). Keep `url`
   the employer-direct posting URL the API gives.
2. Add the instance to `PROVIDERS` in `registry.py`. The pipeline then runs one extra
   Google search per planned ATS query for it; mention it in `prompts.PLAN_PROMPT`.
3. Tests in `backend/tests/ats/` with a trimmed API response in `fixtures/`: URL parsing
   (incl. EU/embed forms), normalization, and a breadcrumb case in `google_results.json`.
4. If `read_page` has its own URL regex for that ATS, point it at the provider's
   `parse_url` too.

Known public APIs: Lever `https://api.lever.co/v0/postings/<slug>?mode=json` (EU:
`api.eu.lever.co`), Ashby `https://api.ashbyhq.com/posting-api/job-board/<slug>`, Workable
`https://apply.workable.com/api/v1/widget/accounts/<slug>`. Check the shape with a few spaced
live requests before relying on it.

## Rules

- Never start a browser here; Google goes through `tools.run_google_search` only.
- Fetch only the boards that will be read, and keep live checks to a few spaced requests.
- Tests are offline: mocked `get_json` and a fake Google (`tests/ats/`).
