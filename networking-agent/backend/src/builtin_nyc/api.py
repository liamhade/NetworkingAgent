"""Search https://www.builtinnyc.com for jobs and companies.

BuiltInNYC has no public JSON API: the listing pages are server-rendered HTML.
Filters are encoded as URL path segments (``/jobs/hybrid/senior``) plus a
``search`` query parameter, and appending ``handler=SearchResults`` returns only the list
fragment. This module builds those URLs and parses the cards that come back.
"""

import re
import time
from collections.abc import Callable
from typing import TypeVar
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup, Tag

from .models import Company, CompanyFilter, Job, JobFilter

BASE_URL = "https://www.builtinnyc.com"
USER_AGENT = "Mozilla/5.0 (compatible; networking-agent/0.1)"
REQUEST_DELAY_S = 0.5  # Be polite between page fetches.
MAX_PAGES = 1000  # The site caps pagination at 1000 pages.
TIMEOUT_S = 30

T = TypeVar("T", Job, Company)

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def _fetch(path: str, params: dict[str, str]) -> BeautifulSoup:
    """GET the list fragment for ``path`` and parse it."""
    query = urlencode({**params, "handler": "SearchResults"})
    response = _session.get(f"{BASE_URL}{path}?{query}", timeout=TIMEOUT_S)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _paginate(
    path: str,
    params: dict[str, str],
    parse_page: Callable[[BeautifulSoup], list[T]],
    n: int,
) -> list[T]:
    """Fetch successive pages until ``n`` items (unique by ``id``) are collected or results
    run out."""
    results: list[T] = []
    seen: set[int] = set()
    for page in range(1, MAX_PAGES + 1):
        if len(results) >= n:
            break
        if page > 1:
            time.sleep(REQUEST_DELAY_S)
        items = parse_page(_fetch(path, {**params, "page": str(page)}))
        new = [item for item in items if item.id not in seen]
        if not new:
            break
        seen.update(item.id for item in new)
        results.extend(new)
    return results[:n]


def _text(node: Tag | None) -> str | None:
    """Stripped text of ``node`` or None if missing/empty."""
    if node is None:
        return None
    text = " ".join(node.get_text(" ", strip=True).split())
    return text or None


def _abs(url: str | None) -> str | None:
    """Make a site-relative URL absolute."""
    return urljoin(BASE_URL, url) if url else None


def _int(text: str | None) -> int | None:
    """First integer in ``text`` (commas allowed), or None."""
    match = re.search(r"\d[\d,]*", text or "")
    return int(match.group().replace(",", "")) if match else None


# --------------------------------------------------------------------------- jobs


def _job_path_and_params(job_filter: JobFilter) -> tuple[str, dict[str, str]]:
    """Translate a JobFilter into the site's ``/jobs/<aliases>`` path and query string."""
    segments = ["jobs"]
    segments += [p.value for p in job_filter.remote_preferences]
    if job_filter.category:
        segments.append(job_filter.category.value)
    segments += [e.value for e in job_filter.experience_levels]
    params = {"search": job_filter.search} if job_filter.search else {}
    return "/" + "/".join(segments), params


def _icon_text(card: Tag, icon_class: str) -> str | None:
    """Text next to the first icon with ``icon_class`` (fa-location-dot, ...)."""
    icon = card.select_one(f"i.{icon_class}")
    if icon is None:
        return None
    row = icon.find_parent("div", class_=re.compile("d-flex"))
    while row is not None and not _text(row):
        row = row.find_parent("div", class_=re.compile("d-flex"))
    return _text(row)


def _parse_job_card(card: Tag) -> Job | None:
    """Parse one ``div[data-id=job-card]``; None if essential fields are missing."""
    title_link = card.select_one('a[data-id="job-card-title"]')
    company_link = card.select_one('a[data-id="company-title"]')
    job_id = _int(card.get("id", "")) if isinstance(card.get("id"), str) else None
    if title_link is None or company_link is None or job_id is None:
        return None

    detail = card.select_one('div[id^="drop-data-"]')
    summary = None
    industries: list[str] = []
    if detail is not None:
        industries_div = detail.select_one("div.fw-bold")
        industries = [i.strip() for i in (_text(industries_div) or "").split("•") if i.strip()]
        summary = _text(detail.select_one("div.fw-regular"))
    skills = [s.get_text(strip=True) for s in card.select("span.fs-xs.text-gray-04.mx-sm")]

    posted_tag = card.select_one("i.fa-clock")
    return Job(
        id=job_id,
        title=_text(title_link) or "",
        url=_abs(title_link.get("href")) or "",
        company_name=_text(company_link) or "",
        company_url=_abs(company_link.get("href")),
        posted=_text(posted_tag.parent) if posted_tag else None,
        work_arrangement=_icon_text(card, "fa-house-building"),
        location=_icon_text(card, "fa-location-dot"),
        salary=_icon_text(card, "fa-sack-dollar"),
        experience_level=_icon_text(card, "fa-trophy"),
        industries=industries,
        skills=skills,
        description=summary,
    )


def _parse_jobs(soup: BeautifulSoup) -> list[Job]:
    """All jobs found in a results fragment."""
    jobs = (_parse_job_card(c) for c in soup.select('div[data-id="job-card"]'))
    return [j for j in jobs if j is not None]


def get_jobs(job_filter: JobFilter, n: int) -> list[Job]:
    """Fetch up to ``n`` job listings matching ``job_filter``.

    Args:
        job_filter: Which jobs to look for.
        n: Maximum number of jobs to return (fewer if the site runs out).
    """
    path, params = _job_path_and_params(job_filter)
    return _paginate(path, params, _parse_jobs, n)


# ---------------------------------------------------------------------- companies


def _company_path(company_filter: CompanyFilter) -> str:
    """Translate a CompanyFilter into the site's ``/companies/<facet>/<values>`` path."""
    path = "/companies"
    if company_filter.hiring_only:
        path += "/hiring/open-jobs"
    if company_filter.fully_remote:
        path += "/location/fully-remote"
    if company_filter.industries:
        path += "/type/" + "/".join(f"{i}-companies" for i in company_filter.industries)
    if company_filter.sizes:
        path += "/size/" + "/".join(s.value for s in company_filter.sizes)
    if company_filter.tech_stack:
        path += "/tech/" + "/".join(f"{t}-companies" for t in company_filter.tech_stack)
    return path


def _parse_company_card(card: Tag) -> Company | None:
    """Parse one ``div.company-card-horizontal``; None if essential fields are missing."""
    overlay = card.select_one("a.company-card-overlay")
    name = _text(card.select_one("h2"))
    if overlay is None or not name:
        return None
    company_id = _int(str(overlay.get("data-company-id", "")))
    if company_id is None:
        return None

    tooltip = card.select_one('[aria-label="Office locations"]')
    locations: list[str] = []
    if tooltip is not None:
        raw = str(tooltip.get("data-bs-title", ""))
        locations = [p.strip() for p in raw.split("<br/>") if p.strip()]
    industries_div = card.select_one("div.company-info-section div.text-gray-04")
    industries = [i.strip() for i in re.split(r"[•�]", _text(industries_div) or "") if i.strip()]
    employees = next(
        (
            t
            for s in card.select("span.text-gray-03")
            if "Employee" in (t := s.get_text(strip=True))
        ),
        None,
    )
    tagline = card.select_one("div.company-tagline-4-rows")

    return Company(
        id=company_id,
        name=name,
        url=_abs(str(overlay.get("href", ""))) or "",
        industries=industries,
        office_locations=locations,
        employee_count=employees,
        is_hiring=card.select_one('a[data-track-id="jobs_all"]') is not None,
        mission=_text(tagline.select_one("strong")) if tagline else None,
        description=_text(tagline.select_one("p")) if tagline else None,
    )


def _parse_companies(soup: BeautifulSoup) -> list[Company]:
    """All companies found in a results fragment."""
    cards = soup.select("div.company-card-horizontal")
    companies = (_parse_company_card(c) for c in cards)
    return [c for c in companies if c is not None]


def get_companies(company_filter: CompanyFilter, n: int) -> list[Company]:
    """Fetch up to ``n`` companies matching ``company_filter``.

    Args:
        company_filter: Which companies to look for.
        n: Maximum number of companies to return (fewer if the site runs out).
    """
    return _paginate(_company_path(company_filter), {}, _parse_companies, n)
