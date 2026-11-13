"""Greenhouse: hosted boards at (job-)boards(.eu).greenhouse.io, public Job Board API.

Board and posting URLs seen in the wild:

- ``https://job-boards.greenhouse.io/<slug>`` and ``.../<slug>/jobs/<id>`` (current)
- ``https://boards.greenhouse.io/<slug>`` and ``.../<slug>/jobs/<id>`` (older)
- the same on ``job-boards.eu.`` / ``boards.eu.`` for EU-hosted boards
- embeds: ``https://boards.greenhouse.io/embed/job_board?for=<slug>`` and
  ``.../embed/job_app?for=<slug>&token=<id>``

``GET https://boards-api.greenhouse.io/v1/boards/<slug>/jobs`` lists every open posting with
``id, title, absolute_url, location.name, company_name, first_published, updated_at``.
``?content=true`` adds the description, departments and offices but makes the response ~12x
larger, so it isn't used: the pipeline reads the full posting of the jobs it picks later
(``read_page``'s ``greenhouse_api`` method). Unknown boards return 404. There is no separate
EU API host (``boards-api.eu.greenhouse.io`` does not resolve).
"""

import re
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlsplit

from .base import Provider, get_json
from .models import AtsJob, BoardRef

API_BASE = "https://boards-api.greenhouse.io/v1/boards"

_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
_NOT_SLUGS = {"embed", "v1", "jobs"}


class Greenhouse(Provider):
    name: ClassVar[str] = "greenhouse"
    label: ClassVar[str] = "Greenhouse"
    site_domains: ClassVar[tuple[str, ...]] = ("job-boards.greenhouse.io", "boards.greenhouse.io")
    host_pattern: ClassVar[re.Pattern[str]] = re.compile(r"(job-)?boards(\.eu)?\.greenhouse\.io")

    def parse_url(self, url: str) -> BoardRef | None:
        url = url.strip()
        if not self.owns(url):
            return None
        parts = urlsplit(url)
        segments = [s for s in parts.path.split("/") if s]
        if not segments:
            return None
        if segments[0].lower() == "embed":
            query = parse_qs(parts.query)
            slug = (query.get("for") or [""])[0]
            token = (query.get("token") or [""])[0]
            if not _SLUG.fullmatch(slug):
                return None
            job_id = token if token.isdigit() else None
            return BoardRef(provider=self.name, slug=slug, job_id=job_id)
        slug = segments[0]
        if not _SLUG.fullmatch(slug) or slug.lower() in _NOT_SLUGS:
            return None
        job_id = None
        if len(segments) >= 3 and segments[1] == "jobs" and segments[2].isdigit():
            job_id = segments[2]
        return BoardRef(provider=self.name, slug=slug, job_id=job_id)

    def board_url(self, slug: str) -> str:
        return f"https://job-boards.greenhouse.io/{slug}"

    def list_jobs(self, slug: str) -> list[AtsJob]:
        data = get_json(f"{API_BASE}/{slug}/jobs")
        raw_jobs = data.get("jobs") if isinstance(data, dict) else None
        jobs = [job for raw in raw_jobs or [] if (job := self._job(slug, raw)) is not None]
        if any(not job.company for job in jobs):
            # company_name is normally on every posting; the board's name is the fallback.
            company = self._board_name(slug)
            jobs = [j if j.company else j.model_copy(update={"company": company}) for j in jobs]
        return jobs

    def _board_name(self, slug: str) -> str:
        try:
            info = get_json(f"{API_BASE}/{slug}")
        except Exception:  # noqa: BLE001 - the name is a nicety; the jobs are already here
            info = None
        name = info.get("name") if isinstance(info, dict) else None
        return (name or "").strip() or slug

    def _job(self, slug: str, raw: Any) -> AtsJob | None:
        if not isinstance(raw, dict):
            return None
        job_id, title = raw.get("id"), (raw.get("title") or "").strip()
        if job_id is None or not title:
            return None
        location = raw.get("location")
        departments = raw.get("departments") or []  # only with ?content=true
        posted = raw.get("first_published") or raw.get("updated_at") or ""
        return AtsJob(
            provider=self.name,
            board=slug,
            id=str(job_id),
            title=title,
            url=raw.get("absolute_url") or f"{self.board_url(slug)}/jobs/{job_id}",
            company=(raw.get("company_name") or "").strip(),
            location=(location.get("name") or "").strip() if isinstance(location, dict) else "",
            departments=[d["name"] for d in departments if isinstance(d, dict) and d.get("name")],
            posted=posted[:10] or None,
        )


GREENHOUSE = Greenhouse()
