# Deploying for user feedback

**Date:** 2026-11-24

## Where things stood

Live searches work for software, mechanical-engineering and conservation profiles, but the
app was only runnable as a local dev setup:

1. Every request is `TEST_USER` (`accounts.get_current_user`), so testers would share one
   account: each other's resume PDFs, search history, pins and saved parameters.
2. Nothing stops anyone with the URL from running searches that spend Anthropic and Serper
   credits.
3. The frontend reaches the API only through Vite's dev proxy; the backend doesn't serve the
   built frontend. No Dockerfile.
4. Data is the local `database/` folder and live search state is in memory, so the app runs
   as one instance with a persistent disk.

Decisions (owner, 2026-11-24): accounts through **Supabase**, with sign-up gated by
**invite codes**; host as **Docker on a cloud host** with a persistent disk.

## Phase 1: one deployable container (this change)

- `config.FRONTEND_DIST` (default `frontend/dist`). When it exists, `server.py` serves it at
  `/` after the API routes, so one origin serves both and the frontend's relative `/api`
  calls work without a proxy or CORS.
- `Dockerfile` (repo root), multi-stage:
  1. `node` builds the frontend (`npm ci && npm run build`).
  2. `python:3.12-slim` installs `backend/requirements.txt` and, unless
     `--build-arg INSTALL_BROWSER=false`, Playwright's headless Chromium (`read_page`'s
     fallback for postings that need JavaScript; 1.55 GB image with it, 473 MB without).
     Without it `READ_PAGE_BROWSER=false` and such pages are read from static HTML only.
  3. Runs `uvicorn server:app --app-dir src --host 0.0.0.0 --port $PORT`.
  `DATABASE_DIR=/data/database` and `LLM_USAGE_LOG=/data/logs/llm_usage.csv`, so mounting
  one persistent volume at `/data` keeps all state.
- `.dockerignore` keeps `.env`, `node_modules`, `.venv`, captures and logs out of the image.
- Secrets come from the host's environment settings, never the image: `ANTHROPIC_KEY`,
  `SERPER_API_KEY` (**required** in a container: the Chrome fallback needs a desktop
  Google Chrome that the image doesn't have), optional `USAJOBS_API_KEY` +
  `USAJOBS_EMAIL`.
- `config` strips one pair of quotes around environment values: `docker run --env-file`
  and hosting dashboards keep the quotes that python-dotenv removes, which made the
  Anthropic key invalid inside the container.
- `read_page` and `tools` browser workers no longer raise at interpreter exit.
- Deploy notes in `docs/deploy/README.md`.

Verified 2026-11-24: both images build; in the container `/` serves the frontend, a full
search over `POST /api/search` finishes in ~66 s with results, and data in `/data` survives
a restart.

Until Phase 2 ships, the container must not be shared beyond the owner: it has the
`TEST_USER` problem above.

## Phase 2: Supabase accounts + invite codes

Decisions (owner, 2026-11-24): **email + password** sign-in; ship the **slim** image
(`INSTALL_BROWSER=false` is now the default). Supabase project keys are in `.env`.

Design (changed from the first sketch: cookies instead of a Bearer header, invite codes
local instead of a Supabase table):

- **Session in HttpOnly cookies, set by the backend.** Several requests can't carry an
  `Authorization` header (the resume PDF is a plain `<a href>` link), and all calls are
  same-origin, so cookies cover everything with no frontend token handling and no Supabase
  keys in the frontend. Cookies: `na_access` (Supabase access token, its own lifetime) and
  `na_refresh` (30 days), `HttpOnly`, `SameSite=Lax`, `Secure` on HTTPS.
- **Backend service `src/auth/`:**
  - `supabase.py`: the Supabase Auth REST calls (password login, refresh, get user, admin
    create/delete user) with `requests`; no new dependency.
  - `invites.py`: invite codes in `<DATABASE_DIR>/invite_codes.json`
    (`code -> max_uses, uses, note, created_at, used_by`), reserved under a lock before the
    Supabase user is created and released if that fails. CLI:
    `python -m auth.invites create --uses 1 --note alice` / `list` / `revoke CODE`.
  - `session.py`: cookie helpers and a middleware that refreshes an expired access token
    with the refresh cookie and re-sets both cookies on the response (a dependency can't add
    cookies to a `StreamingResponse`). Verified tokens are cached for 60 s so each request
    doesn't wait on Supabase.
- **Endpoints:** `POST /api/auth/signup {email, password, invite_code}` (creates the user
  with `email_confirm: true`: the code already vouches for them, so no confirmation email
  is needed), `POST /api/auth/login`, `POST /api/auth/logout`. `accounts.get_current_user`
  returns the Supabase user (id = Supabase user id, display name = email) or 401.
- **Auth is on when `SUPABASE_URL` is set**; without it (dev, tests) everything is
  `TEST_USER` as before.
- **Frontend:** an auth gate asks `/api/me`; on 401 it shows a sign-in / sign-up page (the
  sign-up form takes the invite code). Any later 401 returns to it. A sign-out button sits
  in the top bar.
- **Owner action:** turn off public sign-ups in Supabase (Authentication -> Sign In /
  Providers -> "Allow new users to sign up"), otherwise anyone with the anon key can
  register directly and skip invite codes. The admin API used by `/api/auth/signup` keeps
  working with it off.
