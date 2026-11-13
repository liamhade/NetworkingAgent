"""Read a web page as Markdown (with absolute hyperlinks) for the agent.

Default: `requests` + trafilatura. Fallbacks: JSON-LD JobPosting, headless Chromium for JS-only
pages, and "cleaned-full" (BeautifulSoup + html2text) for card-heavy pages. Specialized
methods (Greenhouse/Lever/Ashby APIs, JSON-LD) are chosen per URL by a regex registry that
can be extended with `register()`. See `docs/read-page/plan.md`.
"""

from .browser import shutdown
from .core import DEFAULT_MAX_CHARS, clear_cache, read_page
from .methods import READERS
from .models import MethodUnavailable, PageBlocked, PageResult, ReadPageError
from .registry import register

METHODS = ("auto", *READERS)
"""Every value accepted by `read_page(method=...)`."""

__all__ = [
    "DEFAULT_MAX_CHARS",
    "METHODS",
    "MethodUnavailable",
    "PageBlocked",
    "PageResult",
    "ReadPageError",
    "clear_cache",
    "read_page",
    "register",
    "shutdown",
]
