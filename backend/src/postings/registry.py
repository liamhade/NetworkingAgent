"""Which reader completes a posting URL: a board API or a site parser (else the generic page)."""

import re
from collections.abc import Callable

from read_page import fetch as fetch_mod
from read_page import methods

from .builtin import parse_builtin
from .greenhouse import fetch_greenhouse
from .models import ParsedPosting
from .workable import parse_workable

Reader = Callable[[str], ParsedPosting | None]
"""Takes a posting URL; returns what it found (None: nothing readable). Raises on HTTP errors."""


def _from_page(parse: Callable[[bytes | str, str], ParsedPosting | None]) -> Reader:
    def read(url: str) -> ParsedPosting | None:
        fetched = fetch_mod.fetch(url)
        return parse(fetched.content, fetched.final_url)

    return read


def _from_method(method: str) -> Reader:
    """A `read_page` method that calls a board's per-posting API (full text as Markdown)."""

    def read(url: str) -> ParsedPosting | None:
        page = methods.READERS[method](url)
        return ParsedPosting(description=page.markdown.strip())

    return read


_RULES: list[tuple[re.Pattern[str], str, str, Reader]] = [
    (
        re.compile(r"^https?://(job-)?boards(\.eu)?\.greenhouse\.io/[^/?#]+/jobs/\d+", re.I),
        "greenhouse_api",
        "api",
        fetch_greenhouse,
    ),
    (
        re.compile(r"^https?://jobs(\.eu)?\.lever\.co/[^/?#]+/[0-9a-f-]{36}", re.I),
        "lever_api",
        "api",
        _from_method("lever_api"),
    ),
    (
        re.compile(r"^https?://jobs\.ashbyhq\.com/[^/?#]+/[0-9a-f-]{36}", re.I),
        "ashby_api",
        "api",
        _from_method("ashby_api"),
    ),
    (
        re.compile(r"^https?://(www\.)?builtin[a-z]*\.com/job/", re.I),
        "builtin_parser",
        "parser",
        _from_page(parse_builtin),
    ),
    (
        re.compile(r"^https?://apply\.workable\.com/[^/?#]+/j/", re.I),
        "workable_parser",
        "parser",
        _from_page(parse_workable),
    ),
]


def reader_for(url: str) -> tuple[str, str, Reader] | None:
    """(trace source, text_source, reader) for a posting URL the package knows, else None."""
    for pattern, source, text_source, reader in _RULES:
        if pattern.search(url):
            return source, text_source, reader
    return None
