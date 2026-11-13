"""Data types returned by the search API."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """A single organic result from a Google results page."""

    title: str
    url: str
    """Destination URL. If redirects were not resolved, Google's /goto link."""
    display_url: str = ""
    """Breadcrumb shown under the title, e.g. ``https://x.org › docs``. Empty
    when Google shows metadata (such as "8 comments · 3 years ago") instead."""
    snippet: str = ""
    site_name: str = ""
    """Site label shown above the title, e.g. ``Stack Overflow``."""
    google_url: str = ""
    """Google's redirect link for this result, if it had one."""
    position: int = 0
    """1-based position among the results parsed from this page. It restarts
    at 1 on every page; see ``SearchMetadata.page``."""


@dataclass
class SearchMetadata:
    """Information about the search as a whole."""

    query: str
    search_time: float | None = None
    """Seconds Google reports for the search, e.g. ``0.19``."""
    results_count: str | None = None
    """Google's result-count text, e.g. ``About 10,500 results``."""
    page: int = 1
    """1-based results page this response came from."""


@dataclass
class SearchResponse:
    """The parsed results page."""

    results: list[SearchResult] = field(default_factory=list)
    metadata: SearchMetadata = field(default_factory=lambda: SearchMetadata(query=""))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict."""
        return asdict(self)
