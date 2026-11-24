"""Search https://www.usajobs.gov through its official API (https://developer.usajobs.gov).

`GET https://data.usajobs.gov/api/search` with the headers `Host`, `User-Agent` (the email the
key was registered with) and `Authorization-Key`. Multiple values of a parameter are
semicolon-delimited. The credentials only ever go into those headers: they are never put in
the URL, logged or placed in an exception message.
"""

import requests

from .models import Job, JobFilter

SEARCH_URL = "https://data.usajobs.gov/api/search"
HOST = "data.usajobs.gov"
MAX_RESULTS = 500  # The API's largest page size.
TIMEOUT_S = 30

_session = requests.Session()


class UsajobsError(RuntimeError):
    """A failed USAJOBS request. Its message never contains the credentials."""


def request_headers(api_key: str, email: str) -> dict[str, str]:
    return {"Host": HOST, "User-Agent": email, "Authorization-Key": api_key}


def search_params(job_filter: JobFilter, n: int) -> dict[str, str]:
    """Query parameters for `job_filter`, asking for `n` results (one page)."""
    params = {"ResultsPerPage": str(max(1, min(n, MAX_RESULTS))), "WhoMayApply": "public"}
    if job_filter.keyword and job_filter.keyword.strip():
        params["Keyword"] = job_filter.keyword.strip()
    if job_filter.location and job_filter.location.strip():
        params["LocationName"] = job_filter.location.strip()
        if job_filter.radius_miles:
            params["Radius"] = str(job_filter.radius_miles)
    if job_filter.agencies:
        codes = dict.fromkeys(a.code for a in job_filter.agencies)  # dedupe, keep order
        params["Organization"] = ";".join(codes)
    if job_filter.remote:
        params["RemoteIndicator"] = "True"
    if job_filter.days_posted is not None:
        params["DatePosted"] = str(max(0, min(job_filter.days_posted, 60)))
    return params


def _str(value: object) -> str | None:
    text = " ".join(str(value).split()) if value is not None else ""
    return text or None


def _date(value: object) -> str | None:
    """`2026-11-01T00:00:00.0000` -> `2026-11-01`."""
    text = _str(value)
    return text[:10] if text else None


def _money(value: object) -> str | None:
    try:
        amount = float(str(value))
    except ValueError:
        return None
    return f"${amount:,.0f}" if amount.is_integer() else f"${amount:,.2f}"


def _salary(remuneration: object) -> str | None:
    """`$92,108 - $119,746 per year` from the first `PositionRemuneration` entry."""
    if not isinstance(remuneration, list) or not remuneration or not remuneration[0]:
        return None
    first = remuneration[0]
    low, high = _money(first.get("MinimumRange")), _money(first.get("MaximumRange"))
    amount = " - ".join(dict.fromkeys(m for m in (low, high) if m))
    if not amount:
        return None
    interval = (_str(first.get("Description")) or "").lower()
    return f"{amount} {interval}".strip()


def _labels(items: object, key: str = "Name") -> list[str]:
    if not isinstance(items, list):
        return []
    return [text for i in items if isinstance(i, dict) and (text := _str(i.get(key)))]


def parse_job(item: dict) -> Job | None:
    """A `SearchResultItems` entry as a `Job`; None without a title or URL."""
    d = item.get("MatchedObjectDescriptor") or {}
    title, url = _str(d.get("PositionTitle")), _str(d.get("PositionURI"))
    if not title or not url:
        return None
    apply_urls = d.get("ApplyURI")
    job_type = " · ".join(
        dict.fromkeys(_labels(d.get("PositionOfferingType")) + _labels(d.get("PositionSchedule")))
    )
    return Job(
        title=title,
        url=url,
        apply_url=_str(apply_urls[0]) if isinstance(apply_urls, list) and apply_urls else None,
        agency=_str(d.get("OrganizationName")),
        department=_str(d.get("DepartmentName")),
        location=_str(d.get("PositionLocationDisplay")),
        salary=_salary(d.get("PositionRemuneration")),
        job_type=job_type or None,
        posted=_date(d.get("PublicationStartDate")),
        closes=_date(d.get("ApplicationCloseDate")),
        summary=_str(d.get("QualificationSummary")),
    )


def parse_response(payload: object) -> list[Job]:
    """Every parseable job in a search response (malformed items are skipped)."""
    if not isinstance(payload, dict):
        raise UsajobsError("USAJOBS returned an unexpected response")
    result = payload.get("SearchResult")
    items = result.get("SearchResultItems") if isinstance(result, dict) else None
    jobs = (parse_job(i) for i in items or [] if isinstance(i, dict))
    return [j for j in jobs if j]


def search_jobs(job_filter: JobFilter, n: int, api_key: str, email: str) -> list[Job]:
    """Open federal jobs matching `job_filter`, at most `n`. Raises `UsajobsError`."""
    try:
        response = _session.get(
            SEARCH_URL,
            params=search_params(job_filter, n),
            headers=request_headers(api_key, email),
            timeout=TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise UsajobsError(f"USAJOBS request failed ({type(exc).__name__})") from None
    status = response.status_code
    if status in (401, 403):
        raise UsajobsError(f"USAJOBS rejected the API key or email (HTTP {status})")
    if status == 429:
        raise UsajobsError("USAJOBS rate limit reached (HTTP 429)")
    if status >= 400:
        raise UsajobsError(f"USAJOBS error (HTTP {status})")
    try:
        payload = response.json()
    except ValueError:
        raise UsajobsError("USAJOBS returned a response that is not JSON") from None
    return parse_response(payload)[:n]
