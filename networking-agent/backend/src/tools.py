"""Shared data-source functions used by the search pipeline (`pipeline.steps`).

- `builtin_jobs` / `builtin_companies`: BuiltInNYC jobs and companies (`builtin_nyc`).
- `conservation_jobs`: Conservation Job Board jobs (`conservation_jobboard`).
- `usajobs_jobs`: federal jobs from the official USAJOBS API (`usajobs`).
- `ats_boards` / `ats_jobs`: companies' ATS boards (Greenhouse, Lever, ...) found through Google,
  and their matching postings from the board's public API (`ats`).
- `google_search`: Google search through real Chrome (`google_serp`), one shared worker.
- `linkedin_people`: LinkedIn profiles at a company, found through Google (`linkedin`).
- `read_page`: any web page as Markdown (`read_page`).

Each returns compact, JSON-friendly dicts (long text clipped) and raises on failure; the
pipeline records errors in its trace and keeps going.
"""

import atexit
import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import ats
import config
import google_serp
import linkedin
import read_page as read_page_pkg
from builtin_nyc import api as builtin_api
from builtin_nyc.models import CompanyFilter, JobFilter
from conservation_jobboard import api as conservation_api
from conservation_jobboard.models import JobFilter as ConservationJobFilter
from usajobs import api as usajobs_api
from usajobs.models import JobFilter as UsajobsFilter

log = logging.getLogger(__name__)

MAX_TEXT = 300
"""Longest description/snippet passed on to the model, in characters."""


def _clip(text: str | None, limit: int = MAX_TEXT) -> str | None:
    if not text:
        return text
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# ----------------------------------------------------------------------- BuiltInNYC


def builtin_jobs(job_filter: JobFilter, n: int = 15) -> list[dict[str, Any]]:
    """BuiltInNYC job postings (NYC tech/startup jobs, plus remote) matching `job_filter`."""
    return [
        {
            "title": j.title,
            "url": j.url,
            "company": j.company_name,
            "company_url": j.company_url,
            "location": j.location,
            "work_arrangement": j.work_arrangement,
            "salary": j.salary,
            "experience_level": j.experience_level,
            "posted": j.posted,
            "industries": j.industries,
            "skills": j.skills[:8],
            "summary": _clip(j.description),
        }
        for j in builtin_api.get_jobs(job_filter, n)
    ]


def builtin_companies(company_filter: CompanyFilter, n: int = 15) -> list[dict[str, Any]]:
    """BuiltInNYC companies (NYC tech companies) matching `company_filter`."""
    return [
        {
            "name": c.name,
            "url": c.url,
            "industries": c.industries,
            "employees": c.employee_count,
            "offices": c.office_locations[:5],
            "is_hiring": c.is_hiring,
            "mission": _clip(c.mission),
            "description": _clip(c.description),
        }
        for c in builtin_api.get_companies(company_filter, n)
    ]


# ------------------------------------------------------------ Conservation Job Board


def conservation_jobs(job_filter: ConservationJobFilter, n: int = 15) -> list[dict[str, Any]]:
    """Conservation Job Board postings (conservation/environmental jobs, mostly US)."""
    return [
        {
            "title": j.title,
            "url": j.url,
            "company": j.organization,
            "location": j.location,
            "job_type": j.job_type,
            "salary": j.salary,
            "experience": j.experience,
            "deadline": j.deadline,
            "posted": j.posted,
        }
        for j in conservation_api.get_jobs(job_filter, n)
    ]


# -------------------------------------------------------------------------- USAJOBS


def usajobs_jobs(job_filter: UsajobsFilter, n: int | None = None) -> list[dict[str, Any]]:
    """Federal job announcements from USAJOBS (needs `USAJOBS_API_KEY` and `USAJOBS_EMAIL`)."""
    if not (config.USAJOBS_API_KEY and config.USAJOBS_EMAIL):
        raise RuntimeError("USAJOBS is not configured")
    jobs = usajobs_api.search_jobs(
        job_filter, n or config.USAJOBS_RESULTS, config.USAJOBS_API_KEY, config.USAJOBS_EMAIL
    )
    return [
        {
            "title": j.title,
            "url": j.url,
            "apply_url": j.apply_url,
            "company": j.agency or j.department,
            "location": j.location,
            "job_type": j.job_type,
            "salary": j.salary,
            "deadline": f"closes {j.closes}" if j.closes else None,
            "posted": j.posted,
            "summary": _clip(j.summary),
        }
        for j in jobs
    ]


# --------------------------------------------------------------------------- Google


ResultPicker = Callable[[list[google_serp.SearchResult]], list[google_serp.SearchResult]]
"""Chooses which results a tool will use, before their links are resolved."""

PageCheck = Callable[[google_serp.SearchResponse], bool]
"""Says whether a results page is good enough to cache."""


class _GoogleWorker:
    """Runs every Google search on one dedicated thread with one reusable browser.

    Playwright's sync API is bound to the thread that started it, and the Chrome
    profile can only be used by one browser at a time, so searches are serialized.

    Resolving Google's /goto links is ~95% of a search's time (Google throttles
    them), so only the results a tool will return are resolved. Results pages are
    cached for `config.GOOGLE_CACHE_TTL_S`, so a repeated query sends no new
    requests to Google.

    When a SERP API key is set (`google_serp.client_from_env`), pages come from that API
    instead: direct URLs, no CAPTCHAs, ~1-2 s, and Chrome is never started.
    """

    MAX_CACHED = 64

    def __init__(
        self,
        cache_ttl: float | None = None,
        client: google_serp.SerpClient | None | bool = True,
    ) -> None:
        # `client=True` means "from the environment"; None forces the Chrome session.
        self._client = google_serp.client_from_env() if client is True else client or None
        if self._client is not None:
            log.info("Google searches go through the %s API", self._client.name)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="google-serp")
        self._session: google_serp.GoogleSerpSession | None = None
        self._closed = False
        self._lock = threading.Lock()
        self._cache_ttl = config.GOOGLE_CACHE_TTL_S if cache_ttl is None else cache_ttl
        self._cache: dict[str, tuple[float, google_serp.SearchResponse]] = {}

    def _ensure_session(self) -> google_serp.GoogleSerpSession:
        if self._session is None:
            self._session = google_serp.GoogleSerpSession().start()
        return self._session

    def _reset(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:  # noqa: BLE001
                log.debug("Ignoring error while closing Google session", exc_info=True)
            self._session = None

    def _fetch(self, query: str, cacheable: PageCheck | None = None) -> google_serp.SearchResponse:
        """The results page for `query`, links unresolved, from the cache if fresh.

        A page that `cacheable` rejects (e.g. Google ignored an operator) isn't cached,
        so asking again really asks Google again.
        """
        now = time.monotonic()
        cached = self._cache.get(query)
        if cached is not None and now - cached[0] < self._cache_ttl:
            log.info("Google results for %r served from cache", query)
            return cached[1]
        if self._client is not None:
            response = self._client.search(query)
        else:
            response = self._search_in_browser(query)
        if response.results and self._cache_ttl > 0 and (cacheable is None or cacheable(response)):
            self._cache = {q: e for q, e in self._cache.items() if now - e[0] < self._cache_ttl}
            if len(self._cache) >= self.MAX_CACHED:
                self._cache.pop(min(self._cache, key=lambda q: self._cache[q][0]))
            self._cache[query] = (now, response)
        return response

    def _search_in_browser(self, query: str) -> google_serp.SearchResponse:
        try:
            return self._ensure_session().search(query)
        except google_serp.CaptchaTimeoutError:
            raise
        except Exception:  # noqa: BLE001
            # The browser may have been closed or crashed: start a fresh one once.
            log.warning("Google search failed; restarting browser", exc_info=True)
            self._reset()
            return self._ensure_session().search(query)

    def _search(
        self,
        query: str,
        resolve_urls: bool,
        pick: ResultPicker | None,
        cacheable: PageCheck | None = None,
    ) -> google_serp.SearchResponse:
        response = self._fetch(query, cacheable)
        results = pick(list(response.results)) if pick else list(response.results)
        if resolve_urls and any(r.google_url and r.url == r.google_url for r in results):
            # Resolved in place, so a cached page keeps its resolved links.
            self._ensure_session().resolve_results(results)
        return google_serp.SearchResponse(results=results, query=response.query)

    def search(
        self,
        query: str,
        resolve_urls: bool = True,
        pick: ResultPicker | None = None,
        cacheable: PageCheck | None = None,
    ) -> google_serp.SearchResponse:
        """Search Google; resolve the links of only the results `pick` keeps."""
        with self._lock:
            return self._executor.submit(
                self._search, query, resolve_urls, pick, cacheable
            ).result()

    def close(self) -> None:
        """Close the browser and stop the thread. Safe to call more than once."""
        if self._closed:
            return
        self._closed = True
        self._executor.submit(self._reset).result()
        self._executor.shutdown(wait=False)


_google: _GoogleWorker | None = None
_google_lock = threading.Lock()


def _google_worker() -> _GoogleWorker:
    global _google
    with _google_lock:
        if _google is None:
            _google = _GoogleWorker()
            atexit.register(_google.close)
        return _google


def run_google_search(
    query: str, pick: ResultPicker | None = None, cacheable: PageCheck | None = None
) -> google_serp.SearchResponse:
    """Run one Google search through the shared worker (patched in tests).

    `pick` chooses the results the caller will use; only their links are resolved.
    `cacheable` rejects results pages that shouldn't be reused for a repeated query.
    """
    return _google_worker().search(
        query, resolve_urls=config.GOOGLE_RESOLVE_URLS, pick=pick, cacheable=cacheable
    )


def shutdown() -> None:
    """Close the Google browser and the read_page browser if they were started."""
    global _google
    with _google_lock:
        if _google is not None:
            _google.close()
            _google = None
    read_page_pkg.shutdown()


def google_search(query: str, n: int = 10) -> list[dict[str, Any]]:
    """Organic Google results (title, URL, site, snippet). Takes 2-25 s (larger n is slower)."""
    response = run_google_search(query, pick=lambda results: results[:n])
    return [
        {"title": r.title, "url": r.url, "site": r.site_name, "snippet": _clip(r.snippet)}
        for r in response.results[:n]
    ]


LINKEDIN_RETRY_DELAY_S = 6.0
"""Pause before asking again when Google ignored `site:linkedin.com/in`."""


class OperatorIgnoredError(RuntimeError):
    """Google kept serving job listings instead of LinkedIn profiles."""


def _search_profiles(query: str, company: str, n: int) -> tuple[list[dict], bool]:
    """Up to `n` profiles for `query`, current employees of `company` first, and whether
    Google ignored the `site:` operator."""
    seen = {"ignored": False}

    def elsewhere(result: google_serp.SearchResult) -> bool:
        return not linkedin.parse_profile(result, company)["at_company"]

    def pick(results: list[google_serp.SearchResult]) -> list[google_serp.SearchResult]:
        seen["ignored"] = linkedin.operator_ignored(results)
        profiles = [r for r in results if linkedin.looks_like_profile(r)]
        # Stable sort keeps Google's order within each group. Only these get resolved.
        return sorted(profiles, key=elsewhere)[:n]

    response = run_google_search(
        query, pick=pick, cacheable=lambda page: not linkedin.operator_ignored(page.results)
    )
    people = []
    for r in response.results:
        # Checked again after resolving: only linkedin.com/in/ links are kept.
        if linkedin.looks_like_profile(r):
            person = linkedin.parse_profile(r, company)
            person["snippet"] = _clip(r.snippet)
            people.append(person)
    return people[:n], seen["ignored"]


def linkedin_people(
    company: str, keywords: str, location: str = "", n: int = 5
) -> list[dict[str, Any]]:
    """LinkedIn profiles of people at `company`, found through Google.

    Only linkedin.com/in profiles, current employees first: name, headline, current title
    and company, `at_company` (False = may work elsewhere now), location, URL and snippet.
    Raises `OperatorIgnoredError` if Google ignored `site:` twice. Takes 2-25 s.
    """
    people, ignored = _search_profiles(
        linkedin.build_query(company, keywords, location), company, n
    )
    if ignored:
        # Google sometimes drops the site: operator and serves job boards instead;
        # asking again shortly after (operator moved to the end) usually works.
        log.info("Google ignored site:linkedin.com/in for %r; retrying", company)
        time.sleep(LINKEDIN_RETRY_DELAY_S)
        people, ignored = _search_profiles(
            linkedin.retry_query(company, keywords, location), company, n
        )
    if not people and ignored:
        raise OperatorIgnoredError(
            "Google returned job listings instead of LinkedIn profiles (asked twice)."
        )
    return people


# ----------------------------------------------------------------------- ATS boards


def ats_boards(provider: str, keywords: str, location: str = "") -> list[dict[str, Any]]:
    """Companies' boards on ATS `provider` (e.g. "greenhouse") that Google finds for
    `keywords` in `location`, via a `site:` search: `{provider, slug, job_ids}` each, in
    Google's order. `job_ids` are postings Google linked to directly.

    Most boards are read off the result's breadcrumb without resolving its `/goto` link;
    only results that hide the board (e.g. embeds) are resolved, at most
    `config.ATS_RESOLVE_LINKS`. Takes 2-25 s.
    """
    p = ats.get_provider(provider)

    def pick(results: list[google_serp.SearchResult]) -> list[google_serp.SearchResult]:
        # Only these get their links resolved; the rest are read from their breadcrumbs.
        return [r for r in results if ats.needs_resolving(r, p)][: config.ATS_RESOLVE_LINKS]

    def on_provider(page: google_serp.SearchResponse) -> bool:
        # Don't cache a page where Google ignored the site: operator.
        return any(ats.board_ref(r, p) or ats.needs_resolving(r, p) for r in page.results)

    query = ats.site_query(p, keywords, location)
    results = _google_page_results(query, pick, on_provider)
    return [b.model_dump() for b in ats.boards_from_results(results, p)]


def _google_page_results(
    query: str, pick: ResultPicker, cacheable: PageCheck
) -> list[google_serp.SearchResult]:
    """Every result of the page (resolved ones included), not only the picked ones."""
    everything: list[google_serp.SearchResult] = []

    def keep_all(results: list[google_serp.SearchResult]) -> list[google_serp.SearchResult]:
        everything[:] = results
        return pick(results)

    run_google_search(query, pick=keep_all, cacheable=cacheable)
    return everything


def ats_jobs(
    provider: str,
    board: str,
    keywords: str,
    location: str = "",
    job_ids: list[str] | None = None,
    n: int = 4,
) -> list[dict[str, Any]]:
    """Up to `n` open postings on one ATS board from its public API: those Google linked to
    (`job_ids`) first, then those matching `keywords` and `location`."""
    p = ats.get_provider(provider)
    jobs = ats.filter_jobs(p.list_jobs(board), keywords, location, job_ids or [], n)
    return [
        {
            "title": j.title,
            "url": j.url,
            "company": j.company,
            "company_url": p.board_url(j.board),
            "location": j.location,
            "summary": " · ".join(
                [p.label, *j.departments[:2], *([f"posted {j.posted}"] if j.posted else [])]
            ),
        }
        for j in jobs
    ]


# ------------------------------------------------------------------------ read_page


def read_page(url: str, max_chars: int = 12_000) -> read_page_pkg.PageResult:
    """`url` as Markdown with links (job postings, careers pages). Not LinkedIn profiles."""
    return read_page_pkg.read_page(url, max_chars=max_chars)
