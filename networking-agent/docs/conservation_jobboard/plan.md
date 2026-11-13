# Conservation Job Board support

Goal: let the agent search https://www.conservationjobboard.com (conservation, environmental,
nature and wildlife jobs, mostly US) through a lean Python API module and a LangChain tool,
following the `builtin_nyc` model.

## Findings (investigated 2026-11-13, 19 `requests` fetches + 4 Chrome page loads, none blocked)

- **robots.txt** allows everything except `/*mailto:`. Served behind Cloudflare, but plain
  `requests` with a normal browser User-Agent got 200s with no challenge.
- **No public JSON API or RSS feed.** Listings are **server-rendered HTML** (Laravel +
  Livewire + a Vue filter widget). The widget calls `/ajax/search` only for sidebar filter
  counts; job cards themselves are in the HTML. No Playwright needed.
- **Browser check** (`research/conservation_jobboard/inspect_page.py`, Playwright + Chrome):
  - The site's own XHR/fetch calls on a search page are `/ajax/auth/check` (login state),
    `/ajax/search?global_filter=...` (JSON labels for the *selected* filters:
    `categories, tags, regions, states, types, experiences`; no jobs) and `/cdn-cgi/rum`
    (Cloudflare analytics). Turnstile runs in the background, but there was no challenge.
  - Scrolling to the bottom loads nothing more (15 main cards before and after): there is no
    infinite scroll.
  - Clicking page 2 is a full document navigation to `?query=<kw>&page=2`, not a Livewire
    call. Its cards match the raw `requests` HTML. `/search/kw=<kw>/2` (the form `get_jobs`
    uses) returns the identical 15 ids.
  - The only Livewire `/livewire-*/update` call is on job detail pages. It is the
    related-jobs widget (`relatedJobLoadJobs`), which returns rendered card HTML and needs a
    page-specific snapshot, checksum and CSRF token. It's not a usable search API.
  - Conclusion: the server-rendered HTML is the complete and simplest source.
- **Facet pages** (one filter each): `/category/<slug>`, `/<state-slug>`,
  `/region/<slug>`, `/job-type/<slug>`, `/experience/<slug>`, `/tag/<slug>`; paged as
  `/<path>/2`.
- **Combined filters** (from `globalFilterToUrl` in `/js/site-new.js`):
  `/search/kw=<text>&cat=<ids>&state=<ids>&region=<ids>&type=<ids>&experience=<ids>`,
  multiple ids joined with `-` (`state=6-5`), page appended as `/<page>`. Verified live:
  `/search/kw=wildlife&state=6-5&cat=1&type=2` (3 jobs) and `/search/region=7&experience=1/2`.
  Values within a field are OR-ed (`state=6-5` = Colorado or California); a state plus
  `region=9` also behaved like OR (Colorado had no wildlife jobs, and only remote ones came
  back). The numeric ids come from the `<top-filter :categories=... :states=... :regions=...
  :types=... :experiences=...>` props on the home page. The remote region is id 9 (from
  `/region/remote`'s Livewire state; id 7 is ignored by the site).
- **Keyword-only search**: the home form posts to `/intermediate-search?kw=...`, which
  redirects to `/search/kw=<text>`; its own pagination links use `?page=N` but the path
  `/N` form works for every filter combination, so we use that.
- **Pagination**: 15 main results per page. A page past the end returns 200 with no main
  cards, so "no new ids" ends pagination.
- **Sorting** (`?sort_by=date|deadline`) is offered, but for keyword searches page 2 was
  identical with and without `sort_by=date`, so it's unreliable and not exposed.
- **Cards**: `div.listing__job > article`. The title link `a.gtag-job-link` carries
  `job_id` (internal numeric id), `href` (detail page, sometimes with `?from=feat-1`) and
  `list_name`: `main-results-page` (the filtered results), `featured-results` (paid
  promotions repeated on every page, unrelated to the filter) or `results-sidebar`.
  Sponsor cards (`listing__job--sponsor`, graduate program ads) have no title link.
  Fields: `h3` organization, `h4` location, `p.listing__job__intro` rows labelled
  `Job type`, `Salary`, `Deadline` (optional), `Min. Experience`; `.listing__job__time`
  relative posted date ("Today", "7 days ago").
- **Detail pages** (`/job-listing-<slug>/<code>`) have `JobPosting` JSON-LD, but its
  description is truncated, so `read_page`'s default `auto` method (full page text) is left
  as is.
- **Organizations**: no organization/employer listing pages (sitemap has none), so no
  `get_organizations`.

## Plan

1. `backend/src/conservation_jobboard/`:
   - `models.py`: filter enums (`Category`, `Location` = states + regions incl. remote,
     `JobType`, `ExperienceLevel`) whose values are readable slugs and which carry the
     site's numeric id; `JobFilter`; `Job` (id, title, url, organization, location,
     job_type, salary, deadline, experience, posted).
   - `api.py`: `search_path(job_filter, page)`, card parsing (main results only), and
     `get_jobs(job_filter, n)` with pagination (cap 10 pages, 1 s delay) and dedupe by id.
     URLs are returned without query strings so entity keys stay stable.
   - `__init__.py`: re-exports.
2. `tools.py`: `search_conservation_jobs` tool (keyword, categories, locations, job_types,
   experience_levels, n <= 30), added to `ALL_TOOLS`. Output is a list of job dicts with
   `url` and `company` like the BuiltIn job tool, so the compile step and the entities
   pipeline (job keys = normalized URLs) treat them the same way.
3. `agent.py`: progress line for the new tool. `prompts.py`: describe the tool and when to
   use it (conservation / environmental / nature / wildlife / outdoor roles).
4. Tests (offline, fixtures in `backend/tests/conservation_jobboard/fixtures/`, trimmed by
   `research/conservation_jobboard/make_fixtures.py`): URL building, card parsing (featured
   and sponsor cards skipped), pagination stop + dedupe, tool output and registration.

No new requirements (`requests` + `beautifulsoup4` already used by `builtin_nyc`).
