# Plan: Companies / Jobs / People pages (menu bar)

TODO item: *"(Add company + jobs + person to menu bar) In the menu bar, there should be three
pages we can navigate to: Companies, Jobs, and People. Each page shows a list of the
respective entities that we have encountered through our search. Each entity (company, job,
or person) should be in its own widget box. Every time we make a new search, these lists are
updated to include them."*

## Aggregate on read (no separate index)

The lists are computed from the user's saved searches on every request instead of keeping a
second "entities" store updated on save. Why:

- Saved searches are already the source of truth; an index would be a second copy that can
  drift (failed write, deleted/corrupt search file, manual edits) and would need a backfill
  for searches saved before this change.
- Keys are re-derived with the current `entities.keys` rules on every read (same approach
  as reopening a saved search), so normalization changes apply retroactively for free.
- Cost is O(total results) per request: a few hundred small objects for a POC user.
- On Supabase this maps naturally to a view / materialized view over the searches table.

If it gets slow, the same `entities.catalog` functions can build a cached index on save.

## Merge rules (`backend/src/entities/catalog.py`, pure functions)

- Identity = entity key (`company:name:…`, `job:…`, `person:…`). Companies come from the
  company results; every job/person is nested under a company, so each job/person also
  contributes to its company's `job_count` / `person_count` (distinct keys).
- Searches are processed newest first. The newest sighting's fields win; a field that is
  blank there is filled from the newest older sighting that has it (e.g. a salary that only
  one search returned).
- `first_seen` / `last_seen` = creation time of the oldest / newest search containing the
  entity; `searches` = those searches (`SearchSummary`), newest first, de-duplicated (the
  same person under two companies in one search counts once).
- Order: `last_seen` desc, then position within that search.

Models in `schemas.py`: `Sighting` (key, first_seen, last_seen, searches) and
`CompanyEntity` / `JobEntity` / `PersonEntity` extending it. Jobs/people also carry
`company` and `company_key`.

`userdata/history.py` gains `load_searches(user_id)` (full records, newest first, corrupt
files skipped); `list_searches` is built on it.

## API

- `GET /api/entities/companies` → `CompanyEntity[]`
- `GET /api/entities/jobs` → `JobEntity[]`
- `GET /api/entities/people` → `PersonEntity[]`

All take the `CurrentUser` dependency (TEST_USER). Unknown kinds are 404 (no route).

## Frontend

- `components/top-nav.tsx`: sticky menu bar at the top of the main column with
  Search / Companies / Jobs / People links (semantic tokens, `aria-current="page"`).
- Routing: view state mirrored in the URL hash (`#/`, `#/companies`, `#/jobs`, `#/people`,
  helpers in `utils/view.ts`) so back/forward and reload work; no router dependency.
  Opening a saved search or starting a new one switches back to the Search view.
- `pages/entities.tsx`: `CompaniesPage`, `JobsPage`, `PeoplePage`. Each entity is its own
  card (`rounded-3xl` widget, same look as the results page): name/title link, meta line,
  alignment box, and a footer with "Last seen …" plus buttons that reopen the searches it
  came from. Job cards keep the APPLIED toggle and person cards the CONNECTED toggle, using
  `StatusToggle` and the status map owned by `App.tsx` (so a toggle on any page is reflected
  everywhere).
- Refresh: `App.tsx` bumps an `entitiesVersion` counter on every `saved` SSE event; the
  pages re-fetch when it changes (and on every visit), keeping the old list on screen while
  loading.
- Small refactor: date formatting shared by the history panel and the cards moves to
  `utils/format-date.ts`; `ExternalLink` / `ErrorBanner` are exported from `results.tsx`.

## Verification

- pytest: merge/dedup/ordering/fallback-key unit tests and endpoint tests, including
  "a new search updates the lists" through `TestClient` with a mocked agent. ruff
  check/format.
- `npm run build` and `npm run lint` in `frontend/`.
