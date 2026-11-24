# Deploying the container

Plan and design notes: [plan.md](plan.md).

One container serves the frontend and the API on one origin. Accounts are Supabase email +
password; signing up needs an invite code that you hand out.

## Before the first deploy (Supabase dashboard)

1. **Turn off public sign-ups:** Authentication -> Sign In / Providers -> turn off "Allow
   new users to sign up". Otherwise anyone with the project's public anon key can create an
   account directly and skip invite codes. The app creates accounts with the admin API, which
   keeps working with this off.
2. Email + password sign-in must stay enabled (it is by default). No email templates are
   needed: invited accounts are created already confirmed.

## Build and run locally

```powershell
cd networking-agent
docker build -t networking-agent .                                    # slim (~470 MB), default
docker build -t networking-agent --build-arg INSTALL_BROWSER=true .  # + Chromium (~1.5 GB)
docker run -p 8000:8000 --env-file .env -v networking-agent-data:/data networking-agent
# http://localhost:8000  (frontend and /api on one origin; /api/health for checks)
```

## Invite codes

```powershell
docker exec <container> python -m auth.invites create --note "alice"           # one sign-up
docker exec <container> python -m auth.invites create --uses 10 --note "beta"  # ten sign-ups
docker exec <container> python -m auth.invites list
docker exec <container> python -m auth.invites revoke ABCD-EFGH
```

On a cloud host use its shell / console (Render: Shell tab; Railway: `railway ssh`; Fly:
`fly ssh console`) and run the same `python -m auth.invites ...`. Codes are stored in
`/data/database/invite_codes.json`, with who used them. Codes are case-insensitive.

Locally without Docker: `cd backend\src` then `..\.venv\Scripts\python.exe -m auth.invites ...`.

## Cloud host (Render, Railway, Fly.io...)

- Build from `networking-agent/Dockerfile`. The app listens on `$PORT` (default 8000).
- **Persistent volume at `/data`** (1 GB is plenty): user data (`/data/database`, including
  invite codes) and the LLM usage log (`/data/logs`). Without it, every deploy wipes it.
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
| `USAJOBS_API_KEY`, `USAJOBS_EMAIL` | optional | Federal jobs board |
| `LLM_MODEL` | optional | Default `anthropic:claude-haiku-5-5` |
| `COOKIE_SECURE` | optional | `auto` (default), `true` or `false` |

## Why the frontend is in the container (and not on Vercel)

The frontend calls `/api/...` on its own origin and the session lives in `SameSite=Lax`
cookies, so it must be served from the same site as the API. The container already does
that, with nothing to configure. Putting it on Vercel would need a `vercel.json` rewrite of
`/api/*` to the backend, and Vercel's proxy can cut off the ~60-70 s search progress stream.
A CDN buys little for a few testers; revisit when the backend moves to Supabase.
