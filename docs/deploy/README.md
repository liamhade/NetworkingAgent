# Deploying the container

Plan and design notes: [plan.md](plan.md).

One container serves the frontend and the API on one origin. Accounts are Supabase email +
password, and only for emails you approve: people request access on the site, then email you
from that address ([access-requests plan](../access-requests/plan.md)).

## Before the first deploy (Supabase dashboard)

1. **Turn off public sign-ups:** Authentication -> Sign In / Providers -> turn off "Allow
   new users to sign up". Otherwise anyone with the project's public anon key can create an
   account directly. The app still won't let them in until you approve the email, but this
   keeps Supabase tidy. The app creates accounts with the admin API, which keeps working with
   this off.
2. Email + password sign-in must stay enabled (it is by default). No email templates are
   needed: accounts are created already confirmed, and you confirm the email yourself.

## Build and run locally

```powershell
# from the repo root
docker build -t networking-agent .                                    # slim (~470 MB), default
docker build -t networking-agent --build-arg INSTALL_BROWSER=true .  # + Chromium (~1.5 GB)
docker run -p 8000:8000 --env-file .env -v networking-agent-data:/data networking-agent
# http://localhost:8000  (frontend and /api on one origin; /api/health for checks)
```

## Approving access requests

1. Someone clicks **Request access** and picks a password. The page then offers a **Send the
   request email** button, which emails `ACCESS_REQUEST_EMAIL` (set it to your inbox) from
   their address.
2. Check that the email really came from the address it asks you to approve, then approve it
   on the **Admin** tab (signed in as `OWNER_EMAIL`), or from a shell:

```powershell
railway ssh -- python -m auth.access list               # pending requests first
railway ssh -- python -m auth.access approve a@x.com    # they can sign in now
railway ssh -- python -m auth.access deny a@x.com       # refuse, or cut off an approved user
```

`approve` (Admin tab: **Add to whitelist**) also works before someone asks: their request is
then approved straight away. The Admin tab's **Remove** is `deny`. `OWNER_EMAIL` is always let
in and can't be removed, so sign up with it first.
Other hosts: run the same `python -m auth.access ...` in their shell (`docker exec <container>`,
Render's Shell tab, `fly ssh console`). Requests are stored in `/data/database/access.json`.
Accounts made with the old invite codes stay approved.

Locally without Docker: `cd backend\src` then `..\.venv\Scripts\python.exe -m auth.access ...`.

## Railway, step by step

1. New Project -> Deploy from GitHub repo -> pick this repo.
2. Railway finds the root `Dockerfile` and builds it. Leave Settings -> Source -> Root
   Directory empty (if it was set to `networking-agent` before, clear it).
3. Service -> Variables: add the variables in the table below (paste from `.env`; `.env.example` lists them), plus
   `MAX_CONCURRENT_SEARCHES=5`. Railway sets `PORT` itself.
4. Right-click the service (or Command Palette) -> **Add Volume**, mount path **`/data`**.
5. Settings -> Networking -> **Generate Domain** (HTTPS). Optional: Settings -> Deploy ->
   Healthcheck Path `/api/health`.
6. Deploys run on every push to `main`. Approve people from your machine with the Railway
   CLI: `railway ssh -- python -m auth.access approve a@x.com` (see above).

## Cloud host (Render, Railway, Fly.io...)

- Build from the root `Dockerfile`. The app listens on `$PORT` (default 8000).
- **Persistent volume at `/data`** (1 GB is plenty): user data (`/data/database`, including
  access requests) and the LLM usage log (`/data/logs`). Without it, every deploy wipes it.
- **One instance only.** Running searches live in the process's memory; don't scale out.
- **HTTPS:** the host's URL is HTTPS, and session cookies are marked `Secure` automatically
  (from `X-Forwarded-Proto`).
- Health check path: `/api/health`.
- Environment variables (set in the host's dashboard, never in the image; quotes around
  values are fine):

| Name | Needed | Notes |
|---|---|---|
| `ANTHROPIC_KEY` | yes | |
| `SERPER_API_KEY` | yes | The Chrome fallback needs desktop Chrome, which the image doesn't have |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | yes | Accounts. Without all three, everyone is `TEST_USER` and no sign-in is asked for: never deploy like that |
| `ACCESS_REQUEST_EMAIL` | yes | Your inbox: people email it from their own address to ask for access. Shown on the sign-in page (public). Unset: the page just says to ask you |
| `OWNER_EMAIL` | yes | Your account email: always approved, and the only account that sees the **Admin** tab (whitelist, every user's LLM usage) |
| `USAJOBS_API_KEY`, `USAJOBS_EMAIL` | optional | Federal jobs board |
| `MAX_CONCURRENT_SEARCHES` | recommended | Default 2: a 3rd simultaneous search gets "too many searches". Measured 2026-11-24: 5 at once took 70-90 s each (vs ~66 s alone), peaking at 229 MB RAM and 0.8 CPU core, so `5` fits a 512 MB instance |
| `LLM_MODEL` | optional | Default `anthropic:claude-haiku-5-5` |
| `COOKIE_SECURE` | optional | `auto` (default), `true` or `false` |

## Why the frontend is in the container (and not on Vercel)

The frontend calls `/api/...` on its own origin and the session lives in `SameSite=Lax`
cookies, so it must be served from the same site as the API. The container already does
that, with nothing to configure. Putting it on Vercel would need a `vercel.json` rewrite of
`/api/*` to the backend, and Vercel's proxy can cut off the ~60-70 s search progress stream.
A CDN buys little for a few testers; revisit when the backend moves to Supabase.
