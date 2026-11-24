"""Plain HTTP fetching (patched in tests)."""

from dataclasses import dataclass
from typing import Any

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
TIMEOUT = 15
"""Seconds; some job boards are occasionally very slow."""


@dataclass
class Fetched:
    url: str
    final_url: str
    status: int
    content: bytes
    """Raw bytes: let the HTML parser detect the charset (servers often omit it)."""


def fetch(url: str) -> Fetched:
    """GET `url` with a desktop User-Agent. Raises for HTTP errors."""
    r = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return Fetched(url=url, final_url=r.url, status=r.status_code, content=r.content)


def get_json(url: str, params: dict[str, str] | None = None) -> Any:
    """GET a JSON API endpoint. Raises for HTTP errors."""
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()
