"""LangChain tools that expose the two backbone packages (both in `src/`) to the agent.

- `builtin_nyc`: BuiltInNYC jobs and companies.
- `google_serp`: Google search through real Chrome.
- `read_page`: read any web page (job posting, careers/team page) as Markdown.

Every tool returns a compact JSON string. Errors are returned as `{"error": ...}`
instead of raised, so the agent can change its query and keep going.
"""

import atexit
import json
import logging
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal, TypeVar

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

import config
import google_serp
import read_page as read_page_pkg
from builtin_nyc import api as builtin_api
from builtin_nyc.models import (
    CompanyFilter,
    CompanySize,
    ExperienceLevel,
    JobCategory,
    JobFilter,
    RemotePreference,
)

log = logging.getLogger(__name__)

T = TypeVar("T")

MAX_TEXT = 300
"""Longest description/snippet passed back to the model, in characters."""


def _clip(text: str | None, limit: int = MAX_TEXT) -> str | None:
    if not text:
        return text
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _error(exc: Exception) -> str:
    log.warning("Tool error: %s", exc)
    return _dump({"error": f"{type(exc).__name__}: {exc}"})


# ----------------------------------------------------------------------- BuiltInNYC


class BuiltinJobsArgs(BaseModel):
    search: str | None = Field(
        default=None, description='Free-text search, e.g. "data analyst" or "python".'
    )
    category: JobCategory | None = Field(default=None, description="Top-level job category.")
    experience_levels: list[ExperienceLevel] = Field(default=[], description="Seniority levels.")
    remote_preferences: list[RemotePreference] = Field(
        default=[], description='"remote", "hybrid" and/or "office" (on-site).'
    )
    n: int = Field(default=15, ge=1, le=30, description="Maximum jobs to return.")


@tool("search_builtin_jobs", args_schema=BuiltinJobsArgs)
def search_builtin_jobs(
    search: str | None = None,
    category: JobCategory | None = None,
    experience_levels: list[ExperienceLevel] | None = None,
    remote_preferences: list[RemotePreference] | None = None,
    n: int = 15,
) -> str:
    """Search job postings on BuiltInNYC (tech/startup jobs in New York City, plus remote).

    Returns jobs with title, posting URL, company, location, salary, level and skills.
    Use a short search phrase (1-3 words); combine with category/level filters.
    """
    try:
        jobs = builtin_api.get_jobs(
            JobFilter(
                search=search,
                category=category,
                experience_levels=experience_levels or [],
                remote_preferences=remote_preferences or [],
            ),
            n,
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return _dump(
        [
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
            for j in jobs
        ]
    )


class BuiltinCompaniesArgs(BaseModel):
    industries: list[str] = Field(
        default=[],
        description='BuiltIn industry aliases (lowercase, hyphenated), e.g. "fintech", '
        '"artificial-intelligence", "healthtech", "edtech", "greentech", "software", '
        '"cybersecurity", "consumer-web", "media", "nonprofit".',
    )
    sizes: list[CompanySize] = Field(default=[], description="Employee-count buckets.")
    tech_stack: list[str] = Field(default=[], description='Tech aliases, e.g. "python".')
    hiring_only: bool = Field(default=True, description="Only companies with open jobs.")
    fully_remote: bool = Field(default=False, description="Only fully remote companies.")
    n: int = Field(default=15, ge=1, le=30, description="Maximum companies to return.")


@tool("search_builtin_companies", args_schema=BuiltinCompaniesArgs)
def search_builtin_companies(
    industries: list[str] | None = None,
    sizes: list[CompanySize] | None = None,
    tech_stack: list[str] | None = None,
    hiring_only: bool = True,
    fully_remote: bool = False,
    n: int = 15,
) -> str:
    """List companies on BuiltInNYC (New York City tech companies) by industry, size or stack.

    Returns company name, BuiltIn profile URL, industries, size, whether it is hiring,
    and its mission/description.
    """
    try:
        companies = builtin_api.get_companies(
            CompanyFilter(
                industries=industries or [],
                sizes=sizes or [],
                tech_stack=tech_stack or [],
                hiring_only=hiring_only,
                fully_remote=fully_remote,
            ),
            n,
        )
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return _dump(
        [
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
            for c in companies
        ]
    )


# --------------------------------------------------------------------------- Google


ResultPicker = Callable[[list[google_serp.SearchResult]], list[google_serp.SearchResult]]
"""Chooses which results a tool will use, before their links are resolved."""


class _GoogleWorker:
    """Runs every Google search on one dedicated thread with one reusable browser.

    Playwright's sync API is bound to the thread that started it, and the Chrome
    profile can only be used by one browser at a time, so searches are serialized.

    Resolving Google's /goto links is ~95% of a search's time (Google throttles
    them), so only the results a tool will return are resolved. Results pages are
    cached for `config.GOOGLE_CACHE_TTL_S`, so a repeated query sends no new
    requests to Google.
    """

    MAX_CACHED = 64

    def __init__(self, cache_ttl: float | None = None) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="google-serp")
        self._session: google_serp.GoogleSerpSession | None = None
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

    def _fetch(self, query: str) -> google_serp.SearchResponse:
        """The results page for `query`, links unresolved, from the cache if fresh."""
        now = time.monotonic()
        cached = self._cache.get(query)
        if cached is not None and now - cached[0] < self._cache_ttl:
            log.info("Google results for %r served from cache", query)
            return cached[1]
        try:
            response = self._ensure_session().search(query, resolve_urls=False)
        except google_serp.CaptchaTimeoutError:
            raise
        except Exception:  # noqa: BLE001
            # The browser may have been closed or crashed: start a fresh one once.
            log.warning("Google search failed; restarting browser", exc_info=True)
            self._reset()
            response = self._ensure_session().search(query, resolve_urls=False)
        if response.results and self._cache_ttl > 0:
            self._cache = {q: e for q, e in self._cache.items() if now - e[0] < self._cache_ttl}
            if len(self._cache) >= self.MAX_CACHED:
                self._cache.pop(min(self._cache, key=lambda q: self._cache[q][0]))
            self._cache[query] = (now, response)
        return response

    def _search(
        self, query: str, resolve_urls: bool, pick: ResultPicker | None
    ) -> google_serp.SearchResponse:
        response = self._fetch(query)
        results = pick(list(response.results)) if pick else list(response.results)
        if resolve_urls:
            # Resolved in place, so a cached page keeps its resolved links.
            self._ensure_session().resolve_results(results)
        return google_serp.SearchResponse(results=results, metadata=response.metadata)

    def search(
        self, query: str, resolve_urls: bool = True, pick: ResultPicker | None = None
    ) -> google_serp.SearchResponse:
        """Search Google; resolve the links of only the results `pick` keeps."""
        with self._lock:
            return self._executor.submit(self._search, query, resolve_urls, pick).result()

    def close(self) -> None:
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


def run_google_search(query: str, pick: ResultPicker | None = None) -> google_serp.SearchResponse:
    """Run one Google search through the shared worker (patched in tests).

    `pick` chooses the results the caller will use; only their links are resolved.
    """
    return _google_worker().search(query, resolve_urls=config.GOOGLE_RESOLVE_URLS, pick=pick)


def shutdown() -> None:
    """Close the Google browser and the read_page browser if they were started."""
    global _google
    with _google_lock:
        if _google is not None:
            _google.close()
            _google = None
    read_page_pkg.shutdown()


def _safe(fn: Callable[[], T]) -> T | str:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


class GoogleSearchArgs(BaseModel):
    query: str = Field(description="Google query. Operators like site: and quotes work.")
    n: int = Field(default=10, ge=1, le=10, description="Maximum results to return.")


@tool("google_search", args_schema=GoogleSearchArgs)
def google_search(query: str, n: int = 10) -> str:
    """Search Google. Returns title, URL, site and snippet for each organic result.

    Good for job postings outside NYC (e.g. `"data analyst" jobs Boston site:greenhouse.io`),
    company research, and company websites. Each call takes 2-25 seconds (larger n is slower).
    """
    response = _safe(lambda: run_google_search(query, pick=lambda results: results[:n]))
    if isinstance(response, str):
        return response
    return _dump(
        [
            {
                "title": r.title,
                "url": r.url,
                "site": r.site_name,
                "snippet": _clip(r.snippet),
            }
            for r in response.results[:n]
        ]
    )


_LINKEDIN_TITLE = re.compile(r"\s*[|·]\s*LinkedIn\s*$", re.IGNORECASE)


def parse_linkedin_title(title: str) -> tuple[str, str]:
    """Split a LinkedIn result title into (name, headline).

    `"Jane Doe - Data Scientist - Acme | LinkedIn"` -> `("Jane Doe", "Data Scientist - Acme")`.
    """
    title = _LINKEDIN_TITLE.sub("", title).strip()
    name, _, headline = (part.strip() for part in title.partition(" - "))
    return name, headline


def _looks_like_linkedin(result: google_serp.SearchResult) -> bool:
    """True for a LinkedIn result. Works before its /goto link is resolved too."""
    return (
        "linkedin.com/in/" in result.url
        or "linkedin.com" in result.display_url
        or "LinkedIn" in (result.site_name + result.title)
    )


class FindPeopleArgs(BaseModel):
    company: str = Field(description="Company name, e.g. 'Ramp'.")
    keywords: str = Field(
        description='Role/team keywords, e.g. "data science manager" or "recruiter".'
    )
    location: str = Field(default="", description="Optional city, e.g. 'New York'.")
    n: int = Field(default=5, ge=1, le=10, description="Maximum people to return.")


@tool("find_people", args_schema=FindPeopleArgs)
def find_people(company: str, keywords: str, location: str = "", n: int = 5) -> str:
    """Find people at a company to network with, via Google search of LinkedIn profiles.

    Returns name, headline, LinkedIn profile URL and snippet.
    Each call takes 2-25 seconds (larger n is slower).
    """
    query = f'site:linkedin.com/in "{company}" {keywords} {location}'.strip()
    response = _safe(
        lambda: run_google_search(
            query, pick=lambda results: [r for r in results if _looks_like_linkedin(r)][:n]
        )
    )
    if isinstance(response, str):
        return response
    people = []
    for r in response.results:
        if not _looks_like_linkedin(r):
            continue
        name, headline = parse_linkedin_title(r.title)
        people.append(
            {"name": name, "headline": headline, "url": r.url, "snippet": _clip(r.snippet)}
        )
    return _dump(people[:n])


# ------------------------------------------------------------------------ read_page

READ_PAGE_MAX_CHARS = 12_000
"""Default page budget for the agent (about 3k tokens); the model may ask for up to 32k."""

ReadMethod = Literal[
    "auto", "static", "full", "browser", "jsonld", "greenhouse_api", "lever_api", "ashby_api"
]


class ReadPageArgs(BaseModel):
    url: str = Field(description="Full http(s) URL of the page, copied from a tool result.")
    method: ReadMethod = Field(
        default="auto",
        description='Leave "auto" (picks the best method for the URL, with fallbacks). Use '
        '"full" for team/leadership/listing pages if names or cards seem missing, and '
        '"browser" if the page needs JavaScript.',
    )
    max_chars: int = Field(
        default=READ_PAGE_MAX_CHARS,
        ge=1_000,
        le=read_page_pkg.DEFAULT_MAX_CHARS,
        description="Maximum Markdown characters to return.",
    )


@tool("read_page", args_schema=ReadPageArgs)
def read_page(url: str, method: ReadMethod = "auto", max_chars: int = READ_PAGE_MAX_CHARS) -> str:
    """Read a web page as Markdown, with its hyperlinks.

    Use it on a job posting (requirements, salary, team, how to apply) or a company's careers,
    about or team page. Returns {url, final_url, method, title, markdown, truncated}.
    LinkedIn profile pages can't be read; use find_people for people. Takes 1-15 seconds.
    """
    try:
        result = read_page_pkg.read_page(url, method=method, max_chars=max_chars)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return _dump(result.model_dump())


ALL_TOOLS: list[BaseTool] = [
    search_builtin_jobs,
    search_builtin_companies,
    google_search,
    find_people,
    read_page,
]
