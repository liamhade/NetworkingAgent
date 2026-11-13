# Plan: `read_page()` tool

TODO item: *"Given a URL, the Agent should get the text of the webpage rendered as Markdown,
including hyperlinks. The tool should use a default method for pages, but we should add the
option to use a more efficient method if we discover one that is particularly suited for a page
or group of pages."* This covers the *plan* and *implement* sub-steps. The method choices come
from [experiment.md](experiment.md).

## Interface

```python
from read_page import read_page, register, PageResult, PageBlocked

read_page(url: str, method: str | None = None, max_chars: int = 32_000) -> PageResult
# PageResult: {url, final_url, method, title, markdown, truncated}
```

- `method=None` / `"auto"` picks a method through the registry, then the generic pipeline.
- An explicit method (`"static"`, `"browser"`, `"full"`, `"jsonld"`, `"greenhouse_api"`,
  `"lever_api"`, `"ashby_api"`) runs only that method. It doesn't fall back.
- `register(pattern, method)` adds a per-URL regex rule at runtime. New rules are checked
  before the built-in rules. The first match wins.
- Errors: `PageBlocked` (LinkedIn profiles), `ReadPageError` (no content, unknown method,
  HTTP errors are passed through as `requests` exceptions). The LangChain tool turns all of
  them into `{"error": ...}`, as the other tools do.

## Package layout: `backend/src/read_page/`

| module | contents |
|---|---|
| `models.py` | `PageResult`, `PageBlocked`, `ReadPageError`, `MethodUnavailable` |
| `fetch.py` | `fetch(url) -> Fetched(url, final_url, status, content: bytes)`: `requests`, desktop UA, 15 s timeout |
| `convert.py` | `trafilatura_markdown(html_bytes, url)`, `cleaned_full_markdown(html, url)`, `html_to_markdown(fragment, url)`, `looks_empty(md)` |
| `methods.py` | one reader per method, each `(url) -> PageResult` (not truncated yet) |
| `browser.py` | `_BrowserWorker`: one thread, one headless Chromium, the same pattern as `tools._GoogleWorker` |
| `registry.py` | built-in rules, `register()`, `match()` |
| `core.py` | `read_page()`: dispatch, fallbacks, truncation, in-memory cache |
| `__init__.py` | the public names |

## Methods

| method | how it works |
|---|---|
| `static` (the default) | `fetch`, then `trafilatura.extract(r.content, url=final_url, output_format="markdown", include_links, include_tables, include_formatting)`. The title comes from `trafilatura.extract_metadata`. Bytes go in, so the charset is detected (the Datadog mojibake case). |
| `full` | BeautifulSoup removes `script/style/noscript/nav/header/footer/aside/form/button/svg/iframe`, ARIA chrome roles (`navigation`, `banner`, `contentinfo`, `search`, `dialog`) and cookie or consent containers. It uses `<main>` if there is one, then `html2text` with `baseurl` (absolute links, no wrapping). |
| `jsonld` | Finds `<script type="application/ld+json">` with `@type` `JobPosting` (including `@graph` and lists). It renders the title, company, location, employment type, date posted, salary and the description HTML converted to Markdown. |
| `greenhouse_api` | `boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}?pay_transparency=true`. The board and id come from `(job-)boards(.eu)?.greenhouse.io/{board}/jobs/{id}`, or from a `gh_jid` query parameter plus a `for=`/board hint. (With only `gh_jid` there's no board, so that case falls back to static. See below.) The content is HTML-escaped: unescape it, then convert to Markdown. |
| `lever_api` | `api.lever.co/v0/postings/{company}/{id}`: `descriptionPlain`/`description`, `lists[]`, `additional`, categories, `applyUrl`. |
| `ashby_api` | `api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true`, then the job with the matching id. The board is cached in memory for 10 min (there's no single-job endpoint). |
| `browser` | Playwright headless Chromium on the shared worker thread (`domcontentloaded` + up to 8 s of `networkidle`), then the same trafilatura step. |

A note on `gh_jid`: the experiment suggested matching `?gh_jid=`. The board token isn't in such
URLs (for example `careers.datadoghq.com/detail/123/?gh_jid=123`), and guessing it from the
domain is unreliable. So `gh_jid` URLs use the static path, which worked well on that page in the
experiment (1,229 tokens). Only real `greenhouse.io` URLs go to the API.

## Registry (built-in rules, first match wins)

```
linkedin.com/in/...                       -> blocked
(job-)boards(.eu)?.greenhouse.io/b/jobs/N -> greenhouse_api
jobs(.eu)?.lever.co/c/<uuid>              -> lever_api
jobs.ashbyhq.com/o/<uuid>                 -> ashby_api
builtin*.com/job/...                      -> jsonld
```

BuiltIn: the experiment offered "delegate to `builtin_nyc`", but `builtin_nyc` only scrapes the
listing pages. The JSON-LD on the job page has everything, including the salary, so we use `jsonld`.

## `auto` pipeline

1. Blocked rule: raise `PageBlocked` ("LinkedIn profiles can't be read; use find_people").
2. Registry match: run the specialized method. If it fails (`MethodUnavailable`, an HTTP error,
   an id not found), log the failure and go on to the generic path.
3. Generic path. Fetch **once**, then:
   1. Run trafilatura on the bytes.
   2. If the result looks empty (under 200 characters, or mentions "enable JavaScript"), try
      JSON-LD from the same HTML. If there's none, use `browser`.
   3. Card-page check: compute cleaned-full from the same HTML. If 4 or more of the page's
      h2 to h4 headings, and at least half of them, are missing **as lines of their own** from
      trafilatura's output, return cleaned-full instead (`method="full"`). This covers the
      Datadog leadership case where names were dropped. The extra conversion costs
      milliseconds and needs no new request.
      - *Changed during implementation:* the experiment suggested a "trafilatura output under
        40% of cleaned-full's length" condition. On the live Datadog page the ratio was 49%,
        and the names still showed up inside the bios, so a plain substring check passed. The
        line-based heading check catches 21 of 21 dropped names.
      - Cleaned-full also drops exact duplicate paragraphs of 80 or more characters, because
        card pages often contain a hidden modal copy of each bio. On Datadog this took the
        output from 28.5k to 16k characters. Once duplicates are removed, the two outputs are
        about the same length, so length isn't used as a signal at all.
4. Truncate to `max_chars` and set `truncated`. The cut happens at the last paragraph break
   before the limit when there is one.

The browser is only used as a fallback (or when explicitly requested). Playwright and Chromium
are already installed for `google_serp`. If launching fails, the error is returned as a tool
error.

## Decisions on the experiment's open questions

- **Cleaned-full for company pages:** no special casing by caller. The card-page heuristic
  (3.3) picks cleaned-full when trafilatura drops headings, and the agent can pass
  `method="full"` explicitly. The tool description tells it to do that for team or leadership pages.
- **Caching:** an in-memory cache with a TTL (about 10 min, 64 entries) keyed by
  `(url, method)`. It stores the untruncated result, and `max_chars` is applied per call. No
  disk cache under `database/`: pages are cheap to fetch again and stale quickly. This can be
  revisited at the Supabase migration.
- **robots.txt / rate limits:** not enforced in the POC. The agent makes about 10 to 14 tool calls
  in a run, a single request per page is the norm, the cache prevents repeats, and the user asks
  for each read. LinkedIn profiles are refused. Noted as a caveat.

## Agent integration

- `tools.py`: a `read_page` tool (`ReadPageArgs`: `url`, `method: Literal[...] | None`,
  `max_chars` 1,000 to 32,000, default 12,000 so a single page can't flood the context). It
  returns `_dump(result.model_dump())` or `_error(exc)`, and is added to `ALL_TOOLS`.
- `agent.py`: the system prompt lists `read_page` (read a job posting for requirements or salary,
  a company's careers or team page). `describe_tool_call` shows "Reading <host/path>".
  `describe_tool_result` already handles dicts; add a "read N chars" line.
- Dependencies: `trafilatura>=2.0`, `html2text>=2024.2` in `requirements.txt`.

## Tests (no network)

`tests/read_page/` with fixture HTML strings and a fake fetch / fake `requests.get`:

- static: links come out absolute, bytes with no charset decode correctly, the title is set.
- full: chrome is stripped, card names are kept, links are absolute.
- jsonld: a JobPosting (plain, `@graph`, list) is rendered; with no JSON-LD it raises `MethodUnavailable`.
- the Greenhouse, Lever and Ashby readers use mocked JSON, and the Ashby board cache is hit once.
- registry: built-in matches, `register()` takes precedence, LinkedIn is blocked.
- auto: a specialized method failing falls back to static; a JS shell falls back to JSON-LD,
  then to browser (fake); the card-page heuristic picks full; the cache avoids a second fetch.
- truncation: `max_chars` and the `truncated` flag.
- the tool: it's in `ALL_TOOLS`, returns JSON, returns the LinkedIn refusal as `{"error"}`,
  and the agent describes the call.

Then a live smoke test (one request per URL) on a handful of real pages, with the results
reported in the hand-off, not in the repo.
