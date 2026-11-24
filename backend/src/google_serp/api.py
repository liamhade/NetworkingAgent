"""Google results from a licensed SERP API instead of a browser.

The provider runs the Google search on its side, so there are no CAPTCHAs here and
result links are already direct URLs (nothing to resolve). One page takes ~1-2 s.

    client = client_from_env()          # SERPER_API_KEY or SERPAPI_API_KEY, else None
    response = client.search("playwright python")
"""

import logging
import os
import time
from typing import Any, Protocol
from urllib.parse import urlparse

import requests

from .models import SearchResponse, SearchResult

log = logging.getLogger(__name__)

TIMEOUT_S = 10.0


class SerpApiError(RuntimeError):
    """The SERP provider refused the request or answered with something unusable."""


class SerpClient(Protocol):
    name: str

    def search(self, query: str, num: int = 10) -> SearchResponse: ...


def _display_url(url: str) -> str:
    """Google-style breadcrumb: ``https://host › a › b``."""
    parsed = urlparse(url)
    crumbs = [p for p in parsed.path.split("/") if p]
    return " › ".join([f"{parsed.scheme}://{parsed.netloc}", *crumbs])


def _site_name(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host


class _HttpClient:
    name = ""

    def __init__(self, api_key: str, session: requests.Session | None = None) -> None:
        if not api_key:
            raise ValueError(f"{type(self).__name__} needs an API key")
        self.api_key = api_key
        self.http = session or requests.Session()

    def _check(self, response: requests.Response) -> dict[str, Any]:
        if response.status_code != 200:
            raise SerpApiError(
                f"{self.name} returned HTTP {response.status_code}: {response.text[:300]}"
            )
        try:
            return response.json()
        except ValueError as e:
            raise SerpApiError(f"{self.name} returned non-JSON: {response.text[:300]}") from e

    def search(self, query: str, num: int = 10) -> SearchResponse:
        started = time.monotonic()
        response = SearchResponse(results=self._search(query, num), query=query)
        log.info(
            "%s: %d results for %r in %.2fs",
            self.name,
            len(response.results),
            query,
            time.monotonic() - started,
        )
        return response

    def _search(self, query: str, num: int) -> list[SearchResult]:
        raise NotImplementedError


class SerperClient(_HttpClient):
    """serper.dev: ``POST https://google.serper.dev/search``."""

    name = "serper"
    URL = "https://google.serper.dev/search"

    def _search(self, query: str, num: int) -> list[SearchResult]:
        data = self._check(
            self.http.post(
                self.URL,
                json={"q": query, "num": num, "gl": "us", "hl": "en"},
                headers={"X-API-KEY": self.api_key},
                timeout=TIMEOUT_S,
            )
        )
        return parse_serper(data)


class SerpApiClient(_HttpClient):
    """serpapi.com: ``GET https://serpapi.com/search.json?engine=google``."""

    name = "serpapi"
    URL = "https://serpapi.com/search.json"

    def _search(self, query: str, num: int) -> list[SearchResult]:
        data = self._check(
            self.http.get(
                self.URL,
                params={
                    "engine": "google",
                    "q": query,
                    "num": num,
                    "gl": "us",
                    "hl": "en",
                    "api_key": self.api_key,
                },
                timeout=TIMEOUT_S,
            )
        )
        if data.get("error") and not data.get("organic_results"):
            # SerpApi reports "no results" as an error string, which isn't a failure.
            if "hasn't returned any results" in data["error"]:
                return []
            raise SerpApiError(f"serpapi: {data['error']}")
        return parse_serpapi(data)


def parse_serper(data: dict[str, Any]) -> list[SearchResult]:
    """Organic results from a serper.dev response."""
    results = []
    for i, item in enumerate(data.get("organic") or [], start=1):
        url = item.get("link") or ""
        if not url:
            continue
        results.append(
            SearchResult(
                title=item.get("title") or "",
                url=url,
                display_url=_display_url(url),
                snippet=item.get("snippet") or "",
                site_name=_site_name(url),
                position=int(item.get("position") or i),
                date=item.get("date") or "",
            )
        )
    return results


def parse_serpapi(data: dict[str, Any]) -> list[SearchResult]:
    """Organic results from a serpapi.com response."""
    results = []
    for i, item in enumerate(data.get("organic_results") or [], start=1):
        url = item.get("link") or ""
        if not url:
            continue
        results.append(
            SearchResult(
                title=item.get("title") or "",
                url=url,
                display_url=item.get("displayed_link") or _display_url(url),
                snippet=item.get("snippet") or "",
                site_name=item.get("source") or _site_name(url),
                position=int(item.get("position") or i),
                date=item.get("date") or "",
            )
        )
    return results


def client_from_env() -> SerpClient | None:
    """A client for whichever key is set (``SERPER_API_KEY`` first), else ``None``."""
    if key := os.environ.get("SERPER_API_KEY", "").strip():
        return SerperClient(key)
    if key := os.environ.get("SERPAPI_API_KEY", "").strip():
        return SerpApiClient(key)
    return None
