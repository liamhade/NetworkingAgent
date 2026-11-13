"""HTML -> Markdown converters (pure functions, no network)."""

import re

import html2text
import trafilatura
from bs4 import BeautifulSoup, Tag

MIN_CHARS = 200
"""Below this, an extraction is treated as empty (e.g. a JS-only shell)."""

_JS_SHELL = re.compile(r"enable javascript|javascript (is )?(required|disabled)", re.IGNORECASE)

_CHROME_TAGS = [
    "script",
    "style",
    "noscript",
    "template",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "button",
    "svg",
    "iframe",
]
_CHROME_ROLES = {"navigation", "banner", "contentinfo", "search", "dialog", "alertdialog"}
_COOKIE = re.compile(r"cookie|consent|gdpr|onetrust", re.IGNORECASE)


def soup_of(html: bytes | str) -> BeautifulSoup:
    """Parse HTML; bytes let BeautifulSoup detect the charset from <meta>."""
    return BeautifulSoup(html, "lxml")


def page_title(soup: BeautifulSoup) -> str | None:
    og = soup.find("meta", attrs={"property": "og:title"})
    if isinstance(og, Tag) and og.get("content"):
        return str(og["content"]).strip() or None
    if soup.title and soup.title.string:
        return soup.title.string.strip() or None
    h1 = soup.find("h1")
    return h1.get_text(" ", strip=True) or None if h1 else None


def trafilatura_markdown(html: bytes | str, url: str) -> str:
    """Main-content extraction with absolute links (needs `url`)."""
    md = trafilatura.extract(
        html,
        url=url,
        output_format="markdown",
        include_links=True,
        include_tables=True,
        include_formatting=True,
        include_comments=False,
    )
    return (md or "").strip()


def trafilatura_title(html: bytes | str, url: str) -> str | None:
    meta = trafilatura.extract_metadata(html, default_url=url)
    return meta.title if meta is not None and meta.title else None


def html_to_markdown(html: str, url: str | None = None) -> str:
    """Convert an HTML fragment (e.g. an API's job description) to Markdown."""
    h = html2text.HTML2Text(baseurl=url or "")
    h.body_width = 0
    h.ignore_images = True
    h.protect_links = False
    h.unicode_snob = True
    return re.sub(r"\n{3,}", "\n\n", h.handle(html)).strip()


def _strip_chrome(soup: BeautifulSoup) -> Tag:
    for tag in soup.find_all(_CHROME_TAGS):
        tag.decompose()
    for tag in soup.find_all(attrs={"role": True}):
        if not tag.decomposed and str(tag.get("role", "")).lower() in _CHROME_ROLES:
            tag.decompose()
    for tag in soup.find_all(True):
        if tag.decomposed or tag.name in ("html", "body", "main"):
            continue
        ident = " ".join([str(tag.get("id", "")), *map(str, tag.get("class") or [])])
        if ident.strip() and _COOKIE.search(ident):
            tag.decompose()
    main = soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup
    return main  # type: ignore[return-value]


def cleaned_full_markdown(html: bytes | str, url: str) -> str:
    """Whole page minus navigation/footer/cookie chrome. Keeps short card text (names)."""
    main = _strip_chrome(soup_of(html))
    return _dedupe_paragraphs(html_to_markdown(str(main), url))


def _dedupe_paragraphs(markdown: str, min_len: int = 80) -> str:
    """Drop repeated long paragraphs (card pages often hold a hidden "modal" copy of each bio)."""
    seen: set[str] = set()
    out = []
    for para in markdown.split("\n\n"):
        key = para.strip()
        if len(key) >= min_len:
            if key in seen:
                continue
            seen.add(key)
        out.append(para)
    return "\n\n".join(out)


def headings(html: bytes | str) -> list[str]:
    """Text of the h2-h4 headings in the page's content area."""
    main = _strip_chrome(soup_of(html))
    return [t for h in main.find_all(["h2", "h3", "h4"]) if (t := h.get_text(" ", strip=True))]


def looks_empty(markdown: str) -> bool:
    """True for empty extractions and 'please enable JavaScript' shells."""
    text = markdown.strip()
    return len(text) < MIN_CHARS or (len(text) < 1000 and bool(_JS_SHELL.search(text)))


_LINE_DECOR = re.compile(r"^[#>*\s-]+|[*_\s]+$")


def prefers_full(trafilatura_md: str, full_md: str, html: bytes | str) -> bool:
    """Card-page heuristic: trafilatura dropped many headings that cleaned-full kept.

    A heading counts as kept only if it is a line of its own in trafilatura's output: on the
    Datadog leadership page the names survive inside bios but not as card headings, and both
    outputs are about the same length, so length is not a usable signal.
    """
    if not full_md.strip():
        return False
    page_headings = headings(html)
    lines = {_LINE_DECOR.sub("", line).strip() for line in trafilatura_md.splitlines()}
    missing = [h for h in page_headings if h not in lines]
    return len(missing) >= 4 and len(missing) >= 0.5 * len(page_headings)
