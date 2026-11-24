"""Search https://www.conservationjobboard.com for jobs.

The site has no public JSON API or feed: listing pages are server-rendered HTML. Filters
are encoded in the search path as numeric ids, ``/search/kw=wildlife&cat=1&state=6-5``
(several ids joined by ``-``), and the page number is appended as ``/2``. This module
builds those URLs and parses the job cards that come back.
"""

import re
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup, Tag

from .models import Job, JobFilter

BASE_URL = "https://www.conservationjobboard.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
REQUEST_DELAY_S = 1.0  # Be polite between page fetches.
MAX_PAGES = 10  # 15 jobs per page.
TIMEOUT_S = 30

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def search_path(job_filter: JobFilter, page: int = 1) -> str:
    """The site path listing jobs that match ``job_filter``, e.g.
    ``/search/kw=wildlife&cat=1&state=6-5/2``."""
    params: list[tuple[str, list[str]]] = []
    if job_filter.keyword and job_filter.keyword.strip():
        params.append(("kw", [quote(job_filter.keyword.strip(), safe="")]))
    params.append(("cat", [str(c.site_id) for c in job_filter.categories]))
    for key in ("state", "region"):
        params.append((key, [str(loc.site_id) for loc in job_filter.locations if loc.key == key]))
    params.append(("type", [str(t.site_id) for t in job_filter.job_types]))
    params.append(("experience", [str(e.site_id) for e in job_filter.experience_levels]))

    query = "&".join(f"{key}={'-'.join(values)}" for key, values in params if values)
    path = f"/search/{query}" if query else ""
    return f"{path}/{page}" if page > 1 else path or "/"


def _fetch(path: str) -> BeautifulSoup:
    response = _session.get(f"{BASE_URL}{path}", timeout=TIMEOUT_S)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _text(node: Tag | None) -> str | None:
    """Whitespace-normalized text of ``node`` or None if missing/empty."""
    if node is None:
        return None
    text = " ".join(node.get_text(" ", strip=True).split())
    return text or None


def _clean_url(href: str) -> str:
    """Absolute URL without query string or fragment (drops ``?from=feat-1`` etc.)."""
    parts = urlsplit(urljoin(BASE_URL, href))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _parse_card(link: Tag) -> Job | None:
    """Parse the card around a title link; None if essential fields are missing."""
    article = link.find_parent("article")
    job_id = str(link.get("job_id", ""))
    href = link.get("href")
    title = _text(link)
    if article is None or not job_id.isdigit() or not isinstance(href, str) or not title:
        return None

    rows: dict[str, str] = {}
    for row in article.select("p.listing__job__intro"):
        label = _text(row.select_one("span"))
        text = _text(row)
        if label and text:
            # "Salary : $20 - $22 per hour" -> {"salary": "$20 - $22 per hour"}
            rows[label.lower()] = re.sub(rf"^{re.escape(label)}\s*:\s*", "", text)

    return Job(
        id=int(job_id),
        title=title,
        url=_clean_url(href),
        organization=_text(article.select_one("h3")) or "",
        location=_text(article.select_one("h4")),
        job_type=rows.get("job type"),
        salary=rows.get("salary"),
        deadline=rows.get("deadline"),
        experience=rows.get("min. experience"),
        posted=_text(article.select_one(".listing__job__time")),
    )


def parse_jobs(soup: BeautifulSoup) -> list[Job]:
    """The filtered results on a listing page. Featured (paid, shown on every page whatever
    the filter), sidebar and sponsor cards are skipped."""
    links = soup.select('a.gtag-job-link[list_name="main-results-page"]')
    jobs = (_parse_card(link) for link in links)
    return [job for job in jobs if job is not None]


def get_jobs(job_filter: JobFilter, n: int) -> list[Job]:
    """Fetch up to ``n`` jobs matching ``job_filter``, unique by id.

    Fetches successive pages (at most ``MAX_PAGES``) until ``n`` jobs are collected or a
    page brings nothing new.
    """
    results: list[Job] = []
    seen: set[int] = set()
    for page in range(1, MAX_PAGES + 1):
        if len(results) >= n:
            break
        if page > 1:
            time.sleep(REQUEST_DELAY_S)
        jobs = parse_jobs(_fetch(search_path(job_filter, page)))
        new = [job for job in jobs if job.id not in seen]
        if not new:
            break
        seen.update(job.id for job in new)
        results.extend(new)
    return results[:n]
