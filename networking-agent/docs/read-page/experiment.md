# read_page() experiment: fetching a web page and converting it to Markdown

**Date:** 2026-11-12
**TODO item:** Add read_page() tool, *experiment* sub-step
**Question:** Which Python modules or tools should `read_page(url)` use to turn a web page into
readable Markdown that keeps hyperlinks? Which page types need a different, faster method?

## TL;DR

- **Default method:** fetch with `requests`, then extract with **`trafilatura`** (`output_format="markdown"`,
  `include_links=True`, `url=<final url>`). Pass the response **bytes** (`r.content`) to trafilatura,
  not `r.text`. It returned the main content on 10 of 10 statically served pages, with 0 to 1 boilerplate
  hits per page and absolute links. It used 1.3 to 12x fewer tokens than whole-page converters, about 3 to 5x on most pages. The new
  dependency adds about 1 MB of code (`trafilatura` plus its small dependencies; `lxml` comes with it).
- **Fallback 1, a JS-rendered page** (the static extraction is under about 200 characters or contains
  "enable JavaScript"): render the page with **Playwright**, which is already a backend dependency, then
  run the same trafilatura step. A cold start with Chromium took 0.7 s. A page took 1 to 12 s.
- **Fallback 2, a "cards" page** (leadership or team page, listing page): trafilatura sometimes drops
  short card text such as people's names in headings. A cheap **"cleaned-full"** method fixes this:
  BeautifulSoup removes `nav`, `header`, `footer`, `aside`, `form` and `script`, then `html2text` converts
  the rest. It kept the names and cost about 2x the tokens of trafilatura.
- **Specialized methods by domain (fastest, structured):** ATS JSON APIs for Greenhouse, Lever and
  Ashby (0.4 to 0.9 s, no browser, no HTML parsing), and **JSON-LD `JobPosting`** for job pages that
  embed it (BuiltIn, Ashby). Ashby's static HTML holds the full posting in JSON-LD even though the
  visible page needs JS, so no browser is needed for it.
- **Crawl4AI:** good quality (its "fit" Markdown kept the names), but **heavy**: 742 MB venv,
  about 100 packages (numpy, nltk, openai/litellm, patchright, playwright-stealth, pillow...), and a
  145 s install. It always launches a browser, even for static pages. It gives us nothing that
  trafilatura + Playwright doesn't already do, so **don't adopt it**. In `raw:` mode its links were
  not absolutized (12 to 100% absolute).
- **readability-lxml:** **not recommended**. It lost most of the article on Wikipedia (1,085 tokens vs
  about 7,250), Lever (337 vs about 1,070) and the LinkedIn job search (9 tokens).
- **LinkedIn:** company pages and job-search pages are served to logged-out guests (HTTP 200, usable
  text). **Profile pages return HTTP 999 to `requests`.** Headless Chromium got a partial guest profile
  once, but that isn't reliable, and LinkedIn's terms forbid scraping. Keep using the Google SERP
  snippets (`find_people`) for people, and have `read_page` refuse `linkedin.com/in/*` with a clear
  error.

## Setup

- A separate scratch venv (Python 3.11), not the project venv: `requests`, `httpx`, `beautifulsoup4`,
  `lxml`, `trafilatura 2.3.1`, `markdownify 1.2.3`, `html2text 2025.4.15`, `readability-lxml 0.9`,
  `playwright 1.65.1`. `crawl4ai 0.9.5` went in its own venv to measure its weight.
- Each URL was fetched **once with `requests`** (Chrome User-Agent) and **once with headless
  Chromium** (Playwright, `domcontentloaded` plus up to 8 s of `networkidle`). The HTML was cached to
  disk, and every converter ran on the cached copy, so no site got more than 2 to 3 requests.
  (Crawl4AI ran on the cached browser HTML through `raw:`. It made one live crawl, of the Ashby page.)
- Metrics:
  - tokens: characters / 4
  - links: the number of `[text](url)` links
  - abs %: the share of links with absolute URLs
  - boiler: hits for "cookie", "privacy policy", "sign in", "log in", "subscribe",
    "all rights reserved", "terms of service" and "skip to"
- I also inspected the outputs by eye.
- The scripts (`fetch.py`, `convert.py`, `variants.py`, `cleaned_full.py`, `c4a.py`,
  `jsonld_and_api.py`) live in the session scratchpad, not in the repo. A summary of what each one
  does is above.

### Pages tested

| key | URL | type |
|---|---|---|
| company_about | datadoghq.com/about/leadership/ | company "about" / leadership |
| careers | careers.datadoghq.com/ | company careers landing |
| greenhouse_job | job-boards.greenhouse.io/datadog/jobs/8257324 (redirects to the custom careers.datadoghq.com detail page) | Greenhouse-backed custom page |
| greenhouse_hosted_job | job-boards.greenhouse.io/discord/jobs/8917177002 | Greenhouse-hosted posting |
| lever_job | jobs.lever.co/spotify/2a55d6c9-... | Lever posting |
| builtin_job | builtinnyc.com/job/senior-product-engineer/11344396 | BuiltIn NYC posting |
| wikipedia | en.wikipedia.org/wiki/Datadog | encyclopedia article |
| blog | blog.cloudflare.com/vole-mole/ | long technical blog post |
| ashby_job_js | jobs.ashbyhq.com/notion/1fc309c8-... | **JS-only SPA** (static HTML only says "You need to enable JavaScript") |
| linkedin_company / _job_search / _profile | linkedin.com/company/datadog/, /jobs/search?..., /in/williamhgates/ | LinkedIn checks |

## Results

### Fetch latency (one request each)

| Page | `requests` (s, status) | headless Chromium (s, status) | raw HTML |
|---|---|---|---|
| company_about | 0.45 (200) | 11.55 (200) | 246 KB |
| careers | 0.46 (200) | 1.50 (200) | 184 KB |
| greenhouse_job | 0.88 (200) | 2.41 (200) | 159 KB |
| greenhouse_hosted_job | 0.53 (200) | 1.85 (200) | 85 KB |
| lever_job | 14.06* (200) | 2.47 (200) | 710 KB |
| builtin_job | 1.02 (200) | 2.03 (200) | 85 KB |
| wikipedia | 0.37 (200) | 0.95 (200) | 316 KB |
| blog | 0.33 (200) | 8.33 (200) | 310 KB |
| ashby_job_js | 0.47 (200, empty shell) | 1.85 (200) | 51 KB |
| linkedin_company | 0.90 (200) | 8.75 (200) | 346 KB |
| linkedin_job_search | 1.08 (200) | 8.70 (200) | 278 KB |
| linkedin_profile | 0.52 (**999**) | 3.31 (200, partial) | 1 KB |

\*The Lever server was slow on this one request (the browser fetch took 2.5 s a moment later). In
an earlier test, `api.lever.co` timed out at 20 s on a large board. Use timeouts.

Chromium launch: 0.7 s. A static fetch takes about 0.3 to 1 s, a browser fetch 1 to 12 s, because
it waits for network idle. **The static path is 2 to 25x faster.**

### Output size (estimated tokens) by converter

All converters ran on the static HTML, except rows marked (browser).

| Page | trafilatura | readability + markdownify | cleaned-full (bs4 + html2text) | html2text (whole page) | markdownify (whole page) | Crawl4AI fit (browser HTML) |
|---|---|---|---|---|---|---|
| company_about | 3,522 ⚠ names lost | 6,895 | 7,140 | 18,709 | 17,994 | 8,340 |
| careers | 537 | 621 | 1,183 | 6,310 | 5,953 | 1,032 |
| greenhouse_job | 1,229 | 1,249 | 1,265 | 6,393 | 6,143 | 1,463 |
| greenhouse_hosted_job | 1,358 | 1,338 | 1,389 | 2,135 | 2,110 | 1,375 |
| lever_job | 1,071 | **337 ✗** | 1,366 | 1,366 | 1,374 | 1,346 |
| builtin_job | 1,026 | 1,813 | 2,481 | 4,234 | 3,963 | 2,495 |
| wikipedia | 7,253 | **1,085 ✗** | 7,462 | 22,182 | 23,384 | 9,038 |
| blog | 7,311 | 7,185 | 7,435 | 22,348 | 21,592 | 7,736 |
| ashby_job_js (static) | 11 ✗ (JS shell) | 0 ✗ | 0 ✗ | 12 ✗ | 16 ✗ | n/a |
| ashby_job_js (browser) | 1,621 | 1,642 | n/a | 1,855 | 1,829 | 1,714 |
| linkedin_company | 1,915 | **160 ✗** | 8,108 | 11,319 | 10,524 | 7,407 |
| linkedin_job_search | 1,314 | **9 ✗** | 6,508 | 7,985 | 7,840 | 7,223 |
| linkedin_profile (browser) | 779 | 1,531 | n/a | 13,751 | 12,535 | 10,193 |

Conversion time once the HTML is in hand is small for every library: 10 to 300 ms per page.
trafilatura took 10 to 190 ms, html2text 2 to 100 ms, markdownify 11 to 320 ms. Crawl4AI took
100 to 1,070 ms in `raw:` mode.

### Boilerplate and links

- **trafilatura:** boilerplate hits of 0 or 1 on every page. Links are absolute when `url=` is
  passed (100% on every page; Wikipedia links that contain parentheses come out as `[x](<url>)`,
  which is still valid Markdown). Wikipedia kept 174 to 231 in-article links; job pages kept "Apply",
  "Back to jobs" and similar links. Weak spots:
  - On the Datadog leadership page, **the names in card headings (`## Olivier Pomel`) were dropped**.
    Only the bios that mention the name survived. `favor_recall=True` didn't help. This matters for
    the "people to connect with" use case.
  - The Lever posting produced 0 links (the apply link wasn't extracted). That's a minor loss.
  - trafilatura adds a YAML front-matter (title, sitename, date, description) with
    `with_metadata=True`. For BuiltIn, that metadata is where the job title and company show up; the
    body has only the description.
- **Whole-page html2text / markdownify:** keep everything, including the menus, footers and cookie
  text (up to 57 boilerplate hits on LinkedIn). They use 1.3 to 12x the tokens of trafilatura (about 3 to 5x on most pages) and carry
  hundreds of nav links (up to 1,006 on the blog post). Not suitable as a default.
- **cleaned-full** (drop `nav`/`header`/`footer`/`aside`/`form`/`button`/`script`, ARIA chrome
  roles and cookie containers, prefer `<main>`, then html2text with `baseurl`): 0 to 3 boilerplate
  hits, absolute links, **kept the leadership names**, and came out at about the same size as
  trafilatura on article pages and about 2x on card or listing pages. A good no-new-dependency fallback.
- **readability-lxml:** fine on articles and job descriptions, but it picks the wrong block on
  Wikipedia, Lever and the LinkedIn job search. Rejected.
- **Crawl4AI `fit_markdown`** (PruningContentFilter, threshold 0.48): good recall (names kept) and
  moderate boilerplate. Its sizes are close to cleaned-full. In `raw:` mode, relative links stayed
  relative (12 to 100% absolute). The live crawl produced 100% absolute links.

### Encoding gotcha

`careers.datadoghq.com` sends `Content-Type: text/html` with no charset, so `requests` falls back to
ISO-8859-1 and `r.text` produces mojibake ("Weâre"). The fix is to pass `r.content` (bytes) to
trafilatura, which detects the charset itself, or to use `r.apparent_encoding`. With bytes the text
came out correct.

### Specialized methods (structured, no HTML scraping)

| Source | Endpoint | Latency | What you get |
|---|---|---|---|
| Greenhouse | `GET boards-api.greenhouse.io/v1/boards/{board}/jobs/{id}?pay_transparency=true` | 0.40 s | title, location, departments, offices, HTML `content` (HTML-escaped; unescape it, then markdownify: 5.3k chars), `absolute_url` |
| Lever | `GET api.lever.co/v0/postings/{company}/{id}` | 0.87 s | `description`, `lists[]` (requirements and so on), `additional`, `categories`, `applyUrl`, `hostedUrl` (4.6k chars of Markdown) |
| Ashby | `GET api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true` | 0.43 s | the whole board (160 jobs, 2.9 MB), each with `descriptionHtml`, `compensation`, `location`, `isRemote`, `applyUrl`. No single-job endpoint; cache the board. |
| JSON-LD `JobPosting` | any page with `<script type="application/ld+json">` | free (same static fetch) | `title`, `hiringOrganization`, `jobLocation`, `datePosted`, `employmentType`, `baseSalary` (BuiltIn), `description` (HTML). It's in **BuiltIn** and **Ashby static HTML** (the Ashby JSON-LD description = 6.6k chars, identical to the rendered page). It's not in Greenhouse-hosted or Lever pages. |
| BuiltIn NYC | already wrapped by `src/builtin_nyc` | n/a | `read_page` can delegate BuiltIn job URLs to it or read the JSON-LD |

Greenhouse custom-domain pages (for example Datadog: `job-boards.greenhouse.io/datadog/jobs/<id>`
redirects to `careers.datadoghq.com/detail/<id>/?gh_jid=<id>`) can still use the Greenhouse API.
Match on the `gh_jid` query parameter or on the original `job-boards.greenhouse.io` URL, before the
redirect.

### Dependency weight

| Stack | Install | Notes |
|---|---|---|
| trafilatura | about 1 MB package; a venv with trafilatura + markdownify + requests = 90 MB / 28 packages, most of which is pip/setuptools and lxml (9 MB) | pure Python plus lxml wheels; no browser |
| markdownify / html2text | about 0.1 to 0.2 MB each | html2text is the better fit for "cleaned-full" (`baseurl` resolves links) |
| readability-lxml | 0.2 MB + lxml_html_clean | rejected on quality |
| playwright | 117 MB package + Chromium (about 150 to 300 MB, already installed) | **already in `requirements.txt`** (google_serp) |
| crawl4ai 0.9.5 | **742 MB venv, about 100 packages, 145 s install** | pulls in numpy, nltk, openai, litellm fork, patchright, playwright-stealth, pillow, rank-bm25, ... |

The backend already depends on `requests`, `beautifulsoup4` and `playwright`. Adding
**`trafilatura` and `html2text`** is the whole incremental cost of the recommendation.

## Recommendation

1. **Default (`method="auto"`):**
   1. Check the domain registry (below) and use a specialized method if one matches.
   2. Otherwise, `requests.get(url, timeout=15)` with a desktop UA → `trafilatura.extract(r.content,
      url=r.url, output_format="markdown", include_links=True, include_tables=True,
      include_formatting=True, with_metadata=True)`.
   3. If the result is empty, under about 200 characters, or matches "enable JavaScript": check for a
      JSON-LD `JobPosting` in the same HTML, and if there isn't one, re-fetch with Playwright and run
      trafilatura again.
   4. If trafilatura's output is much smaller than the cleaned-full output (for example, under 40%
      on a page with many short headings), or the caller asks for `method="full"`, return cleaned-full
      instead.
2. **Specialized methods:** `greenhouse_api`, `lever_api`, `ashby_api` (board cached for about 10 min),
   `jsonld_jobposting`, `builtin` (delegate to `builtin_nyc`).
3. **Blocked:** `linkedin.com/in/*` returns `{"error": "LinkedIn profiles can't be read; use find_people"}`.
   LinkedIn company and jobs pages work through the static path, but keep their use light.
4. **Output limits:** clip to about 8k tokens (about 32k chars) by default with a `max_chars` argument,
   because long pages (Wikipedia, blogs) come out at 7k+ tokens even after extraction. Return
   `{url, final_url, method, title, markdown, truncated}` as JSON, like the other tools.
5. **Don't adopt Crawl4AI or readability-lxml.** Revisit Crawl4AI only if we need its stealth or
   anti-bot features or LLM-driven extraction.

## Proposed interface sketch

```python
# src/read_page/  (package, per networking-agent/AGENTS.md "group into sub-folders")
from typing import Callable, Literal, Protocol
import re

Method = Literal["auto", "static", "browser", "full", "greenhouse_api", "lever_api",
                 "ashby_api", "jsonld", "builtin"]

class PageResult(BaseModel):
    url: str
    final_url: str
    method: str            # the method that actually produced the output
    title: str | None
    markdown: str
    truncated: bool = False

class Reader(Protocol):
    def __call__(self, url: str, *, max_chars: int) -> PageResult: ...

# Per-domain registry: first regex match wins; "auto" consults it before the generic path.
REGISTRY: list[tuple[re.Pattern[str], Method]] = [
    (re.compile(r"^https?://(job-)?boards(-api)?\.greenhouse\.io/[^/]+/jobs/\d+"), "greenhouse_api"),
    (re.compile(r"[?&]gh_jid=\d+"),                                             "greenhouse_api"),
    (re.compile(r"^https?://jobs\.lever\.co/[^/]+/[0-9a-f-]{36}"),               "lever_api"),
    (re.compile(r"^https?://jobs\.ashbyhq\.com/[^/]+/[0-9a-f-]{36}"),            "ashby_api"),
    (re.compile(r"^https?://(www\.)?builtinnyc\.com/job/"),                      "jsonld"),
    (re.compile(r"^https?://([a-z]+\.)?linkedin\.com/in/"),                      "blocked"),
]

READERS: dict[str, Reader] = {
    "static": read_static,          # requests + trafilatura (bytes in, url= for absolute links)
    "browser": read_browser,        # Playwright (shared worker, like _GoogleWorker) + trafilatura
    "full": read_cleaned_full,      # bs4 chrome-stripping + html2text(baseurl)
    "greenhouse_api": read_greenhouse,
    "lever_api": read_lever,
    "ashby_api": read_ashby,
    "jsonld": read_jsonld_jobposting,
}

def register(pattern: str, method: Method) -> None:
    """Add a domain rule at runtime (e.g. after we find a better method for a site)."""
    REGISTRY.insert(0, (re.compile(pattern), method))

def read_page(url: str, method: Method | None = None, max_chars: int = 32_000) -> PageResult:
    method = method or "auto"
    if method == "auto":
        method = next((m for p, m in REGISTRY if p.search(url)), "static")
        if method == "blocked":
            raise PageBlocked(url)
        try:
            res = READERS[method](url, max_chars=max_chars)
        except SpecializedMethodFailed:
            res = READERS["static"](url, max_chars=max_chars)   # API down / id not found
        if looks_empty_or_js_shell(res):        # < ~200 chars or "enable JavaScript"
            res = (read_jsonld_from_cached_html(res) or READERS["browser"](url, max_chars=max_chars))
        return res
    return READERS[method](url, max_chars=max_chars)
```

The LangChain wrapper in `tools.py` would expose `read_page(url: str, method: str | None = None)`
and return `_dump(result.model_dump())`, or `_error(exc)`, following the existing pattern. The
browser reader should reuse a single-thread Playwright worker, the way `_GoogleWorker` does, because
the sync Playwright API is bound to the thread it was created on.

## Open questions for the plan step

- Should "cleaned-full" be the default for company pages found through `search_builtin_companies`
  (team/leadership pages), so that names are kept?
- Caching: should fetched pages be stored under `database/` (per TEST_USER) to avoid re-fetching
  inside a session?
- robots.txt: trafilatura doesn't check it. Decide whether `read_page` should respect it, and
  whether to rate-limit per host.
