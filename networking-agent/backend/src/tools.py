"""LangChain tools that expose the two backbone packages (both in `src/`) to the agent.

- `builtin_nyc`: BuiltInNYC jobs and companies.
- `google_serp`: Google search through real Chrome.

Every tool returns a compact JSON string. Errors are returned as `{"error": ...}`
instead of raised, so the agent can change its query and keep going.
"""

import atexit
import json
import logging
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

import config
import google_serp
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


class _GoogleWorker:
    """Runs every Google search on one dedicated thread with one reusable browser.

    Playwright's sync API is bound to the thread that started it, and the Chrome
    profile can only be used by one browser at a time, so searches are serialized.
    """

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="google-serp")
        self._session: google_serp.GoogleSerpSession | None = None
        self._lock = threading.Lock()

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

    def _search(self, query: str, resolve_urls: bool) -> google_serp.SearchResponse:
        try:
            return self._ensure_session().search(query, resolve_urls=resolve_urls)
        except google_serp.CaptchaTimeoutError:
            raise
        except Exception:  # noqa: BLE001
            # The browser may have been closed or crashed: start a fresh one once.
            log.warning("Google search failed; restarting browser", exc_info=True)
            self._reset()
            return self._ensure_session().search(query, resolve_urls=resolve_urls)

    def search(self, query: str, resolve_urls: bool = True) -> google_serp.SearchResponse:
        with self._lock:
            return self._executor.submit(self._search, query, resolve_urls).result()

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


def run_google_search(query: str) -> google_serp.SearchResponse:
    """Run one Google search through the shared worker (patched in tests)."""
    return _google_worker().search(query, resolve_urls=config.GOOGLE_RESOLVE_URLS)


def shutdown() -> None:
    """Close the Google browser if one was started."""
    global _google
    with _google_lock:
        if _google is not None:
            _google.close()
            _google = None


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
    company research, and company websites. Each call takes 10-30 seconds.
    """
    response = _safe(lambda: run_google_search(query))
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

    Returns name, headline, LinkedIn profile URL and snippet. Each call takes 10-30 seconds.
    """
    query = f'site:linkedin.com/in "{company}" {keywords} {location}'.strip()
    response = _safe(lambda: run_google_search(query))
    if isinstance(response, str):
        return response
    people = []
    for r in response.results:
        if "linkedin.com/in/" not in r.url and "LinkedIn" not in (r.site_name + r.title):
            continue
        name, headline = parse_linkedin_title(r.title)
        people.append(
            {"name": name, "headline": headline, "url": r.url, "snippet": _clip(r.snippet)}
        )
    return _dump(people[:n])


ALL_TOOLS: list[BaseTool] = [
    search_builtin_jobs,
    search_builtin_companies,
    google_search,
    find_people,
]
