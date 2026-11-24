# Deploying the container

Plan and open work: [plan.md](plan.md).

> **Not ready for outside testers yet.** Until Supabase accounts and invite codes ship
> (plan.md, Phase 2), every visitor is `TEST_USER`: they share one resume, search history and
> pins, and anyone with the URL can spend API credits.

## Build and run locally

```powershell
cd networking-agent
docker build -t networking-agent .                                  # with Chromium (~1.5 GB)
docker build -t networking-agent --build-arg INSTALL_BROWSER=false .  # without it (smaller)
docker run -p 8000:8000 --env-file .env -v networking-agent-data:/data networking-agent
# http://localhost:8000  (frontend and /api on one origin; /api/health for checks)
```

## Cloud host (Render, Railway, Fly.io...)

- Build from `networking-agent/Dockerfile`. The app listens on `$PORT` (default 8000).
- **Persistent volume at `/data`** (1 GB is plenty): user data (`/data/database`) and the
  LLM usage log (`/data/logs`). Without it, every deploy wipes all users' data.
- **One instance only.** Running searches live in the process's memory; don't scale out.
- Health check path: `/api/health`.
- Environment variables (set in the host's dashboard, never in the image):

| Name | Needed | Notes |
|---|---|---|
| `ANTHROPIC_KEY` | yes | |
| `SERPER_API_KEY` | yes | The Chrome fallback needs desktop Chrome, which the image doesn't have |
| `USAJOBS_API_KEY`, `USAJOBS_EMAIL` | optional | Federal jobs board |
| `LLM_MODEL` | optional | Default `anthropic:claude-haiku-5-5` |

`CORS_ORIGINS` doesn't matter in the container: the frontend is served from the same origin.
