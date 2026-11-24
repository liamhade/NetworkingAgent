# google_serp

Search Google from Python and get structured results: titles, real destination URLs, site names
and snippets. It is the backend of the agent's `google_search` and `linkedin_people` tools
(`backend/src/tools.py`), and is kept to exactly what those tools need.

It drives a real Chrome browser with a persistent profile. Google's session cookies, including
CAPTCHA clearance, stay in that profile, so if Google shows a CAPTCHA a person only has to solve
it once.

> Google's terms of service don't allow automated querying of its search pages. Use this for
> research, at low volume. For production use, consider an official or commercial search API
> (see [results.md](results.md#alternatives)).

## Requirements

- Google Chrome installed (the package uses your installed Chrome, not Playwright's bundled
  Chromium)
- The backend's requirements (`backend/requirements.txt`), with `backend/src` on the path (the
  backend's pytest config and `uvicorn --app-dir src` already do this)

The package lives at `backend/src/google_serp/` (moved from the standalone
`find-google-serp-url` repo; old history is in the parent repo tag
`archive/find-google-serp-url`).

## Usage

```python
from google_serp import GoogleSerpSession

session = GoogleSerpSession().start()
try:
    response = session.search("python requests library")
    chosen = response.results[:3]
    session.resolve_results(chosen)          # real URLs for only these results
    for result in chosen:
        print(result.title, result.url, result.site_name)
finally:
    session.close()
```

In the app, `tools._GoogleWorker` owns the one session: it runs every search on a single thread,
caches results pages for `GOOGLE_CACHE_TTL_S` (15 minutes by default), and resolves only the
results a tool returns.

## How it behaves

- **Browser window.** Chrome runs headed, because headless Chrome is flagged more often. Its
  window starts off-screen and moves on-screen if Google shows a CAPTCHA. Someone then has
  3 minutes to solve it, after which `CaptchaTimeoutError` is raised.
- **Profile location.** `%LOCALAPPDATA%\google-serp\chrome-profile` (or
  `~/.local/share/google-serp/chrome-profile` where `LOCALAPPDATA` isn't set). Override it with
  the `GOOGLE_SERP_PROFILE_DIR` environment variable. Delete the folder to start a fresh session.
  Only one process can use a profile at a time.
- **Real URLs cost extra time.** Google links every result through an opaque `/goto?url=...`
  redirect, and the real URL isn't in the page. `search()` leaves `url` as that redirect link;
  `resolve_results(results)` follows each one inside the browser session and replaces `url` in
  place (the redirect link stays in `google_url`). Google throttles this after a few links,
  which adds about 5–25 s per search, so resolve only the results you will use. See
  `docs/google-serp-speed/findings.md`.
- **First page only.** `search()` fetches the first results page (about 10 results).
- **Errors.** `search()` raises on failure; it never returns an empty response in place of an
  error.
- **No plain-HTTP mode.** `requests`/curl get Google's "enable JavaScript" page even with fresh
  cookies, so there is no browser-free option.

## API

| Name | Description |
|---|---|
| `GoogleSerpSession()` | `.start()`, `.close()`, `.search(query) -> SearchResponse`, `.resolve_results(results)` |
| `SearchResponse` | `.results: list[SearchResult]`, `.query` |
| `SearchResult` | `title`, `url`, `display_url`, `snippet`, `site_name`, `google_url` |
| `CaptchaTimeoutError` | A CAPTCHA was not solved within 3 minutes |
| `parser.parse_results(html)` | Parse saved results-page HTML (no browser) |
| `parser.is_google_redirect(url)` | True for Google `/goto` and `/url` links |

## Development

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\google_serp tests\test_google_worker.py
```

The tests use a hand-written fixture page (`backend/tests/google_serp/fixtures/results_page.html`)
and don't open a browser. Google changes its markup often. When parsing breaks, compare a live
page with the fixture, then update `backend/src/google_serp/parser.py` and the fixture together.
Don't commit real captured pages: they contain session IDs.

## Layout

Paths are relative to the repo root.

```
backend/src/google_serp/     the package
  session.py                 Chrome session, search, /goto resolution, CaptchaTimeoutError
  parser.py                  HTML -> SearchResult list (pure, no browser)
  models.py                  SearchResult, SearchResponse
backend/tests/google_serp/   pytest suite (no network)
research/google_serp/        scripts used to find the endpoint (see results.md)
docs/google_serp/results.md  research write-up
```
