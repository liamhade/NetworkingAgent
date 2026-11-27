"""Lever: hosted boards at jobs(.eu).lever.co, public Postings API.

Board and posting URLs seen in the wild:

- ``https://jobs.lever.co/<slug>`` (optionally ``?team=...&location=...`` filters)
- ``https://jobs.lever.co/<slug>/<uuid>`` and ``.../<uuid>/apply``
- the same on ``jobs.eu.lever.co`` for EU-hosted accounts

``GET https://api.lever.co/v0/postings/<slug>?mode=json`` lists every open posting as a JSON
array with ``id`` (UUID), ``text`` (title), ``hostedUrl``, ``applyUrl``, ``createdAt`` (epoch
ms), ``workplaceType`` (onsite/hybrid/remote), ``country``, ``categories`` (``location``,
``allLocations``, ``team``, ``department``, ``commitment``) and the full description
(``description``, ``lists``, ``additional`` and their ``*Plain`` twins). There is no way to
leave the descriptions out, so a big board is ~10 KB per posting (Spotify: 85 postings,
800 KB). There is no company name either: it is derived from the slug. EU accounts live on
``api.eu.lever.co``; both hosts answer ``404 {"ok":false,"error":"Document not found"}`` for
an unknown board, so `list_jobs` tries the US host first and the EU host on a 404.
"""

import re
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urlsplit

import requests

from experience import years_required

from .base import Provider, get_json
from .models import AtsJob, BoardRef

API_BASE = "https://api.lever.co/v0/postings"
EU_API_BASE = "https://api.eu.lever.co/v0/postings"

_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _not_found(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == 404


def company_name(slug: str) -> str:
    """ "acme-labs" -> "Acme Labs": the API has no company name, only the board slug."""
    words = [w for w in re.split(r"[-_.]+", slug) if w]
    return " ".join(w[:1].upper() + w[1:] for w in words) or slug


class Lever(Provider):
    name: ClassVar[str] = "lever"
    label: ClassVar[str] = "Lever"
    site_domains: ClassVar[tuple[str, ...]] = ("jobs.lever.co", "jobs.eu.lever.co")
    host_pattern: ClassVar[re.Pattern[str]] = re.compile(r"jobs(\.eu)?\.lever\.co")

    def __init__(self) -> None:
        self._eu_boards: set[str] = set()
        """Slugs (lowercase) found on the EU API, so `board_url` links the EU board."""

    def parse_url(self, url: str) -> BoardRef | None:
        url = url.strip()
        if not self.owns(url):
            return None
        segments = [s for s in urlsplit(url).path.split("/") if s]
        if not segments or not _SLUG.fullmatch(segments[0]):
            return None
        job_id = segments[1] if len(segments) >= 2 and _UUID.fullmatch(segments[1]) else None
        return BoardRef(provider=self.name, slug=segments[0], job_id=job_id)

    def is_eu(self, url: str) -> bool:
        """True for a URL on the EU board host (`jobs.eu.lever.co`)."""
        return urlsplit(url.strip()).netloc.lower() == "jobs.eu.lever.co"

    def api_base(self, url: str) -> str:
        """The Postings API base for a board/posting URL (EU boards have their own host)."""
        return EU_API_BASE if self.is_eu(url) else API_BASE

    def board_url(self, slug: str) -> str:
        host = "jobs.eu.lever.co" if slug.lower() in self._eu_boards else "jobs.lever.co"
        return f"https://{host}/{slug}"

    def list_jobs(self, slug: str) -> list[AtsJob]:
        params = {"mode": "json"}
        try:
            data = get_json(f"{API_BASE}/{slug}", params)
        except requests.HTTPError as exc:
            if not _not_found(exc):
                raise
            data = get_json(f"{EU_API_BASE}/{slug}", params)  # still 404: unknown board
            self._eu_boards.add(slug.lower())
        if not isinstance(data, list):
            return []
        company = company_name(slug)
        return [job for raw in data if (job := self._job(slug, company, raw)) is not None]

    def _job(self, slug: str, company: str, raw: Any) -> AtsJob | None:
        if not isinstance(raw, dict):
            return None
        job_id, title = raw.get("id"), (raw.get("text") or "").strip()
        if not job_id or not title:
            return None
        categories = raw.get("categories")
        categories = categories if isinstance(categories, dict) else {}
        return AtsJob(
            provider=self.name,
            board=slug,
            id=str(job_id),
            title=title,
            url=raw.get("hostedUrl") or f"{self.board_url(slug)}/{job_id}",
            company=company,
            location=_location(categories, raw.get("workplaceType")),
            departments=_unique_names(categories.get("department"), categories.get("team")),
            posted=_date(raw.get("createdAt")),
            years_required=years_required(*_description(raw)),
        )


def _description(raw: dict[str, Any]) -> list[str]:
    """The posting's plain-text description, its lists (requirements, ...) and closing text."""
    lists = raw.get("lists") if isinstance(raw.get("lists"), list) else []
    items = [
        re.sub(r"<[^>]+>", " ", item.get("content") or "")
        for item in lists
        if isinstance(item, dict) and isinstance(item.get("content"), str)
    ]
    plain = [raw.get(k) for k in ("descriptionPlain", "additionalPlain")]
    return [t for t in (*plain, *items) if isinstance(t, str)]


def _unique_names(*values: Any) -> list[str]:
    names = [v.strip() for v in values if isinstance(v, str) and v.strip()]
    return list(dict.fromkeys(names))


def _location(categories: dict[str, Any], workplace: Any) -> str:
    """Every location ("Stockholm / London"), plus "(Remote)" for remote postings so a
    "remote" search matches them."""
    all_locations = categories.get("allLocations")
    names = _unique_names(*(all_locations if isinstance(all_locations, list) else []))
    location = " / ".join(names or _unique_names(categories.get("location")))
    if workplace == "remote" and "remote" not in location.lower():
        return f"{location} (Remote)" if location else "Remote"
    return location


def _date(created_ms: Any) -> str | None:
    """Epoch milliseconds -> ISO date (UTC)."""
    if isinstance(created_ms, bool) or not isinstance(created_ms, int | float):
        return None
    try:
        return datetime.fromtimestamp(created_ms / 1000, UTC).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


LEVER = Lever()
