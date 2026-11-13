"""The provider interface every ATS (Greenhouse, Lever, Ashby, Workable, ...) implements."""

import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar
from urllib.parse import urlsplit

import requests

from .models import AtsJob, BoardRef

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
TIMEOUT_S = 20
"""Seconds per board API request; big boards return a few hundred KB."""


def get_json(url: str, params: dict[str, str] | None = None) -> Any:
    """GET a public board API endpoint. Raises for HTTP errors (patched in tests)."""
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S)
    r.raise_for_status()
    return r.json()


class Provider(ABC):
    """One applicant tracking system.

    A provider says which hosts its boards live on (for Google `site:` queries), how to read a
    board slug (and posting id) from a URL, and how to list a board's open postings through
    its public JSON API as `AtsJob`s.
    """

    name: ClassVar[str]
    """Short id used in the plan, trace and job dicts, e.g. "greenhouse"."""
    label: ClassVar[str]
    """Display name for status messages, e.g. "Greenhouse"."""
    site_domains: ClassVar[tuple[str, ...]]
    """Hosts searched with `site:`, e.g. ("job-boards.greenhouse.io", "boards.greenhouse.io")."""
    host_pattern: ClassVar[re.Pattern[str]]
    """Matches every host (lowercase) the provider's board and posting pages live on."""

    def owns(self, url: str) -> bool:
        """True if `url` is on one of the provider's board hosts."""
        return bool(self.host_pattern.fullmatch(urlsplit(url.strip()).netloc.lower()))

    @abstractmethod
    def parse_url(self, url: str) -> BoardRef | None:
        """The board (and posting id) a board/posting URL points at, or None."""

    @abstractmethod
    def board_url(self, slug: str) -> str:
        """The public page listing the board's jobs."""

    @abstractmethod
    def list_jobs(self, slug: str) -> list[AtsJob]:
        """Every open posting on the board. Raises on HTTP errors (404 = unknown board)."""
