# Plan: sort the Companies / Jobs / People pages

TODO item: *"(add ability to sort companies, jobs, or people in their pages) In their
individual pages, we should be able to sort by "CONNECTED" / "NOT CONNECTED" (or other field
values) to organize the listing."*

## Approach: client-side sort

The pages already load the full list (`GET /api/entities/<kind>`, most recently seen first)
and `App.tsx` already owns the APPLIED / CONNECTED status map, so sorting is a pure function
of data the browser has. No backend or API change. If lists ever get paginated, the same
option ids can become a `?sort=` query parameter.

## Sort options (only fields that exist on the entities)

| Page      | Options (default first)                                                         |
|-----------|---------------------------------------------------------------------------------|
| Companies | Most recent, Name A–Z, Most jobs, Most contacts                                 |
| Jobs      | Most recent, Applied first, Not applied first, Title A–Z, Company A–Z           |
| People    | Most recent, Connected first, Not connected first, Name A–Z, Company A–Z        |

- "Most recent" = `last_seen` descending (the server's order, so it is also the default).
- Status options read the status map (`job` / `person`); an entity with no entry is "not".
- Text options compare with `Intl.Collator` (case/accent-insensitive, numeric); blank
  values (e.g. a person with no company) go last.
- Every comparator is stable and falls back to the server order (recency) on ties, so e.g.
  "Connected first" shows connected people most-recent first.

## Code

- `frontend/src/utils/sort-entities.ts` (pure, no React): a `SortOption<T>` is
  `{ id, label, compare(a, b, ctx) }` where `ctx` carries the status map. `SORT_OPTIONS`
  holds the list per entity kind, `DEFAULT_SORT` the default id, and
  `sortEntities(kind, items, sortId, ctx)` returns a new sorted array (unknown id → default).
  Small comparator builders (`byText`, `byNumberDesc`, `byStatus`, `byLastSeen`) keep each
  option a one-liner, so the upcoming "pinned" sort is a new entry (plus a `pins` field on
  the context), not a new mechanism.
- BoardUI `select` installed (`npx boardui@latest add select`; adds `base/select`,
  `base/dropdown/menu-styles.ts`, `foundations/icons/chevrons.tsx`).
- `pages/entities.tsx`: each page keeps its sort id in state and passes sorted items to
  `EntityPage`, which renders a "Sort by" `Select` (size `sm`) in the header, shown once
  there are at least two items.
- Toggling a status while sorted by status moves the card immediately (the list is derived
  on every render). Acceptable for now; revisit if it feels jumpy.

## Verification

- `npm run build` and `npm run lint` in `frontend/`; the helper is exercised with a scratch
  Node script (the frontend has no test runner).
- Backend unchanged, but run the full pytest suite and ruff check/format as a regression.
