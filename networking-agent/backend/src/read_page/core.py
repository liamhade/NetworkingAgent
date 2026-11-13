"""`read_page()`: pick a method, apply fallbacks, cache and truncate."""

import logging
import threading
import time
from collections import OrderedDict

from . import browser, methods, registry
from . import fetch as fetch_mod
from .convert import cleaned_full_markdown, looks_empty, prefers_full
from .models import MethodUnavailable, PageBlocked, PageResult, ReadPageError

log = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 32_000
CACHE_TTL = 600.0
CACHE_SIZE = 64

LINKEDIN_PROFILE_MESSAGE = (
    "LinkedIn profiles can't be read (LinkedIn blocks it and its terms forbid scraping); "
    "use linkedin_people to get people's names and headlines instead."
)

_cache: OrderedDict[tuple[str, str], tuple[float, PageResult]] = OrderedDict()
_cache_lock = threading.Lock()


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _cached(key: tuple[str, str]) -> PageResult | None:
    with _cache_lock:
        hit = _cache.get(key)
        if hit is None:
            return None
        if time.monotonic() - hit[0] > CACHE_TTL:
            del _cache[key]
            return None
        _cache.move_to_end(key)
        return hit[1]


def _store(key: tuple[str, str], result: PageResult) -> None:
    with _cache_lock:
        _cache[key] = (time.monotonic(), result)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)


def truncate(result: PageResult, max_chars: int) -> PageResult:
    """Clip markdown to `max_chars`, preferring a paragraph or line break."""
    md = result.markdown
    if len(md) <= max_chars:
        return result
    cut = md[:max_chars]
    for sep in ("\n\n", "\n"):
        pos = cut.rfind(sep)
        if pos >= max_chars * 0.8:
            cut = cut[:pos]
            break
    return result.model_copy(update={"markdown": cut.rstrip(), "truncated": True})


def _generic(url: str) -> PageResult:
    """Static fetch + trafilatura, with JSON-LD / browser / cleaned-full fallbacks."""
    f = fetch_mod.fetch(url)
    result = methods.static_from_html(url, f.final_url, f.content)
    if looks_empty(result.markdown):
        try:
            return methods.jsonld_from_html(url, f.final_url, f.content)
        except MethodUnavailable:
            pass
        log.info("Static extraction of %s looks empty; rendering in a browser", url)
        final_url, rendered = browser.render(url)
        result = methods.static_from_html(url, final_url, rendered)
        result = result.model_copy(update={"method": "browser"})
        if looks_empty(result.markdown):
            # Short pages are legitimate; prefer whichever conversion kept more text.
            full_md = cleaned_full_markdown(rendered, final_url)
            if len(full_md) > len(result.markdown):
                result = result.model_copy(update={"markdown": full_md, "method": "browser+full"})
        if not result.markdown.strip():
            raise ReadPageError(f"No readable content at {url}")
        return result
    full_md = cleaned_full_markdown(f.content, f.final_url)
    if prefers_full(result.markdown, full_md, f.content):
        log.info("trafilatura dropped card headings on %s; using cleaned-full", url)
        return result.model_copy(update={"markdown": full_md, "method": "full"})
    return result


def _auto(url: str) -> PageResult:
    method = registry.match(url)
    if method == registry.BLOCKED:
        raise PageBlocked(_blocked_message(url))
    if method is not None:
        try:
            result = methods.reader(method)(url)
            if result.markdown.strip():
                return result
            log.info("%s returned nothing for %s; using the generic path", method, url)
        except ReadPageError as exc:
            if not isinstance(exc, MethodUnavailable):
                raise
            log.info("%s unavailable for %s (%s); using the generic path", method, url, exc)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s failed for %s (%s); using the generic path", method, url, exc)
    return _generic(url)


def _blocked_message(url: str) -> str:
    if "linkedin.com" in url.lower():
        return LINKEDIN_PROFILE_MESSAGE
    return f"Reading {url} is blocked by a registry rule."


def read_page(
    url: str, method: str | None = None, max_chars: int = DEFAULT_MAX_CHARS
) -> PageResult:
    """Read `url` as Markdown with absolute hyperlinks.

    `method=None`/"auto" uses the registry and fallbacks; any other method runs only that
    reader. Raises `PageBlocked` for refused URLs and `ReadPageError` for unreadable pages.
    """
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        raise ReadPageError(f"Not an http(s) URL: {url!r}")
    method = (method or "auto").strip().lower()
    if registry.match(url) == registry.BLOCKED:
        raise PageBlocked(_blocked_message(url))
    if method != "auto":
        methods.reader(method)  # validate the name before fetching
    key = (url, method)
    result = _cached(key)
    if result is None:
        result = _auto(url) if method == "auto" else methods.reader(method)(url)
        _store(key, result)
    return truncate(result, max(1, max_chars))
