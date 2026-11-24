# Plan: Searches keep running in the background

TODO item: *"If a user clicks on "Find Opportunities", then looks around at some of the other
pages, they should still be able to find that ongoing search in the "Previous Searches"
panel, even if it hasn't finished yet. Users shouldn't have to wait on a "searching" page."*

## Before

`POST /api/search` ran the pipeline inside the SSE response generator. The search lived and
died with the HTTP connection (abort or navigation closed it), and the record was only written
when the result arrived, so an unfinished search was invisible in the panel and failed
searches were never saved.

## Design

- The search is a **server-side background thread** (`backend/src/search_runs/runner.py`),
  decoupled from any request. `start()` saves a record with `status: "running"` immediately,
  then runs `pipeline.run_search` in a daemon thread.
- Each progress message is appended to the record (`messages`), so progress survives a
  reload. On success the record gets `results`, `trace`, `status: "done"`; on failure
  `status: "error"` and `error: <reason>`. Failed searches are now kept (so a user who left
  can see why it failed).
- Live fan-out: an in-memory `_Run` (event list + `Condition`) per running search. Any number
  of clients can follow it. `attach()` replays from the first event, then streams live; for a
  finished search it replays from the saved record (messages, then result or error), so one
  code path serves "reconnect while running" and "open an old search".
- A run leaves the in-memory registry only after its final record is on disk, so a late
  `attach()` always finds either the live run or the finished record.
- **Restart**: nothing survives a restart, so on startup `history.mark_interrupted()` flips
  every stale `running` record (all users) to `error` ("interrupted because the server
  restarted").
- Quiet SSE streams send `: keepalive` comments every 15s so dead clients are noticed.
- LLM usage logging: the thread sets `usage_context` itself (replaces `bind_context` for
  this endpoint).

## Data model (`schemas.py`)

- `SearchStatus = "running" | "done" | "error"`.
- `SearchSummary.status` (default `done`, so existing files load unchanged).
- `SavedSearch.results` now defaults to empty (empty until done); new `messages: list[str]`
  and `error: str | None`.
- New SSE event `started` (`{search: SearchSummary}`), first event of every stream, so the
  client knows the id and can show the running entry at once.

## Endpoints

- `POST /api/search`: now starts the background run and streams the same events as before
  with `started` first (`started`, `status`*, `result`, `saved` | `error`). Closing the stream
  no longer cancels the search.
- `GET /api/searches/{id}/events` (new): follow a search from its start; 404 if unknown.
- `GET /api/searches` / `GET /api/searches/{id}`: include `status` (and `messages`, `error`).
- `GET /api/entities/*`: only count searches with `status == "done"`.
- On-demand people search on a not-yet-done search: 404 (no companies yet), unchanged code.

## Frontend

- `api.ts`: `streamSearchEvents(id)`; shared SSE reader; `status`/`messages`/`error` types.
- `App.tsx`: one `follow()` consumer for both a fresh search and re-attaching. Navigating to
  Companies/Jobs/People never touches the stream (App stays mounted); "New search"/opening
  another search only detaches the stream, the search keeps running. Opening a running entry
  shows its progress then results; opening a failed one shows its error.
- Searches nobody is watching (reload, other tab, user started another search) are noticed
  finishing by re-listing every 5s while any is `running`; the entity pages refresh when one
  finishes.
- `SearchHistory` bubble: spinner and "Searching…" while running, "Failed" with an icon on
  error.

## Tradeoffs

- Threads + in-memory registry: simple and fits the single-process POC. A multi-worker
  deployment (or Supabase) needs a job queue/worker and a pub-sub channel instead of the
  in-process `Condition`.
- Progress is persisted per message (a small JSON rewrite per step; a handful per search).
- Polling (5s) rather than a global event stream for unwatched searches; cheap and enough.
- No cancel button and no limit on concurrent searches (each uses the one shared Chrome
  worker for Google calls, so concurrent searches queue there).

## Tests

`backend/tests/test_background_search.py` (run without a client, attach live then replay,
failure replay, endpoints while running, unknown id, stale-on-restart), updated streaming
tests in `test_server.py`, `App.test.tsx` (running entry follow, failed entry, survives page
change) and `search-history.test.tsx`. All pipelines are fakes.
