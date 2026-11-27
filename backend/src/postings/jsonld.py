"""Shared reading of a schema.org `JobPosting` (JSON-LD), which BuiltIn and Workable embed."""

import html
from typing import Any

from experience import years_required
from read_page.convert import html_to_markdown, soup_of
from read_page.methods import find_job_posting

from .models import ParsedPosting


def _name(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("name")
    return value.strip() if isinstance(value, str) else ""


def _location(posting: dict[str, Any]) -> str:
    raw = posting.get("jobLocation") or []
    places: list[str] = []
    for loc in raw if isinstance(raw, list) else [raw]:
        address = loc.get("address") if isinstance(loc, dict) else None
        if isinstance(address, dict):
            parts = [address.get(k) for k in ("addressLocality", "addressRegion")]
            place = ", ".join(p for p in parts if isinstance(p, str) and p)
            if place:
                places.append(place)
        elif isinstance(address, str) and address:
            places.append(address)
    if posting.get("jobLocationType") == "TELECOMMUTE":
        places.append("Remote")
    return " / ".join(dict.fromkeys(places))


def _salary(posting: dict[str, Any]) -> str:
    base = posting.get("baseSalary")
    value = base.get("value") if isinstance(base, dict) else None
    if not isinstance(base, dict) or not isinstance(value, dict):
        return ""
    low, high = value.get("minValue"), value.get("maxValue")
    if not (low or high):
        return ""
    amount = f"{low}-{high}" if low and high else str(low or high)
    unit = value.get("unitText")
    return " ".join(p for p in (base.get("currency"), amount, unit and f"per {unit.lower()}") if p)


def parse_jsonld(content: bytes | str, url: str) -> ParsedPosting | None:
    """The page's JSON-LD `JobPosting` as a `ParsedPosting`, or None if it has none."""
    posting = find_job_posting(content)
    if posting is None:
        return None
    description = html_to_markdown(html.unescape(str(posting.get("description") or "")), url)
    return ParsedPosting(
        description=description,
        title=_name(posting.get("title")),
        company=_name(posting.get("hiringOrganization")),
        location=_location(posting),
        salary=_salary(posting),
        posted_at=str(posting.get("datePosted") or "")[:10],
        years_required=years_required(description),
    )


def section_text(content: bytes | str, selectors: list[str], url: str) -> str:
    """Markdown of the first element matching each CSS selector, joined (HTML fallback)."""
    soup = soup_of(content)
    parts = [
        html_to_markdown(str(node), url)
        for selector in selectors
        if (node := soup.select_one(selector)) is not None
    ]
    return "\n\n".join(p for p in parts if p)
