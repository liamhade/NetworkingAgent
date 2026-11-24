"""Data types returned by a search."""

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """A single organic result from a Google results page."""

    title: str
    url: str
    """Destination URL; Google's /goto link until the result is resolved."""
    display_url: str = ""
    """Breadcrumb shown under the title, e.g. ``https://x.org › docs``. Empty
    when Google shows metadata (such as "8 comments · 3 years ago") instead."""
    snippet: str = ""
    site_name: str = ""
    """Site label shown above the title, e.g. ``Stack Overflow``."""
    google_url: str = ""
    """Google's redirect link for this result, if it had one."""
    position: int = 0
    """1-based rank on the page (0 = unknown)."""
    date: str = ""
    """Date Google shows for the result, e.g. ``"Mar 3, 2025"`` or ``"2 days ago"``."""


@dataclass
class SearchResponse:
    """The organic results of one search."""

    results: list[SearchResult] = field(default_factory=list)
    query: str = ""
