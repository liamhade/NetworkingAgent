# Plan: Delete a search from Previous Searches

TODO item: *"Failed searches stay in the Previous Searches panel marked 'Failed'. Add a way to
delete a search (failed or otherwise) from the panel."* Builds on `docs/cancel-search/plan.md`.

## Backend

- `history.delete_search(user_id, search_id)` removes the JSON file under the per-search lock
  (the same lock as `update_search`), so a late worker write or on-demand people search finds
  no record and cannot resurrect the file. Returns False if unknown or the id is malformed.
- **Running searches are refused**: `history.SearchRunning` -> `DELETE /api/searches/{id}`
  returns **409** ("That search is still running. Cancel it before deleting."). Why not
  cancel-then-delete: a destructive action should not also have a hidden side effect; Cancel
  already exists and frees the slot at once, so "cancel, then delete" is two deliberate clicks
  and keeps the live-run bookkeeping in `search_runs` untouched.
- 204 on success; 404 for an unknown id or another user's.
- Entities come from saved searches, so the search's companies/jobs/people disappear from the
  Companies/Jobs/People pages unless another search has them. Applied/connected marks and pins
  are keyed by entity id and are deliberately left alone (they reappear if the entity is found
  again).

## Frontend

- `api.ts`: `deleteSearch(id)`.
- `SearchHistory`: every row except running ones gets a trash icon button (BoardUI ghost `xs`
  `Button`, `RiDeleteBinLine`); clicking shows an inline "Delete this search? Keep / Delete"
  confirm (same pattern as saved search configurations). `deleteError` is shown in the panel.
- `App.remove()`: on success drops the row, refreshes entity pages, and if the deleted search
  is the one open, returns to the new-search view (`back()`). On failure shows the message and
  re-lists searches.

## Tests (mocks only)

`backend/tests/test_delete_search.py`; `search-history.test.tsx` and `App.test.tsx`.
