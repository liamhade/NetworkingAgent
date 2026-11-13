# google-serp

Search Google from Python and get structured results: titles, real destination URLs, site names, snippets, and the result count.

It drives a real Chrome browser with a persistent profile. Google's session cookies, including CAPTCHA clearance, stay in that profile, so if Google shows a CAPTCHA a person only has to solve it once.

> Google's terms of service don't allow automated querying of its search pages. Use this for research, at low volume. For production use, consider an official or commercial search API (see [results.md](results.md#alternatives)).

## Requirements

- Python 3.10+
- Google Chrome installed (the package uses your installed Chrome, not Playwright's bundled Chromium)

## Install

The package lives in the Networking Agent backend at `networking-agent/backend/src/google_serp/`
(moved from the standalone `find-google-serp-url` repo; old history is in the parent repo tag
`archive/find-google-serp-url`). It isn't installed separately: install the backend's
requirements (`backend/requirements.txt`) and run code with `backend/src` on the path (the
backend's pytest config and `uvicorn --app-dir src` already do this).

## Usage

### Python

```python
import google_serp

response = google_serp.search("python requests library")

print(response.metadata.results_count)   # "About 10,500 results"
for result in response.results:
    print(result.position, result.title)
    print("  ", result.url)              # real destination URL
    print("  ", result.site_name)        # e.g. "Stack Overflow"
```

For several queries, open one session so Chrome starts only once:

```python
from google_serp import GoogleSerpSession

with GoogleSerpSession() as serp:
    for query in ["python requests", "playwright python"]:
        response = serp.search(query)
        print(query, len(response.results))
```

To parse a results page you already have (no browser needed):

```python
from google_serp import parse_results_page

response = parse_results_page(html, query="python requests library")
```

### Command line

Run from `networking-agent/backend/src`:

```powershell
..\.venv\Scripts\python.exe -m google_serp "python requests library"
..\.venv\Scripts\python.exe -m google_serp "query one" "query two" --json > results.json
..\.venv\Scripts\python.exe -m google_serp "python requests library" --no-resolve
```

| Option | Effect |
|---|---|
| `--json` | Print a JSON list with one object per query |
| `-n, --limit N` | Results to print per query in text mode (default 10) |
| `-p, --page N` | Results page to start at, 10 results per page (default 1) |
| `--pages N` | Fetch N consecutive pages per query (default 1); `--json` prints one object per page |
| `--no-resolve` | Keep Google's `/goto` redirect links (faster) |
| `--show-window` | Keep the Chrome window on-screen |
| `--profile-dir DIR` | Use a different Chrome profile |
| `-v, --verbose` | Debug logging |

## How it behaves

- **Browser window.** Chrome runs headed, because headless Chrome is flagged more often. Its window starts off-screen (`hidden=True`) and moves on-screen if Google shows a CAPTCHA. Someone then has 3 minutes to solve it (`captcha_timeout=`), after which `CaptchaTimeoutError` is raised. Pass `hidden=False` or `--show-window` to keep the window visible.
- **Profile location.** Defaults to `%LOCALAPPDATA%\google-serp\chrome-profile` on Windows, `~/Library/Application Support/google-serp/chrome-profile` on macOS, and `~/.local/share/google-serp/chrome-profile` on Linux. Override it with `profile_dir=` or the `GOOGLE_SERP_PROFILE_DIR` environment variable. Delete the folder to start a fresh session. Only one process can use a profile at a time.
- **Real URLs cost extra time.** Google links every result through an opaque `/goto?url=...` redirect, and the real URL isn't in the page. With `resolve_urls=True` (the default), each link is followed inside the browser session. Google throttles this after a few links, which adds about 5–25s per search. With `resolve_urls=False`, `url` is the redirect link. The redirect link is always kept in `result.google_url`. Resolving is ~95% of a search's time, so resolve only the results you will use: pass `resolve_limit=n`, or search with `resolve_urls=False` and call `session.resolve_results(chosen)`. See `docs/google-serp-speed/findings.md`.
- **Pagination.** `page=` is 1-based and maps to Google's `start=(page-1)*10`. `result.position` restarts at 1 on each page; `response.metadata.page` says which page it came from. Reuse one `GoogleSerpSession` to walk several pages: `[serp.search(q, page=p) for p in (1, 2, 3)]`. Google may CAPTCHA or stop returning results on deep pages.
- **Errors.** `search()` raises by default. Pass `strict=False` to log the error and get an empty response instead. All package errors subclass `GoogleSerpError`.
- **No plain-HTTP mode.** `requests`/curl get Google's "enable JavaScript" page even with fresh cookies, so there is no browser-free option.

## API

| Name | Description |
|---|---|
| `search(query, *, page=1, resolve_urls=True, hidden=True, profile_dir=None, strict=True)` | One search; starts and closes Chrome |
| `GoogleSerpSession(profile_dir=None, hidden=True, captcha_timeout=180, language="en")` | Reusable session; `.search(query, resolve_urls=True, page=1, resolve_limit=None)`, `.fetch_html(query, page=1)`, `.resolve_results(results)`, `.resolve_url(url)` |
| `parse_results_page(html, query)` | Parse saved HTML into a `SearchResponse` |
| `SearchResponse` | `.results: list[SearchResult]`, `.metadata: SearchMetadata`, `.to_dict()` |
| `SearchResult` | `title`, `url`, `display_url`, `snippet`, `site_name`, `google_url`, `position` |
| `SearchMetadata` | `query`, `results_count`, `search_time` |

## Development

```powershell
cd networking-agentackend
.\.venv\Scripts\python.exe -m pytest tests\google_serp
```

The tests use a hand-written fixture page (`backend/tests/google_serp/fixtures/results_page.html`) and don't open a browser. Google changes its markup often. When parsing breaks, save a live page with `GoogleSerpSession().fetch_html(...)`, compare it with the fixture, then update `backend/src/google_serp/parser.py` and the fixture together.

## Repository layout

Paths are relative to `networking-agent/`.

```
backend/src/google_serp/     the package
  session.py                 Chrome session, search, redirect resolution
  parser.py                  HTML -> SearchResponse (pure, no browser)
  models.py                  result dataclasses
  errors.py                  exceptions
  cli.py                     `python -m google_serp` command
backend/tests/google_serp/   pytest suite (no network)
research/google_serp/        scripts used to find the endpoint (see results.md)
docs/google_serp/results.md  research write-up
```
