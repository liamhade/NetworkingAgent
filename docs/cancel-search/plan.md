# Plan: Cancel a running search, and cap concurrent searches

TODO item: *"Add a Cancel button for a running search in the Previous Searches panel, and cap
how many searches can run at the same time."* Builds on `docs/background-searches/plan.md`.

## Cancel

- **Cooperative.** Each live run has a `cancel_requested` `threading.Event`. The worker thread
  checks it after every event the pipeline yields (one per step status), and when set it
  returns; its `finally` closes the pipeline generator, so LangGraph stops at the step it is
  in. A Google/LLM call already in flight finishes first and its output is discarded
  (a Python thread cannot be killed safely).
- **Immediate for the user.** `search_runs.cancel()` does not wait for the worker: it saves the
  record as `status: "cancelled"`, publishes a `cancelled` event (which ends every followed
  stream) and finishes the run. The worker winds down on its own.
- **No done -> cancelled races.** A per-run `settle` lock + `settled` flag: whoever settles the
  run first (worker with a result/error, or `cancel`) wins. A result arriving after a cancel
  is thrown away; cancelling a search that just finished gets 409.
- **Status.** `SearchStatus` gains `cancelled`. Cancelled searches keep their progress
  messages, have no results, are excluded from entity pages (`only_done`), and replay as
  `started, status*, cancelled`.
- **Endpoint.** `POST /api/searches/{id}/cancel` returns the `SearchSummary` (200); 404 for an
  unknown id (or another user's); 409 if the search is not running (done, failed, already
  cancelled, or orphaned).
- **Event.** New SSE event `cancelled` (`{search: SearchSummary}`), always the last event.

## Concurrency cap

- `config.MAX_CONCURRENT_SEARCHES` (env var, default 2, minimum 1), counted across all users
  (they share one Chrome worker and one LLM rate limit).
- **Refuse, not queue.** `POST /api/search` returns **429** with a clear message ("2 searches
  are already running (the limit is 2). Wait for one to finish or cancel one, then try
  again."). Nothing is saved for a refused search. Why not a queue: a waiting search would need
  a new `queued` status, ordering, a restart story and UI for it, none of which is trivial;
  refusing keeps the user in control and the message tells them what to do.
- The check and the registration happen under one lock, so two simultaneous starts cannot both
  take the last slot.
- A cancelled search still winding down does not count, so Cancel frees a slot at once. This
  can briefly exceed the cap by the number of winding-down runs (each stops at its next step).

## Frontend

- `api.ts`: `cancelSearch(id)`, `cancelled` status and event.
- `SearchHistory`: running bubbles get a **Cancel** button (BoardUI `Button`, ghost, xs, with
  an icon; a sibling of the select button, not nested in it). Cancelled searches show a
  "Cancelled" marker. `cancelError` shows why a cancel failed.
- `App`: `cancel()` updates the entry from the response; on failure (e.g. 409) it shows the
  message and re-lists searches. A followed stream's `cancelled` event updates the entry and
  shows "This search was cancelled." on the results page; opening a cancelled search shows
  its progress and that message. A refused start (429) shows the server message in the
  existing search error area.

## Tests (all fakes, no network)

`backend/tests/test_cancel_search.py`: cancel saves status and discards the late result;
streams end cleanly with `cancelled` (live and replayed); pipeline stops at the next step and
is closed; 404/409 (unknown, finished, cancelled twice, other user); 429 at the cap with
nothing saved; Cancel frees the slot; cap spans users. Frontend: `search-history.test.tsx`
(Cancel only on running, which id, does not select, "Cancelled" marker, error) and
`App.test.tsx` (cancel from panel, refused cancel, followed stream ends on `cancelled`).

## Not included

Deleting searches (separate task); a wait queue; cancelling from the results page.
