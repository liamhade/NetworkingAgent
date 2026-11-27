"""Greenhouse: one posting's content from the per-job endpoint.

`GET https://boards-api.greenhouse.io/v1/boards/<slug>/jobs/<id>` returns that posting with
its `content` (HTML, entity-escaped). The board listing is not asked for `?content=true`: it is
about 12x larger and covers every job, while only the jobs worth ranking are read here."""

import html

from ats.base import get_json
from ats.greenhouse import API_BASE, GREENHOUSE
from experience import years_required
from read_page.convert import html_to_markdown

from .models import ParsedPosting


def fetch_greenhouse(url: str) -> ParsedPosting | None:
    """The Greenhouse posting at `url`, or None if the URL isn't a posting. Raises on HTTP
    errors."""
    ref = GREENHOUSE.parse_url(url)
    if ref is None or not ref.job_id:
        return None
    data = get_json(f"{API_BASE}/{ref.slug}/jobs/{ref.job_id}")
    if not isinstance(data, dict):
        return None
    description = html_to_markdown(html.unescape(str(data.get("content") or "")), url)
    location = data.get("location")
    return ParsedPosting(
        description=description,
        title=str(data.get("title") or "").strip(),
        company=str(data.get("company_name") or "").strip(),
        location=(location.get("name") or "").strip() if isinstance(location, dict) else "",
        posted_at=str(data.get("first_published") or data.get("updated_at") or "")[:10],
        years_required=years_required(description),
    )
