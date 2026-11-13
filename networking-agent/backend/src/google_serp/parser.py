"""Parse Google results-page HTML into structured data.

These functions are pure (HTML in, objects out), so they can be used on saved
pages and tested without a browser.
"""

import html as html_lib
import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from .models import SearchMetadata, SearchResponse, SearchResult

GOOGLE_ORIGIN = "https://www.google.com/"


def parse_results_page(html: str, query: str) -> SearchResponse:
    """Parse a full results page into a SearchResponse."""
    soup = BeautifulSoup(html, "html.parser")
    return SearchResponse(
        results=_extract_results(soup),
        metadata=_extract_metadata(soup, query),
    )


def parse_results(html: str) -> list[SearchResult]:
    """Parse only the organic results from a results page."""
    return _extract_results(BeautifulSoup(html, "html.parser"))


def parse_metadata(html: str, query: str) -> SearchMetadata:
    """Parse only the result count and search time from a results page."""
    return _extract_metadata(BeautifulSoup(html, "html.parser"), query)


def is_google_redirect(url: str) -> bool:
    """True for Google's result redirect links (/goto and /url)."""
    parsed = urlparse(url)
    return parsed.netloc == "www.google.com" and parsed.path in ("/goto", "/url")


def parse_meta_refresh(html: str) -> tuple[int, str] | None:
    """Return (delay_seconds, url) from a ``<meta http-equiv="refresh">`` page."""
    match = re.search(r'content="(\d+);\s*url=([^"]+)"', html)
    if not match:
        return None
    return int(match.group(1)), html_lib.unescape(match.group(2))


def _clean_url(href: str) -> str:
    """Unwrap old-style /url?q=... links; make relative links absolute."""
    if href.startswith("/url?"):
        target = parse_qs(urlparse(href).query).get("q", [""])[0]
        if target:
            return target
    return urljoin(GOOGLE_ORIGIN, href)


def _extract_results(soup: BeautifulSoup) -> list[SearchResult]:
    # Anchor on <a href><h3>title</h3></a>. It has stayed stable across Google
    # layout changes, while the class names around it are obfuscated and change.
    root = soup.select_one("#rso") or soup.select_one("#search") or soup
    results: list[SearchResult] = []
    seen: set[str] = set()

    for h3 in root.find_all("h3"):
        link = h3.find_parent("a", href=True)
        if link is None:  # e.g. the "AI Mode" heading
            continue
        url = _clean_url(link["href"])
        if url in seen:
            continue
        host = urlparse(url).netloc
        # Skip Google's own links (maps, "more results", ...), keep redirects.
        if not is_google_redirect(url) and (
            not url.startswith("http") or host.endswith("google.com")
        ):
            continue

        container = (
            h3.find_parent("div", class_="MjjYud")
            or h3.find_parent("div", class_="tF2Cxc")
            or h3.find_parent("div", class_="g")
            or h3.find_parent("div", attrs={"data-hveid": True})
            or link.parent
        )

        # <cite> holds the breadcrumb for most sites, but metadata such as
        # "8 comments · 3 years ago" for forums and videos.
        display_url = ""
        for cite in container.find_all("cite"):
            text = cite.get_text(" ", strip=True)
            if text.startswith("http"):
                display_url = text
                break

        site_tag = container.select_one("span.VuuXrf")
        site_name = site_tag.get_text(" ", strip=True).replace("\xa0", " ") if site_tag else ""

        snippet_tag = container.select_one(
            'div.VwiC3b, div[data-sncf], div[style*="-webkit-line-clamp"]'
        )
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        seen.add(url)
        results.append(
            SearchResult(
                title=h3.get_text(" ", strip=True),
                url=url,
                display_url=display_url,
                snippet=snippet,
                site_name=site_name,
                google_url=url if is_google_redirect(url) else "",
                position=len(results) + 1,
            )
        )

    return results


def _extract_metadata(soup: BeautifulSoup, query: str) -> SearchMetadata:
    stats = soup.select_one("#result-stats")
    text = stats.get_text(" ", strip=True) if stats else ""

    count_match = re.search(r"((?:About )?[\d,.]+ results?)", text, re.IGNORECASE)
    # "(0.19s)" in the current layout, "(0.19 seconds)" in older ones.
    time_match = re.search(r"\(([\d.]+)\s*s(?:econds?)?\)", text, re.IGNORECASE)

    return SearchMetadata(
        query=query,
        search_time=float(time_match.group(1)) if time_match else None,
        results_count=count_match.group(1) if count_match else None,
    )
