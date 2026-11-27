"""BuiltIn (builtinnyc.com and sister sites) job pages: `https://builtinnyc.com/job/<slug>/<id>`.

The page embeds a schema.org `JobPosting` with the title, hiring organization, location and
the whole description. If a redesign drops it, the description block is read as HTML."""

from experience import years_required

from .jsonld import parse_jsonld, section_text
from .models import ParsedPosting

_DESCRIPTION = ["#job-post-body", ".job-description", "[data-id='job-description']"]


def parse_builtin(content: bytes | str, url: str) -> ParsedPosting | None:
    """The posting on a BuiltIn job page, or None when nothing readable is found."""
    parsed = parse_jsonld(content, url)
    if parsed is not None and parsed.description:
        return parsed
    description = section_text(content, _DESCRIPTION, url)
    if not description:
        return None
    return ParsedPosting(description=description, years_required=years_required(description))
