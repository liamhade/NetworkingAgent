"""Workable job pages: `https://apply.workable.com/<account>/j/<SHORTCODE>/`.

The page carries a schema.org `JobPosting`; failing that, its description, requirements and
benefits sections (`data-ui` attributes) are read as HTML."""

from experience import years_required

from .jsonld import parse_jsonld, section_text
from .models import ParsedPosting

_SECTIONS = [
    "[data-ui='job-description']",
    "[data-ui='job-requirements']",
    "[data-ui='job-benefits']",
]


def parse_workable(content: bytes | str, url: str) -> ParsedPosting | None:
    """The posting on a Workable job page, or None when nothing readable is found."""
    parsed = parse_jsonld(content, url)
    if parsed is not None and parsed.description:
        return parsed
    description = section_text(content, _SECTIONS, url)
    if not description:
        return None
    return ParsedPosting(description=description, years_required=years_required(description))
