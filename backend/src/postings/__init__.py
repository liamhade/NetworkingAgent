"""Readers that turn a job posting URL into its full text and fields.

`reader_for(url)` picks the board API (Greenhouse per-job content) or the site parser
(BuiltIn, Workable) for a URL; other URLs fall back to the generic `read_page` in the
pipeline's `steps.complete`. Parsers take HTML, so they are tested on small fixtures.
"""

from .models import ParsedPosting
from .registry import Reader, reader_for

__all__ = ["ParsedPosting", "Reader", "reader_for"]
