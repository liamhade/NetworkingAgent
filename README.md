# Networking Agent

Type in your background, where you live and what you're looking for (or upload a resume
PDF), and the agent returns companies to research, open jobs, and people to network
with, each with a note on how you align. Design: [docs/v1/plan.md](docs/v1/plan.md).

- `backend/`: FastAPI + a LangGraph search pipeline (Python 3.11, `backend/src/pipeline/`,
  plan: [docs/langgraph-pipeline/plan.md](docs/langgraph-pipeline/plan.md)). Its data
  sources (`backend/src/tools.py`) wrap `builtin_nyc` (BuiltInNYC jobs/companies),
  `conservation_jobboard`, `read_page` and `google_serp` (Google search through Chrome,
  used for LinkedIn people and non-NYC jobs). Per-user data
  (accounts, search history, APPLIED/CONNECTED statuses) lives in `backend/src/userdata/`;
  stable job/person/company keys in `backend/src/entities/keys.py`.
- `research/`: scripts used to reverse-engineer those two sites (not used at runtime).
- `docs/`: plans, plus module docs (`docs/google_serp/`, `docs/builtin_nyc/`).
- `frontend/`: Vite + React + TypeScript, styled with the Map · Linen theme (`src/styles/linen.css`).

## Setup

Copy `.env.example` to `.env` (repo root). It needs an Anthropic key at least:

```
ANTHROPIC_KEY=sk-ant-...
# optional: any LangChain "<provider>:<model>" string
LLM_MODEL=anthropic:claude-haiku-5-5
```

Google Chrome must be installed (see `docs/google_serp/README.md`). If Google
shows a CAPTCHA, the Chrome window comes on-screen and someone has 3 minutes to solve it.

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

cd ..\frontend
npm install
```

## Deploy

One Docker container (frontend + API), accounts and approving access requests: [docs/deploy/README.md](docs/deploy/README.md).

## Run

```powershell
# terminal 1
cd backend
.\.venv\Scripts\python.exe -m uvicorn server:app --app-dir src --port 8000

# terminal 2
cd frontend
npm run dev          # http://localhost:3000 (proxies /api to :8000)
```

## Test

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest      # offline, no LLM or browser
.\.venv\Scripts\ruff.exe check .

cd ..\frontend
npm run build
```

## Settings (environment variables)

| Name | Default | Meaning |
|---|---|---|
| `LLM_MODEL` | `anthropic:claude-haiku-5-5` | Model used by the agent and resume parser |
| `ANTHROPIC_KEY` / `ANTHROPIC_API_KEY` | | API key (`<PROVIDER>_KEY` works for other providers) |
| `MAX_COMPANIES` | `6` | Companies a search returns, ranked by fit (0-100) |
| `PEOPLE_AUTO_COMPANIES` | `3` | Top-ranked companies that get a people search automatically |
| `PEOPLE_PER_COMPANY` | `3` | People-search ladder stops at this many current employees |
| `PEOPLE_SEARCH_N` | `5` | Profiles asked for per people search |
| `READ_POSTINGS` | `2` | Job postings read in full for the results (0 = off) |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | | Accounts (email + password, for emails you approve). Unset: everyone is `TEST_USER` |
| `ACCESS_REQUEST_EMAIL` | | Your inbox: people email it from their address to request access (`python -m auth.access approve <email>`) |
| `OWNER_EMAIL` | | Your account email: always allowed in, and the only account that sees the **Admin** tab (whitelist, every user's LLM usage) |
| `LOCAL_DEV_MODE` | `false` | `true`: the sign-in page stays, but any credentials sign in as TEST_USER (no Supabase). Localhost only; never on a host. See `docs/local-dev-mode/plan.md` |
| `SERPER_API_KEY` / `SERPAPI_API_KEY` | | Google results from serper.dev / serpapi.com instead of Chrome (no CAPTCHAs, ~1-2 s) |
| `GOOGLE_RESOLVE_URLS` | `true` | Follow Google redirects to real URLs (slower) |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed browser origins |
