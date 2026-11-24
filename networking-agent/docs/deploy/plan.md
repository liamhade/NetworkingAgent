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
- `networking-agent/Dockerfile`, multi-stage:
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

## Phase 2: Supabase accounts + invite codes (needs the owner's Supabase project)

- **Login:** the frontend signs in with `@supabase/supabase-js` (email magic link or
  password) and sends `Authorization: Bearer <access token>` on every `/api` call.
- **Backend:** `accounts.get_current_user` verifies the JWT (Supabase JWKS, or the project's
  JWT secret), and the Supabase user id (`sub`) becomes the user id. All per-user data keeps
  its current layout under `database/users/<id>/`, so nothing else changes; moving the data
  itself to Supabase tables is a later step.
- **Invite codes:** a Supabase table `invite_codes(code, max_uses, uses, note, created_at)`.
  Sign-up goes through `POST /api/signup {email, invite_code}`: the backend checks and
  consumes the code with the service-role key and creates the user through the Supabase
  Admin API, so nobody can register without a code. Codes are made with a small CLI
  (`python -m userdata.invites create --uses 1 --note "alice"`).
- Unauthenticated requests get 401 except `/api/health`; that also closes the credit leak.
- Needs from the owner: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (frontend),
  `SUPABASE_SERVICE_ROLE_KEY` (backend only), and the email sign-in settings.
