"""One reader per method. Each takes a URL (or already-fetched HTML) and returns a PageResult.

Results are never truncated here; `core.read_page` does that.
"""

import html
import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

from ats.ashby import ASHBY
from ats.greenhouse import GREENHOUSE
from ats.lever import LEVER

from . import browser
from . import fetch as fetch_mod
from .convert import (
    cleaned_full_markdown,
    html_to_markdown,
    page_title,
    soup_of,
    trafilatura_markdown,
    trafilatura_title,
)
from .models import MethodUnavailable, PageResult, ReadPageError

# --------------------------------------------------------------------- generic HTML


def static_from_html(url: str, final_url: str, content: bytes | str) -> PageResult:
    md = trafilatura_markdown(content, final_url)
    title = trafilatura_title(content, final_url) or page_title(soup_of(content))
    return PageResult(url=url, final_url=final_url, method="static", title=title, markdown=md)


def full_from_html(url: str, final_url: str, content: bytes | str) -> PageResult:
    md = cleaned_full_markdown(content, final_url)
    title = page_title(soup_of(content))
    return PageResult(url=url, final_url=final_url, method="full", title=title, markdown=md)


def read_static(url: str) -> PageResult:
    f = fetch_mod.fetch(url)
    return static_from_html(url, f.final_url, f.content)


def read_full(url: str) -> PageResult:
    f = fetch_mod.fetch(url)
    return full_from_html(url, f.final_url, f.content)


def read_browser(url: str) -> PageResult:
    final_url, rendered = browser.render(url)
    result = static_from_html(url, final_url, rendered)
    return result.model_copy(update={"method": "browser"})


# ------------------------------------------------------------------ JSON-LD JobPosting


def _walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        yield node
        if "@graph" in node:
            yield from _walk(node["@graph"])


def _is_job_posting(node: dict[str, Any]) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return "JobPosting" in kinds


def find_job_posting(content: bytes | str) -> dict[str, Any] | None:
    soup = soup_of(content)
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or script.get_text() or "", strict=False)
        except json.JSONDecodeError:
            continue
        for node in _walk(data):
            if _is_job_posting(node):
                return node
    return None


def _name(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("name") or None
    if isinstance(value, str):
        return value or None
    return None


def _locations(posting: dict[str, Any]) -> list[str]:
    raw = posting.get("jobLocation") or []
    out: list[str] = []
    for loc in raw if isinstance(raw, list) else [raw]:
        if not isinstance(loc, dict):
            continue
        addr = loc.get("address")
        if isinstance(addr, dict):
            parts = [
                addr.get(k)
                for k in ("addressLocality", "addressRegion", "addressCountry")
                if isinstance(addr.get(k), str)
            ]
            if parts:
                out.append(", ".join(parts))
        elif isinstance(addr, str):
            out.append(addr)
        elif loc.get("name"):
            out.append(str(loc["name"]))
    if posting.get("jobLocationType") == "TELECOMMUTE":
        out.append("Remote")
    return out


def _salary(posting: dict[str, Any]) -> str | None:
    base = posting.get("baseSalary")
    if not isinstance(base, dict):
        return None
    value = base.get("value")
    currency = base.get("currency", "")
    if isinstance(value, dict):
        low, high = value.get("minValue"), value.get("maxValue")
        unit = value.get("unitText", "")
        amount = f"{low}-{high}" if low and high else str(low or high or value.get("value") or "")
        return " ".join(p for p in (currency, amount, unit and f"per {unit.lower()}") if p) or None
    return f"{currency} {value}".strip() if value else None


def _field_lines(fields: list[tuple[str, Any]]) -> list[str]:
    lines = []
    for label, value in fields:
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value if v)
        if value:
            lines.append(f"- **{label}:** {value}")
    return lines


def job_posting_markdown(posting: dict[str, Any], url: str) -> tuple[str | None, str]:
    title = posting.get("title") or None
    lines = [f"# {title}"] if title else []
    lines += _field_lines(
        [
            ("Company", _name(posting.get("hiringOrganization"))),
            ("Location", _locations(posting)),
            ("Employment type", posting.get("employmentType")),
            ("Salary", _salary(posting)),
            ("Date posted", posting.get("datePosted")),
            ("Valid through", posting.get("validThrough")),
        ]
    )
    description = posting.get("description") or ""
    if description:
        lines += ["", html_to_markdown(html.unescape(description), url)]
    return title, "\n".join(lines).strip()


def jsonld_from_html(url: str, final_url: str, content: bytes | str) -> PageResult:
    posting = find_job_posting(content)
    if posting is None:
        raise MethodUnavailable("No JSON-LD JobPosting on the page")
    title, md = job_posting_markdown(posting, final_url)
    return PageResult(url=url, final_url=final_url, method="jsonld", title=title, markdown=md)


def read_jsonld(url: str) -> PageResult:
    f = fetch_mod.fetch(url)
    return jsonld_from_html(url, f.final_url, f.content)


# -------------------------------------------------------------------------- ATS APIs


def _not_found(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == 404


def _api(url: str, params: dict[str, str] | None = None) -> Any:
    try:
        return fetch_mod.get_json(url, params)
    except Exception as exc:
        if _not_found(exc):
            raise MethodUnavailable(f"Not found in the API: {url}") from exc
        raise


def greenhouse_ids(url: str) -> tuple[str, str]:
    """(board slug, job id) of a Greenhouse posting URL; the URL rules live in `ats`."""
    ref = GREENHOUSE.parse_url(url)
    if ref is not None and ref.job_id:
        return ref.slug, ref.job_id
    raise MethodUnavailable("Not a Greenhouse job URL")


def read_greenhouse(url: str) -> PageResult:
    board, job_id = greenhouse_ids(url)
    data = _api(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}",
        {"pay_transparency": "true"},
    )
    title = data.get("title") or None
    pay = [
        f"{r.get('currency_type', '')} {r.get('min_cents', 0) // 100:,}-"
        f"{r.get('max_cents', 0) // 100:,} ({r.get('title', '')})".strip()
        for r in data.get("pay_input_ranges") or []
        if isinstance(r, dict) and r.get("min_cents") is not None
    ]
    final_url = data.get("absolute_url") or url
    lines = [f"# {title}"] if title else []
    lines += _field_lines(
        [
            ("Company", data.get("company_name")),
            ("Location", _name(data.get("location"))),
            ("Departments", [_name(d) for d in data.get("departments") or []]),
            ("Offices", [_name(o) for o in data.get("offices") or []]),
            ("Pay", pay),
            ("Updated", data.get("updated_at")),
            ("Apply", final_url),
        ]
    )
    content = data.get("content") or ""
    if content:
        lines += ["", html_to_markdown(html.unescape(content), final_url)]
    return PageResult(
        url=url,
        final_url=final_url,
        method="greenhouse_api",
        title=title,
        markdown="\n".join(lines).strip(),
    )


def lever_api_url(url: str) -> str:
    """The Postings API URL of a Lever posting URL; the URL rules live in `ats`."""
    ref = LEVER.parse_url(url)
    if ref is not None and ref.job_id:
        return f"{LEVER.api_base(url)}/{ref.slug}/{ref.job_id}"
    raise MethodUnavailable("Not a Lever job URL")


def read_lever(url: str) -> PageResult:
    data = _api(lever_api_url(url))
    title = data.get("text") or None
    categories = data.get("categories") or {}
    final_url = data.get("hostedUrl") or url
    lines = [f"# {title}"] if title else []
    lines += _field_lines(
        [
            ("Location", categories.get("location") or categories.get("allLocations")),
            ("Team", categories.get("team")),
            ("Department", categories.get("department")),
            ("Commitment", categories.get("commitment")),
            ("Workplace", data.get("workplaceType")),
            ("Apply", data.get("applyUrl")),
        ]
    )
    if data.get("description"):
        lines += ["", html_to_markdown(data["description"], final_url)]
    for section in data.get("lists") or []:
        lines += ["", f"## {section.get('text', '')}".rstrip()]
        lines.append(html_to_markdown(f"<ul>{section.get('content', '')}</ul>", final_url))
    if data.get("additional"):
        lines += ["", html_to_markdown(data["additional"], final_url)]
    return PageResult(
        url=url,
        final_url=final_url,
        method="lever_api",
        title=title,
        markdown="\n".join(lines).strip(),
    )


ASHBY_TTL = 600.0
"""Seconds to keep an Ashby board (the API has no single-job endpoint)."""

_ashby_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_ashby_lock = threading.Lock()


def _ashby_board(org: str, now: Callable[[], float] = time.monotonic) -> list[dict[str, Any]]:
    with _ashby_lock:
        hit = _ashby_cache.get(org)
        if hit and now() - hit[0] < ASHBY_TTL:
            return hit[1]
    data = _api(
        f"https://api.ashbyhq.com/posting-api/job-board/{org}", {"includeCompensation": "true"}
    )
    jobs = data.get("jobs") or []
    with _ashby_lock:
        _ashby_cache[org] = (now(), jobs)
    return jobs


def read_ashby(url: str) -> PageResult:
    ref = ASHBY.parse_url(url)  # the URL rules live in `ats`
    if ref is None or not ref.job_id:
        raise MethodUnavailable("Not an Ashby job URL")
    job = next(
        (j for j in _ashby_board(ref.slug) if str(j.get("id")).lower() == ref.job_id.lower()), None
    )
    if job is None:
        raise MethodUnavailable("Job not on the Ashby board (it may be closed or unlisted)")
    title = job.get("title") or None
    final_url = job.get("jobUrl") or url
    comp = job.get("compensation") or {}
    lines = [f"# {title}"] if title else []
    lines += _field_lines(
        [
            ("Location", job.get("location")),
            ("Remote", "yes" if job.get("isRemote") else None),
            ("Department", job.get("department")),
            ("Team", job.get("team")),
            ("Employment type", job.get("employmentType")),
            ("Compensation", comp.get("compensationTierSummary") or comp.get("scrapeableSummary")),
            ("Published", job.get("publishedAt")),
            ("Apply", job.get("applyUrl")),
        ]
    )
    if job.get("descriptionHtml"):
        lines += ["", html_to_markdown(job["descriptionHtml"], final_url)]
    elif job.get("descriptionPlain"):
        lines += ["", job["descriptionPlain"]]
    return PageResult(
        url=url,
        final_url=final_url,
        method="ashby_api",
        title=title,
        markdown="\n".join(lines).strip(),
    )


# --------------------------------------------------------------------------- lookup

Reader = Callable[[str], PageResult]

READERS: dict[str, Reader] = {
    "static": read_static,
    "full": read_full,
    "browser": read_browser,
    "jsonld": read_jsonld,
    "greenhouse_api": read_greenhouse,
    "lever_api": read_lever,
    "ashby_api": read_ashby,
}


def reader(method: str) -> Reader:
    try:
        return READERS[method]
    except KeyError:
        raise ReadPageError(
            f"Unknown method {method!r}; choose one of: auto, {', '.join(READERS)}"
        ) from None
