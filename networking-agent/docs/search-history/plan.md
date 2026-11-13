# Plan: Store previous searches (search-history side panel)

TODO item: *"User should see a side-panel on the left of the different searches they've
done, ordered by the most recent. Each chat bubble should have the time it was created,
and a short title."*

Scope addition: there was no account concept at all, and history (plus later per-user
features such as APPLIED/CONNECTED toggles and the Companies/Jobs/People pages) must be
stored per user. So this change also adds a minimal, auth-free account layer.

## Current flow (before)

- `frontend/src/App.tsx` posts the hero form to `POST /api/search` and reads the SSE
  stream (`status` / `result` / `error` events). Nothing is persisted; results live only in
  React state and are lost on refresh or "New search".
- The repo-root `database/` folder exists but is empty.

## Accounts (minimal, Supabase-ready)

- New `backend/src/accounts.py`:
  - `User` model: `id`, `display_name`, `created_at`.
  - Store: `database/users/<user_id>/user.json`.
  - `user_dir(user_id)` is the root for *all* per-user data
    (`database/users/<user_id>/...`); ids are validated so they can't escape `users/`.
  - `seed()` creates the `TEST_USER` record ("Test User"); called at server startup.
  - `get_current_user()` – the single place that decides who is calling. Always returns
    `TEST_USER` for now (creating it if missing). It's a FastAPI dependency
    (`CurrentUser` in `server.py`); every per-user endpoint takes it, so real auth
    (e.g. verifying a Supabase JWT) plugs in there and nowhere else.
- `GET /api/me` returns the current user; the side panel shows the display name.
- No sign-in UI / auth (postponed).

## Search storage

- One JSON file per search at `database/users/<user_id>/searches/<search_id>.json`.
- Record shape (`SavedSearch`): `id` (uuid4 hex), `user_id`, `created_at` (UTC ISO-8601),
  `title`, `request` (the `SearchRequest`), `results` (the `SearchResults`).
- The database root is configurable with `DATABASE_DIR` (tests point it at a tmp dir via an
  autouse fixture, so tests never touch the real folder).
- Only searches that produce a result are saved (failed/aborted runs have nothing to
  reopen). A storage failure is logged and does not hide the results from the user.
- All search storage code lives in `backend/src/history.py`; functions take an explicit
  `user_id`, so swapping to Supabase only touches `accounts.py` / `history.py`.

## Title

Derived locally, no LLM call: take the first sentence of "What you're looking for", strip
filler such as "I'm looking for", capitalise, cap at ~40 characters on a word boundary,
and append ` · <location>` when a location was given (e.g. "Data analyst roles · NYC").

## API

- `GET /api/me` – current `User`.
- `POST /api/search` – unchanged, plus a new `saved` SSE event (carrying the
  `SearchSummary`) emitted right after the `result` event once the search is persisted.
- `GET /api/searches` – `SearchSummary[]` (`id`, `title`, `created_at`), newest first.
- `GET /api/searches/{id}` – full `SavedSearch`; 404 if unknown (ids are validated as
  32-char hex).

## Frontend

- New `components/search-history.tsx`: a left side panel (sticky, full height, hidden
  below the `md` breakpoint) with a "New search" button, a scrollable list of bubbles
  (title + created time; "3:41 PM" today, "Yesterday, …", else "Nov 3, …"; full date on
  hover), the active one highlighted, and the current user's name at the bottom. Uses the
  BoardUI `scroll-fade` registry item for the scroll region, per the design rules.
- `App.tsx` loads the user and the list on mount, prepends the entry when a `saved` event
  arrives, and on click fetches `/api/searches/{id}` and shows it on the existing results
  page (the form is restored too, so "New search" starts from the same inputs).

## Verification

- Backend pytest: history + accounts unit tests and endpoint tests through `TestClient`
  with a mocked agent (no paid/external calls); ruff check/format.
- Live smoke test: uvicorn with a mocked agent and a scratch `DATABASE_DIR`, exercised
  with curl.
- `npm run build` (tsc + vite) and `npm run lint` in `frontend/`.
