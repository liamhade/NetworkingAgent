# Plan: applied / connected counts on the Jobs and People pages

TODO item: *"(add counts) For jobs and people, we should add a count to their pages to show
how many out of the total number we have connected / applied to, shown as an X/Y format."*

## Approach

Client-side only, like sorting (`docs/entity-sorting/plan.md`): the page already has the
full list and `App.tsx` owns the status map, so no backend change.

- The count chip next to the page title becomes **"3/12 applied"** on Jobs and
  **"5/40 connected"** on People. Companies keep the plain "12 companies" chip (they have
  no status). One chip, not two, to keep the header tidy; the total is still visible as Y.
- `frontend/src/utils/count-status.ts`: pure `countStatus(items, statuses)` returning
  `{ active, total }`. An entity with no saved status counts as not applied / connected;
  status entries for entities not in the list are ignored, so `active <= total`.
- `pages/entities.tsx`: Jobs / People compute the count with `useMemo` over the unsorted
  list and their slice of the status map, so it updates as soon as a toggle flips (the
  status map is replaced optimistically in `App.tsx`). The label word lives on `PAGES`
  (`statusLabel`).

## Verification

- `npm run build`, `npm run lint`; the helper is checked with a scratch Node script (no
  frontend test runner).
- Backend unchanged; full pytest suite and ruff check/format as a regression.
