# Networking Agent v1: implementation plan

Implements [task.md](task.md). Everything lives in `networking-agent/`; the two sibling
modules (`find-google-serp-url`, `built-in-nyc-api`) are used as-is, not modified.

## Architecture

```
React (Vite) ──POST /api/resume (PDF)──────────▶ FastAPI ──▶ resume.py ──▶ LLM (structured)
             ──POST /api/search (SSE stream)───▶ FastAPI ──▶ agent.py
                                                              │  LangChain create_agent (tool loop)
                                                              ├─ search_builtin_jobs      ─▶ built-in-nyc-api.get_jobs
                                                              ├─ search_builtin_companies ─▶ built-in-nyc-api.get_companies
                                                              ├─ google_search            ─▶ google_serp (Chrome)
                                                              └─ find_people              ─▶ google_serp, site:linkedin.com/in
                                                              ▼
                                                    compile step: LLM structured output → SearchResults
```

## Backend (`backend/`)

Python 3.11 virtual environment at `backend/.venv`.

| File | Purpose |
|---|---|
| `requirements.txt` | Dependencies; `google-serp` installed editable from `../../find-google-serp-url` |
| `pyproject.toml` | Ruff + pytest config (`pythonpath = ["src"]`) |
| `src/config.py` | Loads `networking-agent/.env`; settings (`LLM_MODEL`, API key, CORS origins) |
| `src/llm.py` | `get_llm()`: model-agnostic `init_chat_model("<provider>:<model>")`. Default `anthropic:claude-haiku-5-5`. Reads `ANTHROPIC_KEY` (or `ANTHROPIC_API_KEY`) |
| `src/schemas.py` | Pydantic models for requests, results, and SSE events |
| `src/tools.py` | LangChain tools wrapping the two modules. `built-in-nyc-api/src` is added to `sys.path` (it is a flat module, not a package). Google searches run on one dedicated worker thread that owns a reusable `GoogleSerpSession` (Playwright sync API is thread-bound; the profile allows one process at a time) |
| `src/resume.py` | PDF → text (`pypdf`) → LLM structured output → `{background, location, looking_for}` |
| `src/agent.py` | Builds the LangChain agent; `run_search()` yields progress events while the agent runs, then a compile step turns the transcript into `SearchResults` |
| `src/server.py` | FastAPI app: `GET /api/health`, `POST /api/resume`, `POST /api/search` (Server-Sent Events) |
| `tests/` | Offline pytest suite: tools (mocked modules), resume parsing, agent event flow (fake LLM), server endpoints |

### Structured output

Haiku 5.5 runs with thinking on, which does not allow forced tool choice, so all
structured output uses `with_structured_output(..., method="json_schema")` (native
structured outputs) instead of forced tool calls. The agent loop itself has no
`response_format`; a separate compile call produces the final JSON. This also keeps
the code portable to other providers.

### Result schema

```
SearchResults
  summary: str
  companies: [CompanyResult]
    name, url, description, alignment
    jobs:   [JobResult    {title, url, location, salary, alignment}]
    people: [PersonResult {name, title, profile_url, alignment}]
```

`alignment` is the text shown in the expandable green box.

### Agent strategy (system prompt)

1. Infer target roles, industries and seniority from the profile.
2. `search_builtin_jobs` (BuiltInNYC covers NYC and remote roles); `google_search` for
   job postings when the user is outside NYC or BuiltIn is thin.
3. `search_builtin_companies` for hiring companies in matching industries.
4. Pick 3–5 best-fit companies; `find_people` at each (relevant team + recruiters).
5. Stop. Never invent URLs, names or postings: only use tool output.

Limits: `recursion_limit` caps the loop; tool outputs are compact JSON with truncated
descriptions.

### SSE events

`{"type": "status", "message": "..."}` for each tool call/result,
`{"type": "result", "data": SearchResults}` at the end, `{"type": "error", "message": "..."}`.

## Frontend (`frontend/`)

Vite + React 19 + TypeScript + Tailwind CSS v4 + BoardUI components
(`npx boardui@latest init/add --yes`). `@/` path alias, Inter font via `@fontsource-variable/inter`.

| Piece | Purpose |
|---|---|
| `src/api.ts` | `parseResume(file)`, `streamSearch(request, onEvent)` (fetch + SSE parsing) |
| `src/pages/Hero.tsx` | Background / location / looking-for fields; optional PDF upload fills the fields |
| `src/pages/Results.tsx` | Progress log while running; then a simple list of companies → jobs → people |
| `src/components/AlignmentBox.tsx` | Expandable green "how you align" box |
| `vite.config.ts` | Dev proxy `/api` → `http://localhost:8000` |

## Verification

- `pytest` and `ruff check` pass in `backend/`.
- `npm run build` (tsc + vite) passes in `frontend/`.
- Smoke test: start uvicorn, hit `/api/health`, POST a generated PDF to `/api/resume`,
  and run one live `/api/search`.

## Running

```powershell
cd networking-agent\backend
.\.venv\Scripts\python.exe -m uvicorn server:app --app-dir src --reload --port 8000

cd networking-agent\frontend
npm run dev
```
