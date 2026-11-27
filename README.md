# Networking Agent

Type in your background, where you live and what you're looking for (or upload a resume
PDF), and the agent returns a ranked list of open jobs (best fit first, each with a score,
a reason and how you align), with the people to network with at each job's company. Design: [docs/v1/plan.md](docs/v1/plan.md).

- `backend/`: FastAPI + a LangGraph search pipeline (Python 3.11, `backend/src/pipeline/`,
  plan: [docs/langgraph-pipeline/plan.md](docs/langgraph-pipeline/plan.md)). Its data
  sources (`backend/src/tools.py`) wrap `builtin_nyc` (BuiltInNYC jobs/companies),
  `conservation_jobboard`, `read_page` and `google_serp` (Google search through Chrome,
  used for LinkedIn people and non-NYC jobs). Per-user data
  (accounts, search history, APPLIED/CONNECTED statuses) lives in `backend/src/userdata/`;
  stable job/person/company keys in `backend/src/entities/keys.py`.
- Pipeline: `plan → find_jobs → filter → rank_jobs → find_people → compile`. `filter` is code
  (dedupe, location, years of experience, cap at `RANK_MAX_JOBS`) and reads each remaining
  posting; `rank_jobs` scores them on `RANK_MODEL`; the results page is one ranked card per
  job. Plan: [docs/job-ranking/plan.md](docs/job-ranking/plan.md).
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
| `MAX_JOBS` | `12` | Jobs a search returns: the ranker's best, by fit score (0-100), with no per-company cap |
| `RANK_MAX_JOBS` | `30` | Jobs that pass the filter, get their posting read and are ranked |
| `RANK_MODEL` | `anthropic:claude-sonnet-5-5` | Model for the `rank_jobs` step (one call per search; `LLM_MODEL` runs the rest) |
| `PEOPLE_AUTO_COMPANIES` | `3` | First companies, in job rank order, that get a people search automatically; others use the button |
| `PEOPLE_PER_COMPANY` | `3` | People-search ladder stops at this many current employees |
| `PEOPLE_SEARCH_N` | `5` | Profiles asked for per people search |
| `PEOPLE_SIMILAR_MAX_QUERIES` | `2` | Extra Google searches per company for people from the user's school (`0` turns it off) |
| `PEOPLE_SIMILAR_PER_COMPANY` | `2` | That search stops once this many people with a shared school were found |
| `ATS_MAX_BOARDS` | `6` | Most ATS boards (Greenhouse, Lever, Ashby, Workable) fetched per search (`0` turns ATS off) |
| `ATS_JOBS_PER_BOARD` | `4` | Matching postings kept from each ATS board |
| `ATS_RESOLVE_LINKS` | `3` | Google links resolved per ATS board search when the board isn't visible in the result |
| `USAJOBS_API_KEY`, `USAJOBS_EMAIL` | | Free USAJOBS key and the email it was registered with; unset skips federal jobs |
| `USAJOBS_MAX_QUERIES` | `2` | Most USAJOBS searches per run (`0` turns it off) |
| `USAJOBS_RESULTS` | `10` | Jobs kept from each USAJOBS search |
| `LINKEDIN_MESSAGE_MAX_CHARS` | `300` | Upper bound on each example LinkedIn connection note |
| `MAX_CONCURRENT_SEARCHES` | `2` | Searches that may run at once; another is refused with HTTP 429 |
| `READ_TIMEOUT_S` | `8` | Seconds a batch of page reads may take; slower pages are skipped |
| `READ_BUDGET_S` | `20` | Seconds all posting reads of the `filter` step may take; unread jobs keep their card text |
| `READ_HOST_CONCURRENCY` | `5` | Posting reads of one site at once |
| `READ_RETRY_BACKOFF_S` | `1.5` | Wait before the one retry of a read that got HTTP 429 |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | | Accounts (email + password, for emails you approve). Unset: everyone is `TEST_USER` |
| `ACCESS_REQUEST_EMAIL` | | Your inbox: people email it from their address to request access (`python -m auth.access approve <email>`) |
| `OWNER_EMAIL` | | Your account email: always allowed in, and the only account that sees the **Admin** tab (whitelist, every user's LLM usage) |
| `LOCAL_DEV_MODE` | `false` | `true`: the sign-in page stays, but any credentials sign in as TEST_USER (no Supabase). Localhost only; never on a host. See `docs/local-dev-mode/plan.md` |
| `SERPER_API_KEY` / `SERPAPI_API_KEY` | | Google results from serper.dev / serpapi.com instead of Chrome (no CAPTCHAs, ~1-2 s) |
| `GOOGLE_RESOLVE_URLS` | `true` | Follow Google redirects to real URLs (slower) |
| `GOOGLE_CACHE_TTL_S` | `900` | Seconds a Google results page is reused for a repeated query (`0` turns the cache off) |
| `DATABASE_DIR` | `./database` | Local JSON store (gitignored, personal data) |
| `COOKIE_SECURE` | `auto` | Session cookies' `Secure` flag: `auto`, `true` or `false` |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed browser origins |
