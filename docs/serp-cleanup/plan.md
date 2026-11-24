# Clean up the `google_serp` and `builtin_nyc` modules

TODO item: "(cleanup serp module) Strip away the fluff from the `serp` module and keep only what
is necessary for the `networking_agent` to use it. Bonus: apply the same kind of update to
`builtin_nyc`."

## What the agent actually uses

`google_serp` (from `tools.py` and `linkedin.py`):

- `GoogleSerpSession()` with no arguments: `.start()`, `.close()`, `.search(query)` (links left
  unresolved), `.resolve_results(results)` (resolve only the results a tool returns).
- `CaptchaTimeoutError` (re-raised by the worker instead of restarting the browser).
- `SearchResult` fields `title`, `url`, `snippet`, `site_name`, `display_url`, `google_url`.
- `SearchResponse.results`.
- `google_serp.parser.is_google_redirect` (linkedin.py).

The 15-minute query cache and pick-then-resolve logic live in `tools._GoogleWorker` and are not
touched.

`builtin_nyc` (from `tools.py`):

- `api.get_jobs(JobFilter(search, category, experience_levels, remote_preferences), n)`
- `api.get_companies(CompanyFilter(industries, sizes, tech_stack, hiring_only, fully_remote), n)`
- Enums `JobCategory`, `ExperienceLevel`, `RemotePreference`, `CompanySize`.
- Model fields the tools return (title, url, company, location, salary, ...). `id` is kept for
  de-duplication across pages.

The `research/` scripts import neither module (they drive Playwright directly), so they are
unaffected.

## google_serp changes

- Delete `cli.py`, `__main__.py`, `py.typed`, `errors.py`.
- `CaptchaTimeoutError` moves into `session.py` (where it is raised) as a plain `Exception`
  subclass; the `GoogleSerpError` base class goes (only one error exists).
- `models.py`: `SearchResult` drops `position`; `SearchResponse` becomes `query` + `results`;
  `SearchMetadata` (result count, search time, page) and `to_dict()` go.
- `parser.py`: keep `parse_results`, `is_google_redirect`, `parse_meta_refresh`; drop metadata
  parsing and the `parse_results_page`/`parse_metadata` wrappers.
- `session.py`: `GoogleSerpSession()` takes no options (always off-screen window, 180 s CAPTCHA
  wait, `hl=en`; profile dir still overridable with `GOOGLE_SERP_PROFILE_DIR`). `search(query)`
  returns unresolved results; `resolve_results()` resolves in place. Drop pagination,
  `resolve_limit`, the `resolve_urls` flag, the module-level `search()` helper and its
  `strict=False` mode, and the context-manager methods. Errors always raise.
- `tools.py`: call `search(query)` instead of `search(query, resolve_urls=False)`; build the
  response with `query=` instead of `metadata=`.

## builtin_nyc changes

- `JobFilter`: keep `search`, `category`, `remote_preferences`, `experience_levels`.
- `CompanyFilter`: keep `industries`, `sizes`, `tech_stack`, `hiring_only`, `fully_remote`.
- `Job`/`Company`: drop fields no tool returns (logos, office/benefit counts, featured flag).
- `api.py`: drop the matching URL-building and parsing code.

## Tests and docs

- Delete `tests/google_serp/test_cli.py`; drop metadata / pagination / `resolve_limit` / `to_dict`
  tests; adapt fakes in `test_google_worker.py`. Trim `builtin_nyc` URL tests to kept filters.
- Rewrite `docs/google_serp/README.md` to the smaller API. `docs/google-serp-speed/findings.md`
  stays as a historical record.
- Nested `AGENTS.md` files are updated separately (content proposed in the report).
