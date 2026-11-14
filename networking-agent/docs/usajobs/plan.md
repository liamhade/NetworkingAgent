# USAJOBS source

Adds the official USAJOBS search API as a job source, mainly for federal conservation roles
(NPS, USFWS, USFS, EPA). Code: `backend/src/usajobs/`; notes for agents: `usajobs/AGENTS.md`.

## API (from developer.usajobs.gov/api-reference/get-api-search)

- `GET https://data.usajobs.gov/api/search`; headers `Host: data.usajobs.gov`,
  `User-Agent: <registered email>`, `Authorization-Key: <key>`. Free key:
  https://developer.usajobs.gov/apirequest.
- Parameters used: `Keyword`, `LocationName`, `Radius` (only with a location), `Organization`
  (agency subelement codes, `;`-delimited), `RemoteIndicator=True`, `DatePosted` (0-60),
  `ResultsPerPage` (max 500), `WhoMayApply=public` (`All`/`Status` need special authorization).
- Response: `SearchResult.SearchResultItems[].MatchedObjectDescriptor` (PositionTitle,
  PositionURI, ApplyURI[], OrganizationName, DepartmentName, PositionLocationDisplay,
  PositionRemuneration[], PublicationStartDate, ApplicationCloseDate, QualificationSummary...).

## Design

- **Credentials**: `USAJOBS_API_KEY` and `USAJOBS_EMAIL` in `config.py`. `config.usajobs_configured()`
  is true only with both set and `USAJOBS_MAX_QUERIES > 0`. They only go into request headers;
  errors use fixed messages (`UsajobsError`), network exceptions are re-raised without their
  original message, and plan args/trace never include them.
- **Plan**: `SearchPlan.usajobs: list[UsajobsQuery]` with `keywords`, `location` (city/state,
  `"remote"` or `""`) and `agencies` (`nps`, `usfws`, `usfs`, `epa`; `[]` = any agency).
- **Prompt**: `prompts.plan_prompt()` adds `USAJOBS_PLAN_PROMPT` only when configured, so the
  LLM is never asked for a source that would be skipped.
- **Wiring**: `cap_plan` keeps at most `USAJOBS_MAX_QUERIES` non-empty queries and counts
  USAJOBS toward "has a source" only when configured (otherwise the Google fallback applies).
  `find_jobs` runs each query through `tools.usajobs_jobs` (a trace step `usajobs` per query).
  Without credentials but with planned queries it records one step with
  `note="skipped: USAJOBS_API_KEY and USAJOBS_EMAIL are not both configured"`, no error.
  Failures (401, 429, 5xx, network) are recorded in the step's `error` and the search goes on.
- **Normalization** to the shared job dict: company = `OrganizationName` (falls back to
  `DepartmentName`), url = `PositionURI`, salary = `$min - $max per year|hour`, deadline =
  `closes YYYY-MM-DD` (shown in the job summary with the job type and qualification summary).
- **Knobs**: `USAJOBS_MAX_QUERIES` (default 2, 0 = off), `USAJOBS_RESULTS` (default 10 per query).

## Caveats

- Agency codes NPS `IN10`, USFWS `IN15`, USFS `AG11`, EPA `EP00` were taken from the task
  brief; they could not be verified (the public code list endpoint refused a script request
  and no key was configured). Verify against `/api/codelist/agencysubelements` and fix
  `usajobs.models.Agency` if needed.
- The test fixture is built from the documented response shape, not recorded live.
- No live requests were made.
