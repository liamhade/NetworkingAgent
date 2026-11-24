# ats

Employer-direct job postings from applicant tracking systems (ATS). Used by the search
pipeline through `tools.ats_boards` and `tools.ats_jobs`; the plan's `ats_jobs` queries drive
it. Design and tradeoffs: `docs/ats-boards/plan.md`.

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
Workable's widget API returns the real company name (`name`) and all postings in one request
(no pagination, no descriptions: 6 postings = 4 KB); `list_jobs` uses it instead of the slug.
Posting ids are the uppercase shortcodes (`parse_url` upper-cases breadcrumb ids to match);
the API's posting `url` (`apply.workable.com/j/<SHORTCODE>`) has no account, so such URLs are
not parseable into a board. Legacy `<account>.workable.com` hosts are accepted except Workable's
own (`www`, `resources`, `help`, ...). Accounts hosted elsewhere answer 200 with no jobs.
`read_page` has no Workable method (the generic JSON-LD path is used).

## Layout

- `base.py`: `Provider` interface and the shared `get_json` (patched in tests)
- `models.py`: `BoardRef` (parsed URL), `Board` (found through Google), `AtsJob`
- `greenhouse.py`: the Greenhouse provider (`GREENHOUSE`)
- `lever.py`: the Lever provider (`LEVER`); EU boards are found by retrying a 404 on the EU API
- `ashby.py`: the Ashby provider (`ASHBY`), `jobs.ashbyhq.com` + the public job-board API
- `workable.py`: the Workable provider (`WORKABLE`), `apply.workable.com` + the public widget API
- `registry.py`: `PROVIDERS`, `get_provider()`, `parse_url()`
- `search.py`: pure helpers: `site_query`, breadcrumbs -> boards, keyword/location matching

`read_page.methods.greenhouse_ids` uses `GREENHOUSE.parse_url` and
`read_page.methods.lever_api_url` uses `LEVER.parse_url` / `LEVER.api_base` and
`read_page.methods.read_ashby` uses `ASHBY.parse_url`, so those URL
rules live only here. `ats` must not import `read_page` (that would be an import cycle).

Provider quirks: Lever's API has no company name (`lever.company_name` title-cases the slug)
and always includes full descriptions (~10 KB per posting); remote postings get "(Remote)"
appended to their location so a "remote" search matches them. Ashby also has no company
name (it reuses `lever.company_name`) and always includes descriptions (Ramp: 179 postings,
3 MB); `list_jobs` leaves `includeCompensation` off (no pay field in `AtsJob`, +7% payload).
Ashby's `isRemote` is true for most hybrid postings, so only `workplaceType == "Remote"` adds
"(Remote)"; secondary locations are joined into `location`, and `isListed: false` postings are
skipped.

## Adding a provider

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

Every registered provider costs one more Google search per planned ATS query (Greenhouse +
Lever + Ashby + Workable = 4 per query, up to 8 per pipeline run), unless `ATS_MAX_BOARDS` is
reached first. The board cap is shared and providers are searched in `PROVIDERS` order, so a
Greenhouse search that fills it leaves the later providers unsearched.

## Rules

- Never start a browser here; Google goes through `tools.run_google_search` only.
- Fetch only the boards that will be read, and keep live checks to a few spaced requests.
- Tests are offline: mocked `get_json` and a fake Google (`tests/ats/`).
