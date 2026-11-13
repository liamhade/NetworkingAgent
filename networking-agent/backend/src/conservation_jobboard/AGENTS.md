# conservation_jobboard

Python API for https://www.conservationjobboard.com (conservation and environmental jobs),
used by the search pipeline through `tools.conservation_jobs`. The site has no public JSON API or feed:
`api.py` builds `/search/kw=<text>&cat=<ids>&state=<ids>&region=<ids>&type=<ids>&experience=<ids>`
paths (ids joined by `-`, page appended as `/N`) and parses the server-rendered job cards.
Only `list_name="main-results-page"` cards are results; featured/sidebar/sponsor cards are ads.
Filter enums and their site ids are in `models.py` (ids come from the home page's
`<top-filter>` props; remote is region 9). The public API is re-exported from `__init__.py`.
Findings and plan: `networking-agent/docs/conservation_jobboard/plan.md`.

A real-browser check found no XHR/JSON source of listings: `/ajax/search` only returns sidebar
filter labels, and pagination is a full page load. Plain `requests` sees every result.

## Code Style

- Always use type hints in function signatures
- Create docstrings for complex functions
- Always lint using Ruff (backend config: `backend/pyproject.toml`)

## Tests

Offline, against saved HTML in `backend/tests/conservation_jobboard/fixtures/`, trimmed with
`networking-agent/research/conservation_jobboard/make_fixtures.py` (strips Livewire state,
checksums, scripts, forms and tokens). When the site's markup or filter ids change, update
`api.py`/`models.py` and those fixtures together.

## Investigating the site

Output goes to `research/conservation_jobboard/out/` (gitignored; raw pages contain CSRF and
Livewire tokens). Keep live requests few and spaced out; the site is behind Cloudflare.

- `fetch.py <url> <outfile>`: one polite `requests` fetch (3.5 s delay, logs to
  `out/requests.log`, exits non-zero on a block).
- `inspect_page.py <url> [--click-page-2] [<detail-url>]`: loads the page in Chrome via
  Playwright and logs every XHR/fetch/document request to `out/browser_requests.log`, plus the
  rendered DOM.
