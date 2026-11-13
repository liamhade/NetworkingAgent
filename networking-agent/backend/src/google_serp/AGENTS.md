# google_serp

Runs Google searches by driving a real Chrome browser, then parses the results page. Results
come from `GET https://www.google.com/search?q=...` as server-rendered HTML. Developer docs:
`networking-agent/docs/google_serp/README.md`. Research write-up:
`networking-agent/docs/google_serp/results.md`.

Moved here from the standalone `find-google-serp-url` repo. Its history is in the parent repo
tag `archive/find-google-serp-url`.

## Layout

- `session.py`: browser, search, `/goto` resolution
- `parser.py`: pure HTML parsing
- `models.py`, `errors.py`
- `cli.py`: `python -m google_serp` (run from `backend/src`)

Public API is exported from `__init__.py`.

```powershell
cd networking-agent\backend\src
..\.venv\Scripts\python.exe -m google_serp "query one" "query two"
..\.venv\Scripts\python.exe -m google_serp "query" --json --no-resolve
cd ..
.\.venv\Scripts\python.exe -m pytest tests\google_serp          # offline; no browser
```

```python
import google_serp

response = google_serp.search("python requests library")

with google_serp.GoogleSerpSession() as serp:  # several queries, one browser
    response = serp.search("playwright python")
```

## Behavior notes

- **Chrome.** Google Chrome must be installed: everything uses `channel="chrome"`, not
  Playwright's bundled Chromium.
- **Chrome profile.** Runs real Chrome with a persistent profile at
  `%LOCALAPPDATA%\google-serp\chrome-profile`. Override it with `GOOGLE_SERP_PROFILE_DIR` or
  `profile_dir=`. The profile holds Google session cookies and CAPTCHA clearance; delete it to
  start a fresh session. Only one process can use it at a time, so don't run two searches in
  parallel.
- **CAPTCHAs.** The window starts off-screen (`hidden=True`) and moves on-screen if a CAPTCHA
  appears. A **person** has 3 minutes to solve it, so run it in the background and ask the
  user. After it's solved, the profile keeps the clearance for later runs.
- **No headless mode or plain HTTP** (`requests`/curl). Plain HTTP gets Google's "enable
  JavaScript" page even with fresh tokens, and headless Chrome is flagged more often.
- **Result links.** They are opaque `/goto?url=...` redirects. With `resolve_urls=True` (the
  default), each one is followed to its real URL. Google throttles this after a few links,
  which adds ~5-25s per search.
- **People searches.** Adding `site:linkedin.com/in` to a query returns mostly individual
  LinkedIn profiles; in testing, 10 of 10 results were profiles.
- **Errors.** `search()` raises by default (`strict=True`). All errors subclass
  `GoogleSerpError`.
- **Parser changes.** When Google's markup changes, update `parser.py` and
  `backend/tests/google_serp/fixtures/results_page.html` together. Don't commit real captured
  pages: they contain session IDs.

## Research scripts (`networking-agent/research/google_serp/`)

These write to `research/google_serp/captures/` (gitignored; the HAR contains session cookies).

```powershell
cd networking-agent
backend\.venv\Scripts\python.exe research\google_serp\capture.py "your query"           # HAR + screenshot
backend\.venv\Scripts\python.exe research\google_serp\get_curl_command.py "your query"  # curl command
```

- Both open a visible Chrome window and wait up to 3 minutes for a **person** to solve a
  CAPTCHA (`/sorry/`, HTTP 429). Run them in the background and ask the user.
- Wait for the `load` state, not `networkidle`. Results pages keep connections open, so
  `networkidle` times out.
- The generated curl command does **not** return results when replayed: Google returns its
  JavaScript challenge page. See `results.md`.
- `minimal_params.py` and `rate_limit.py` replay that curl command. They judge success by
  status code and size, so they can't tell the challenge page from results.
- When the findings change, update `docs/google_serp/results.md`.
