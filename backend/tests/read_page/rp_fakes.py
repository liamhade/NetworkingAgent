"""Offline fakes for the read_page tests: scripted fetch, JSON API and browser."""

from pathlib import Path
from typing import Any

import requests

from read_page import fetch as fetch_mod

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} Error", response=response)


class FakeWeb:
    """Maps URLs to HTML pages / JSON payloads / rendered pages and records every call."""

    def __init__(self) -> None:
        self.pages: dict[str, tuple[str, bytes]] = {}
        self.json: dict[str, Any] = {}
        self.rendered: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []

    def page(self, url: str, content: bytes | str, final_url: str | None = None) -> None:
        data = content.encode() if isinstance(content, str) else content
        self.pages[url] = (final_url or url, data)

    def fetch(self, url: str) -> fetch_mod.Fetched:
        self.calls.append(("fetch", url))
        if url not in self.pages:
            raise http_error(404)
        final_url, content = self.pages[url]
        return fetch_mod.Fetched(url=url, final_url=final_url, status=200, content=content)

    def get_json(self, url: str, params: dict[str, str] | None = None) -> Any:
        self.calls.append(("json", url))
        value = self.json.get(url)
        if value is None:
            raise http_error(404)
        if isinstance(value, Exception):
            raise value
        return value

    def render(self, url: str) -> tuple[str, str]:
        self.calls.append(("browser", url))
        if url not in self.rendered:
            raise RuntimeError("browser: page not scripted")
        return url, self.rendered[url]
