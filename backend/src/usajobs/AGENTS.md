# usajobs

Federal job announcements from the official USAJOBS API (`GET https://data.usajobs.gov/api/search`),
used by the search pipeline through `tools.usajobs_jobs`. Mainly for conservation roles at
NPS, USFWS, USFS and EPA. Design: `docs/usajobs/plan.md`.

- Needs a free key (https://developer.usajobs.gov/apirequest): env vars `USAJOBS_API_KEY` and
  `USAJOBS_EMAIL` (the registered email, sent as `User-Agent`), read in `config.py`. Without
  both, `config.usajobs_configured()` is False: the plan prompt does not offer the source and
  `find_jobs` records a "skipped" trace step instead of an error.
- Credentials go only into request headers (`api.request_headers`). Never put them in URLs,
  logs, traces or exception messages; `UsajobsError` messages are fixed strings.
- `models.Agency` maps agencies to the `Organization` subelement codes. Verified 2026-11-24
  against the live code list (`/api/codelist/agencysubelements`, with the key headers): AG11
  Forest Service, IN10 National Park Service, IN15 U.S. Fish and Wildlife Service, EP00 EPA,
  all active.
- Always sends `WhoMayApply=public` (other values need special authorization).
- One request per query (up to 500 results per page; the pipeline asks for
  `config.USAJOBS_RESULTS`). Multiple values of a parameter are `;`-delimited.

## Code Style

- Always use type hints in function signatures
- Always lint using Ruff (backend config: `backend/pyproject.toml`)

## Tests

Offline, with mocked HTTP and `tests/usajobs/fixtures/search.json`, which is built from the
documented response shape, not recorded from the live API.
