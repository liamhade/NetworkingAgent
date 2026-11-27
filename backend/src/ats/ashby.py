"""Ashby: hosted boards at jobs.ashbyhq.com, public job-board API.

Board and posting URLs seen in the wild:

- ``https://jobs.ashbyhq.com/<org>`` (optionally with ``?departmentId=...`` filters)
- ``https://jobs.ashbyhq.com/<org>/<uuid>`` and ``.../<uuid>/application``

``GET https://api.ashbyhq.com/posting-api/job-board/<org>`` returns ``{"apiVersion", "jobs"}``.
Each job has ``id`` (UUID), ``title`` (sometimes with stray spaces), ``department``, ``team``,
``employmentType``, ``location`` (primary) and ``secondaryLocations`` (``[{"location": ...}]``),
``workplaceType`` (OnSite/Hybrid/Remote), ``isRemote``, ``isListed``, ``publishedAt`` (ISO
timestamp), ``jobUrl``, ``applyUrl``, ``address`` and the full description
(``descriptionHtml`` / ``descriptionPlain``). There is no company name (it is derived from the
slug) and no way to drop the descriptions: Ramp's 179 postings are 3.0 MB.
``?includeCompensation=true`` adds pay ranges (+7% on Ramp), but `AtsJob` has no pay field, so
the list call leaves it off. An unknown board answers ``404`` with the plain text "Not Found".

``isRemote`` is true for many hybrid postings (any remote-capable secondary location), so only
``workplaceType == "Remote"`` marks a posting remote here.
"""

import re
from typing import Any, ClassVar
from urllib.parse import urlsplit

from experience import years_required

from .base import Provider, get_json
from .lever import company_name
from .models import AtsJob, BoardRef

API_BASE = "https://api.ashbyhq.com/posting-api/job-board"

_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


class Ashby(Provider):
    name: ClassVar[str] = "ashby"
    label: ClassVar[str] = "Ashby"
    site_domains: ClassVar[tuple[str, ...]] = ("jobs.ashbyhq.com",)
    host_pattern: ClassVar[re.Pattern[str]] = re.compile(r"jobs\.ashbyhq\.com")

    def parse_url(self, url: str) -> BoardRef | None:
        url = url.strip()
        if not self.owns(url):
            return None
        segments = [s for s in urlsplit(url).path.split("/") if s]
        if not segments or not _SLUG.fullmatch(segments[0]):
            return None
        job_id = segments[1] if len(segments) >= 2 and _UUID.fullmatch(segments[1]) else None
        return BoardRef(provider=self.name, slug=segments[0], job_id=job_id)

    def board_url(self, slug: str) -> str:
        return f"https://jobs.ashbyhq.com/{slug}"

    def list_jobs(self, slug: str) -> list[AtsJob]:
        data = get_json(f"{API_BASE}/{slug}")
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            return []
        company = company_name(slug)
        return [job for raw in jobs if (job := self._job(slug, company, raw)) is not None]

    def _job(self, slug: str, company: str, raw: Any) -> AtsJob | None:
        if not isinstance(raw, dict) or raw.get("isListed") is False:
            return None
        job_id, title = raw.get("id"), _text(raw.get("title"))
        if not job_id or not title:
            return None
        return AtsJob(
            provider=self.name,
            board=slug,
            id=str(job_id),
            title=title,
            url=_text(raw.get("jobUrl")) or f"{self.board_url(slug)}/{job_id}",
            company=company,
            location=_location(raw),
            departments=_unique_names(raw.get("department"), raw.get("team")),
            posted=_date(raw.get("publishedAt")),
            years_required=years_required(_text(raw.get("descriptionPlain"))),
        )


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _unique_names(*values: Any) -> list[str]:
    return list(dict.fromkeys(name for v in values if (name := _text(v))))


def _location(raw: dict[str, Any]) -> str:
    """The primary and every secondary location ("New York, NY (HQ) / Remote (US)"), plus
    "(Remote)" for remote postings so a "remote" search matches them."""
    secondary = raw.get("secondaryLocations")
    others = [s.get("location") if isinstance(s, dict) else s for s in secondary or []]
    location = " / ".join(_unique_names(raw.get("location"), *others))
    if raw.get("workplaceType") == "Remote" and "remote" not in location.lower():
        return f"{location} (Remote)" if location else "Remote"
    return location


def _date(published: Any) -> str | None:
    """ISO timestamp ("2026-04-07T17:12:35.753+00:00") -> ISO date."""
    match = re.match(r"\d{4}-\d{2}-\d{2}", published) if isinstance(published, str) else None
    return match.group() if match else None


ASHBY = Ashby()
