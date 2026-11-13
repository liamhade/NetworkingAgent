# builtin_nyc

Python API for https://www.builtinnyc.com (jobs and companies). BuiltInNYC has no public JSON
API: `api.py` builds the filtered listing URLs and parses the server-rendered HTML cards.
Data models and filter enums are in `models.py`. The public API is re-exported from
`__init__.py`.

Moved here from the standalone `built-in-nyc-api` repo. Its history is in the parent repo
tag `archive/built-in-nyc-api`. Original requirements: `docs/builtin_nyc/prd.md`.

## Code Style

- Always use type hints in function signatures
- Create docstrings for complex functions
- Always lint using Ruff (backend config: `backend/pyproject.toml`)

## Tests

Offline, against saved HTML in `backend/tests/builtin_nyc/fixtures/`. When the site's markup
changes, update `api.py` and those fixtures together.

## Investigating the site

`networking-agent/research/builtin_nyc/inspect_page.py <url> [--headed]` logs a page's
network requests and saves a screenshot and the HTML to `research/builtin_nyc/out/`
(gitignored).
