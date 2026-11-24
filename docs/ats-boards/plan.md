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

## Lever (second provider)

Goal: add Lever (`jobs.lever.co`, public Postings API) as `ats/lever.py` + one `PROVIDERS`
entry, without changing the pipeline design.

### Findings (2026-11-13, 3 requests to the Postings API, spaced 6 s, none limited)

- `GET https://api.lever.co/v0/postings/<slug>?mode=json` returns a JSON **array** (no
  wrapper, no pagination by default). Each posting has `id` (UUID), `text` (title),
  `hostedUrl`, `applyUrl` (`hostedUrl` + `/apply`), `createdAt` (epoch ms), `country`,
  `workplaceType` (`onsite` / `hybrid` / `remote`), `categories` (`location`,
  `allLocations`, `team`, `department`, `commitment`; `commitment` sometimes missing) and
  the full description (`description`, `descriptionBody`, `opening`, `lists`,
  `additional` and `*Plain` twins). Spotify: 85 postings, 800 KB.
- There is no parameter to leave the descriptions out, and no company name anywhere.
- Unknown board: `404 {"ok":false,"error":"Document not found"}`, on both `api.lever.co`
  and `api.eu.lever.co`.
- No real EU board was checked (none known); `read_page` already used `api.eu.lever.co`
  for `jobs.eu.lever.co` postings.

### Design

- `Lever` provider: `site_domains = ("jobs.lever.co", "jobs.eu.lever.co")`, hosts
  `jobs(.eu).lever.co`. `parse_url` reads `/<slug>` and `/<slug>/<uuid>` (any trailing
  `/apply`, query string ignored; non-UUID second segments give a board-only ref).
- `list_jobs(slug)` asks the US API; on a 404 it asks the EU API (a second 404 is raised as
  an unknown board) and remembers the slug so `board_url` links `jobs.eu.lever.co`. Other
  HTTP errors (429, 5xx) are raised without the EU retry. A `Board` only carries a slug,
  so this keeps EU support without changing the shared models.
- Normalization: `title` = `text`, `url` = `hostedUrl` (else built), `company` = slug
  title-cased (`acme-labs` -> `Acme Labs`), `location` = all of `allLocations` joined with
  " / " (else `location`), plus " (Remote)" for `workplaceType == "remote"` so
  `matches_location(..., "remote")` finds them; `departments` = `[department, team]`
  (deduplicated, so keyword matching also sees the team); `posted` = `createdAt` as a UTC
  date.
- `read_page.methods.read_lever` now builds its API URL with `lever_api_url`, which uses
  `LEVER.parse_url` + `LEVER.api_base` (the `_LEVER` regex is gone). `read_page`'s
  registry regex still routes `jobs(.eu).lever.co/<slug>/<uuid>` URLs to `lever_api`.
- `search.breadcrumb_url` also treats a segment ending in "…" (Google truncating a long
  UUID) as truncation, so `jobs.lever.co › spotify › 2a55d6c9-c5…` still gives the board.
- `PLAN_PROMPT`: `ats_jobs` names Greenhouse and Lever and says each search costs one
  Google search per board provider; the `google_queries` example no longer suggests
  `site:lever.co` (now `site:ashbyhq.com` only). `SearchPlan.ats_jobs` description updated.

### Google searches per pipeline run

`_ats_searches` runs one `site:` search per (ATS query, provider) until `ATS_MAX_BOARDS`
(6) boards are read. With `cap_plan`'s 2 ATS queries: at most 2 searches before, at most
4 now, i.e. **+0 to +2 Google searches per run** (+1 per planned ATS query), and none
when the plan has no `ats_jobs`. The extra search is skipped when an earlier search
already filled the board cap. Each search is 2-25 s on the shared Chrome worker and
cached for 15 minutes.

### Tests (offline)

`test_ats_lever.py` (URL forms incl. EU, `/apply`, query strings, rejections; registry;
company names; normalization from a trimmed live Spotify fixture `lever_postings.json`;
broken entries and gaps; empty/odd responses; EU fallback; 404 on both hosts; 429 not
retried). `google_results.json` gained Lever results (full crumb, board crumb, "…"
truncated UUID, EU `/apply`, fully truncated) used by `test_ats_search.py` and
`test_ats_tools.py` (Lever `site:` query, breadcrumb boards, resolution, `ats_jobs`).
`pipeline_fakes.fake_ats_boards` now returns only boards of the searched provider, and
`test_ats_pipeline.py` expects a Greenhouse and a Lever search per query.

### Caveats / deferred

- Lever responses are large (descriptions can't be excluded); reading 6 boards can be a
  few MB. A board-level cache would help if boards repeat.
- The board cap is shared and Greenhouse is searched first, so a Greenhouse search that
  yields 6 boards means Lever is never searched for that run. A per-provider share or
  interleaving would be fairer; left as is to keep the pipeline design.
- Company names are guessed from slugs (`mckinsey` -> `Mckinsey`); the LLM ranking and
  entity matching may see slightly off names. The board page's `<title>` would give the
  real name at the cost of one more request per board.
- EU fallback costs a second request for unknown/closed boards; EU boards were not
  verified live.

## Ashby (third provider)

Goal: add Ashby (`jobs.ashbyhq.com`, public job-board API) as `ats/ashby.py` + one
`PROVIDERS` entry, without changing the pipeline design.

### Findings (2026-11-13, 3 requests to the job-board API, spaced 6 s, none limited)

- `GET https://api.ashbyhq.com/posting-api/job-board/<org>` returns
  `{"apiVersion": "1", "jobs": [...]}`. Each job has `id` (UUID), `title` (sometimes with
  leading/trailing spaces), `department`, `team`, `employmentType`, `location` (primary),
  `secondaryLocations` (`[{"location", "address"}]`), `publishedAt` (ISO timestamp),
  `isListed`, `isRemote`, `workplaceType` (`OnSite` / `Hybrid` / `Remote`), `address`,
  `jobUrl`, `applyUrl` (`jobUrl` + `/application`) and the full description
  (`descriptionHtml`, `descriptionPlain`). Ramp: 179 postings, 3.0 MB.
- `?includeCompensation=true` adds pay data: 3.24 MB vs 3.02 MB (+7%). Not requested by
  `list_jobs` since `AtsJob` has no pay field; `read_page.read_ashby` still asks for it
  (it shows pay on a single posting).
- `isRemote` is true for most hybrid NYC postings (any remote-capable secondary location),
  so it is not a good "remote" signal; `workplaceType` is.
- No company name in the response. Unknown board: `404` with plain-text `Not Found`.

### Design

- `Ashby` provider: `site_domains = ("jobs.ashbyhq.com",)`, host `jobs.ashbyhq.com`.
  `parse_url` reads `/<org>` and `/<org>/<uuid>` (trailing `/application`, query string and
  fragment ignored; a non-UUID second segment gives a board-only ref).
- `list_jobs(org)`: one request, no params; HTTP errors (404 = unknown board) are raised.
- Normalization: `title` stripped, `url` = `jobUrl` (else built), `company` = slug
  title-cased (`lever.company_name`), `location` = primary + secondary locations joined with
  " / " plus " (Remote)" for `workplaceType == "Remote"` when not already said,
  `departments` = `[department, team]` deduplicated, `posted` = date part of `publishedAt`.
  `isListed: false` postings are skipped.
- `read_page.methods.read_ashby` now uses `ASHBY.parse_url` (the `_ASHBY` regex is gone) and
  compares posting ids case-insensitively. `read_page`'s registry regex still routes
  `jobs.ashbyhq.com/<org>/<uuid>` URLs to `ashby_api`.
- Breadcrumbs: `jobs.ashbyhq.com › ramp › <uuid>` and `› ramp › 34413f8d-26bf…` both give the
  board through the existing `search.breadcrumb_url`; `jobs.ashbyhq.com › …` is resolved.
- `PLAN_PROMPT`: `ats_jobs` names Greenhouse, Lever and Ashby; the `google_queries` example
  is now `"<role>" jobs <city> "<company>" careers` (no ATS `site:` suggestion).
  `SearchPlan.ats_jobs` description updated.

### Google searches per pipeline run

One `site:` search per (ATS query, provider): with `cap_plan`'s 2 ATS queries and 3
providers, at most **6** ATS searches per run (was 4), fewer once `ATS_MAX_BOARDS` (6) is
reached; plus the 0-2 `google_queries`, i.e. up to 8 Google searches per run in total.

### Tests (offline)

`test_ats_ashby.py` (URL forms incl. `/application`, query strings, fragments, rejections;
registry order; normalization from a trimmed live Ramp fixture `ashby_job_board.json`;
missing fields, unlisted postings, empty/odd responses; 404). `google_results.json` gained
Ashby results (full crumb, board crumb, "…" truncated UUID, `/application`, fully
truncated) used by `test_ats_search.py` and `test_ats_tools.py`. `test_ats_pipeline.py`
expects a Greenhouse, a Lever and an Ashby search per query.

### Caveats / deferred

- Payloads are large (descriptions can't be excluded): 6 Ashby boards can be ~10 MB+.
- The shared board cap starves later providers more now (Ashby is searched last).
- No EU Ashby host is known; only `jobs.ashbyhq.com` is handled. Ashby boards embedded on
  company domains (`?ashby_jid=...`) are not recognised.

## Workable

Fourth provider (`ats/workable.py`, last in `PROVIDERS`). Live checks (5 requests, spaced
6+ s apart, no key, no challenges):

- `GET https://apply.workable.com/api/v1/widget/accounts/<account>` (chosen): 200 with
  `{"name", "description", "jobs": [...]}`. All open postings come in one response with no
  pagination and no descriptions (Hugging Face: 6 postings, 4.3 KB). `name` is the real company
  name. Unknown account: `404` plain text "Not Found". Accounts whose boards live elsewhere
  (Canonical, Jobgether) answer 200 with `jobs: []`, which is treated as an empty board.
- `POST https://apply.workable.com/api/v3/accounts/<account>/jobs` (not used): 200,
  `{"results", "total"}` (3.3 KB for the same board, `nextPage` token when more); fewer
  fields (no `url`, department as a list, no company name). The widget has everything needed
  in one request, so pagination is not implemented. The `www.workable.com` API was not tried.
- Job fields used: `shortcode` (id, upper-cased), `title`, `url` (`apply.workable.com/j/<CODE>`,
  kept; built as `<board>/j/<code>/` if missing), `department` + `function` (departments),
  `published_on`/`created_at` (date), `telecommuting`, and `locations` (else `city`/`state`/
  `country`). Location = every place as "City, Region, Country" joined with " / ", plus
  "(Remote)" for telecommuting postings. Hidden locations are kept (they still name a country).

- `Workable` provider: `site_domains = ("apply.workable.com",)`, `host_pattern` any
  `*.workable.com`. `parse_url` reads `/<account>` and `/<account>/j/<SHORTCODE>` (trailing
  `/apply`, query, fragment ignored), plus legacy `<account>.workable.com[/jobs/<id>]`. It
  rejects Workable's own hosts (`www`, `resources`, `help`, ...), `apply.workable.com/api/...`
  and account-less `apply.workable.com/j/<CODE>`.
- `read_page` has no Workable handling, so nothing was changed there.
- Breadcrumbs: `apply.workable.com › acct › j › SHORTCODE` gives board and posting; a "…"
  truncated shortcode gives the board; `apply.workable.com › …` is resolved.
- `PLAN_PROMPT` and `SearchPlan.ats_jobs` name all four providers.

### Google searches per pipeline run

With `cap_plan`'s 2 ATS queries and 4 providers, up to **8** ATS searches per run (was 6),
fewer once `ATS_MAX_BOARDS` (6, unchanged) is reached; plus 0-2 `google_queries`, i.e. up to
**10** Google searches per run in total.

### Tests (offline)

`test_ats_workable.py` (valid/legacy/rejected URLs, registry order, normalization from a
trimmed live Hugging Face fixture `workable_widget.json`, missing fields, empty/odd responses,
404). `google_results.json` gained Workable results; search, tools and pipeline tests cover
four providers.

### Caveats / deferred

- Workable is searched last, so a full shared board cap starves it most.
- The widget API's behaviour on very large boards (a possible job cap) was not observed.
- Boards embedded on company domains are not recognised.
