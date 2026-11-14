"""Workable: hosted boards at apply.workable.com, public widget API.

Board and posting URLs seen in the wild:

- ``https://apply.workable.com/<account>/`` (board) and ``.../<account>/j/<SHORTCODE>/``
  (posting; ``/apply`` and query strings follow it)
- legacy ``https://<account>.workable.com/`` and ``.../jobs/<id>``

``GET https://apply.workable.com/api/v1/widget/accounts/<account>`` needs no key and returns
every open posting in one response: ``{"name", "description", "jobs": [...]}``. There is no
pagination and no description in the postings (Hugging Face: 6 postings, 4 KB). ``name`` is
the real company name ("Hugging Face"). Each job has ``title``, ``shortcode``, ``url``
(``https://apply.workable.com/j/<SHORTCODE>``, without the account), ``application_url``,
``department``, ``function``, ``employment_type``, ``telecommuting``, ``published_on``,
``created_at``, ``country``/``state``/``city`` and ``locations`` (``city``, ``region``,
``country``, ``hidden``). An unknown account answers ``404`` with the plain text "Not Found";
an account whose boards are hosted elsewhere (e.g. Canonical) answers ``200`` with no jobs.

The v3 ``POST /api/v3/accounts/<account>/jobs`` endpoint (``{"results", "total", "nextPage"}``,
paged with a token) has the same postings with fewer fields, so the widget is used instead.
"""

import re
from typing import Any, ClassVar
from urllib.parse import urlsplit

from .base import Provider, get_json
from .models import AtsJob, BoardRef

API_BASE = "https://apply.workable.com/api/v1/widget/accounts"

_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_RESERVED_PATHS = {"api", "j", "assets", "static", "img"}
"""First path segments of apply.workable.com that are not accounts."""
_NOT_ACCOUNTS = {
    "www", "apply", "api", "resources", "help", "support", "blog", "status", "developers",
    "careers", "jobs", "app", "docs", "learn", "community", "partners", "marketplace",
}  # fmt: skip
"""Workable's own subdomains: `<name>.workable.com` is a legacy board only for other names."""


class Workable(Provider):
    name: ClassVar[str] = "workable"
    label: ClassVar[str] = "Workable"
    site_domains: ClassVar[tuple[str, ...]] = ("apply.workable.com",)
    host_pattern: ClassVar[re.Pattern[str]] = re.compile(r"[a-z0-9-]+\.workable\.com")

    def parse_url(self, url: str) -> BoardRef | None:
        url = url.strip()
        if not self.owns(url):
            return None
        parts = urlsplit(url)
        host = parts.netloc.lower()
        segments = [s for s in parts.path.split("/") if s]
        if host == "apply.workable.com":
            if not segments or segments[0].lower() in _RESERVED_PATHS:
                return None
            slug, rest = segments[0], segments[1:]
            marker = "j"
        else:
            slug, rest = host.removesuffix(".workable.com"), segments
            if slug in _NOT_ACCOUNTS:
                return None
            marker = "jobs"
        if not _SLUG.fullmatch(slug):
            return None
        job_id = rest[1] if len(rest) >= 2 and rest[0].lower() == marker else None
        if job_id is not None:
            job_id = job_id.upper() if _SLUG.fullmatch(job_id) else None
        return BoardRef(provider=self.name, slug=slug, job_id=job_id)

    def board_url(self, slug: str) -> str:
        return f"https://apply.workable.com/{slug}/"

    def list_jobs(self, slug: str) -> list[AtsJob]:
        data = get_json(f"{API_BASE}/{slug}")
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            return []
        company = _text(data.get("name")) or slug
        return [job for raw in data["jobs"] if (job := self._job(slug, company, raw)) is not None]

    def _job(self, slug: str, company: str, raw: Any) -> AtsJob | None:
        if not isinstance(raw, dict):
            return None
        code, title = _text(raw.get("shortcode")), _text(raw.get("title"))
        if not code or not title:
            return None
        return AtsJob(
            provider=self.name,
            board=slug,
            id=code.upper(),
            title=title,
            url=_text(raw.get("url")) or f"{self.board_url(slug)}j/{code}/",
            company=company,
            location=_location(raw),
            departments=_unique(raw.get("department"), raw.get("function")),
            posted=_date(raw.get("published_on")) or _date(raw.get("created_at")),
        )


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _unique(*values: Any) -> list[str]:
    return list(dict.fromkeys(name for v in values if (name := _text(v))))


def _place(raw: dict[str, Any]) -> str:
    """ "Paris, Île-de-France, France" (a region equal to the city is not repeated)."""
    city = _text(raw.get("city"))
    region = _text(raw.get("region") if "region" in raw else raw.get("state"))
    return ", ".join(_unique(city, region if region != city else "", raw.get("country")))


def _location(raw: dict[str, Any]) -> str:
    """Every listed place joined with " / ", plus "(Remote)" for telecommuting postings so a
    "remote" search matches them. Hidden locations (street address hidden) still name a
    country, so they are kept."""
    places = raw.get("locations")
    places = [p for p in places if isinstance(p, dict)] if isinstance(places, list) else []
    location = " / ".join(_unique(*(_place(p) for p in places))) or _place(raw)
    if raw.get("telecommuting") and "remote" not in location.lower():
        return f"{location} (Remote)" if location else "Remote"
    return location


def _date(published: Any) -> str | None:
    """ "2026-05-29" or an ISO timestamp -> ISO date."""
    match = re.match(r"\d{4}-\d{2}-\d{2}", published) if isinstance(published, str) else None
    return match.group() if match else None


WORKABLE = Workable()
