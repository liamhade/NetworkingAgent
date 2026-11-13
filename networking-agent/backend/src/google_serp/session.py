"""Run Google searches in a real Chrome browser with a persistent profile.

Google's cookies, including CAPTCHA clearance, live in the profile, so a
CAPTCHA only has to be solved once. Later runs reuse the same session.

A browser is required: plain HTTP clients (requests, curl) get Google's
"enable JavaScript" page instead of results, even with fresh cookies.
Headless Chrome is flagged more often, so the browser always runs headed. By
default its window sits off-screen and only comes forward for a CAPTCHA.
"""

import logging
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlencode, urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from .errors import CaptchaTimeoutError
from .models import SearchMetadata, SearchResponse, SearchResult
from .parser import parse_meta_refresh, parse_results_page

log = logging.getLogger(__name__)

PathLike = str | os.PathLike

CAPTCHA_TIMEOUT_S = 180
_OFFSCREEN = (-32000, -32000)
_REDIRECT_STATUSES = (301, 302, 303, 307, 308)
RESULTS_PER_PAGE = 10


def default_profile_dir() -> Path:
    """Where the Chrome profile is kept unless another is given.

    Override with the ``GOOGLE_SERP_PROFILE_DIR`` environment variable.
    """
    override = os.environ.get("GOOGLE_SERP_PROFILE_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "google-serp" / "chrome-profile"


class GoogleSerpSession:
    """A Chrome session that can run many searches.

    Use it as a context manager so the browser is closed afterwards::

        with GoogleSerpSession() as serp:
            response = serp.search("python requests")

    Args:
        profile_dir: Chrome profile directory. Defaults to
            :func:`default_profile_dir`.
        hidden: Keep the window off-screen. It is moved on-screen
            automatically if a CAPTCHA appears.
        captcha_timeout: Seconds to wait for a person to solve a CAPTCHA.
        language: Interface language passed to Google as ``hl``.
    """

    def __init__(
        self,
        profile_dir: PathLike | None = None,
        hidden: bool = True,
        captcha_timeout: float = CAPTCHA_TIMEOUT_S,
        language: str = "en",
    ):
        self.profile_dir = Path(profile_dir) if profile_dir else default_profile_dir()
        self.hidden = hidden
        self.captcha_timeout = captcha_timeout
        self.language = language
        self._pw = None
        self._context = None
        self._page = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> "GoogleSerpSession":
        """Launch Chrome. Called automatically by ``with`` and by ``search``."""
        if self._context is not None:
            return self
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        args = ["--disable-blink-features=AutomationControlled"]
        if self.hidden:
            args.append(f"--window-position={_OFFSCREEN[0]},{_OFFSCREEN[1]}")
        self._pw = sync_playwright().start()
        try:
            self._context = self._pw.chromium.launch_persistent_context(
                str(self.profile_dir),
                channel="chrome",
                headless=False,
                locale="en-US",
                args=args,
                no_viewport=True,
            )
        except Exception:
            self._pw.stop()
            self._pw = None
            raise
        pages = self._context.pages
        self._page = pages[0] if pages else self._context.new_page()
        return self

    def close(self) -> None:
        """Close Chrome. Safe to call more than once."""
        if self._context is not None:
            try:
                self._context.close()
            finally:
                self._context = None
                self._page = None
        if self._pw is not None:
            self._pw.stop()
            self._pw = None

    def __enter__(self) -> "GoogleSerpSession":
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- public API --------------------------------------------------------

    def search(
        self,
        query: str,
        resolve_urls: bool = True,
        page: int = 1,
        resolve_limit: int | None = None,
    ) -> SearchResponse:
        """Search Google and return the parsed results page.

        Args:
            query: The search query.
            page: 1-based results page (Google shows 10 results per page).
            resolve_urls: Google links results through opaque /goto
                redirects. If True, follow each one to get the real URL. This
                adds one request per result, and Google throttles after a
                few, so expect about 5-25s extra. If False, ``url`` is the
                redirect link.
            resolve_limit: Resolve only the first ``resolve_limit`` results
                (the rest keep their /goto link). Resolving is almost all of a
                search's time, so only resolve the results you will use.

        Raises:
            CaptchaTimeoutError: A CAPTCHA appeared and was not solved in time.
        """
        response = parse_results_page(self.fetch_html(query, page=page), query)
        response.metadata.page = page
        if resolve_urls:
            self.resolve_results(response.results[:resolve_limit])
        return response

    def resolve_results(self, results: Iterable[SearchResult]) -> None:
        """Replace each result's /goto ``url`` with its real destination, in place.

        Results that have no redirect link, or were already resolved, are
        skipped. A link that can't be resolved keeps its /goto URL. Links are
        resolved one at a time, honouring Google's throttle delay.
        """
        for result in results:
            if not result.google_url or result.url != result.google_url:
                continue
            try:
                result.url = self.resolve_url(result.google_url) or result.google_url
            except Exception as e:
                log.warning("Could not resolve %s: %s", result.google_url, e)

    def fetch_html(self, query: str, page: int = 1) -> str:
        """Run a search and return the raw results-page HTML.

        ``page`` is the 1-based results page, sent to Google as ``start``.
        """
        if page < 1:
            raise ValueError(f"page must be >= 1, got {page}")
        tab = self.start()._page
        params = {"q": query, "hl": self.language}
        if page > 1:
            params["start"] = (page - 1) * RESULTS_PER_PAGE
        url = "https://www.google.com/search?" + urlencode(params)
        # The results are server-rendered, so they are in the DOM well before
        # 'load' (images, scripts). Don't wait for 'networkidle' at all: results
        # pages keep connections open. The page keeps loading normally in the
        # background, exactly as it would for a person.
        tab.goto(url, wait_until="domcontentloaded", timeout=30_000)
        if "/sorry/" in tab.url:
            self._wait_for_captcha()
        if "consent.google." in tab.url:
            self._accept_consent()
        try:
            tab.wait_for_selector("#search, #rso", timeout=10_000)
        except PlaywrightTimeout:
            pass  # e.g. a query with no results; parse whatever loaded
        return tab.content()

    def resolve_url(self, google_url: str, _depth: int = 0) -> str | None:
        """Follow a Google /goto redirect link and return its destination.

        Google answers with a 302 for the first few links, then throttles
        by returning a page with a meta refresh of a few seconds. That delay
        is honoured rather than skipped.
        """
        response = self.start()._page.request.get(google_url, max_redirects=0)
        if response.status in _REDIRECT_STATUSES:
            return response.headers.get("location")
        refresh = parse_meta_refresh(response.text())
        if refresh and _depth < 3:
            delay, next_url = refresh
            self._page.wait_for_timeout(delay * 1000)
            return self.resolve_url(urljoin(google_url, next_url), _depth + 1)
        return None

    # -- internals ---------------------------------------------------------

    def _wait_for_captcha(self) -> None:
        log.warning(
            "CAPTCHA shown; solve it in the Chrome window (waiting up to %ds)",
            self.captcha_timeout,
        )
        if self.hidden:
            self._move_window(100, 100, bring_to_front=True)
        try:
            self._page.wait_for_url(
                lambda u: "/search?" in u and "/sorry/" not in u,
                timeout=self.captcha_timeout * 1000,
            )
            self._page.wait_for_load_state("load", timeout=30_000)
        except PlaywrightTimeout as e:
            raise CaptchaTimeoutError("CAPTCHA was not solved in time") from e
        finally:
            if self.hidden:
                self._move_window(*_OFFSCREEN, bring_to_front=False)

    def _accept_consent(self) -> None:
        for label in ("Accept all", "I agree", "Reject all"):
            button = self._page.get_by_role("button", name=label)
            if button.count():
                button.first.click()
                self._page.wait_for_load_state("load", timeout=30_000)
                return

    def _move_window(self, left: int, top: int, bring_to_front: bool) -> None:
        """Move the Chrome window through CDP. Best effort."""
        try:
            cdp = self._context.new_cdp_session(self._page)
            window_id = cdp.send("Browser.getWindowForTarget")["windowId"]
            cdp.send(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {"windowState": "normal"},
                },
            )
            cdp.send(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {"left": left, "top": top, "width": 1200, "height": 900},
                },
            )
            cdp.detach()
            if bring_to_front:
                self._page.bring_to_front()
        except Exception as e:
            log.debug("Could not move browser window: %s", e)


def search(
    query: str,
    *,
    page: int = 1,
    resolve_urls: bool = True,
    hidden: bool = True,
    profile_dir: PathLike | None = None,
    strict: bool = True,
) -> SearchResponse:
    """Run one search: start Chrome, search, close Chrome.

    For several queries, use :class:`GoogleSerpSession` so the browser is
    started only once.

    Args:
        query: The search query.
        page: 1-based results page (10 results per page).
        resolve_urls: Follow Google's redirect links to get real URLs.
        hidden: Keep the browser window off-screen unless a CAPTCHA appears.
        profile_dir: Chrome profile directory (see :func:`default_profile_dir`).
        strict: If False, log errors and return an empty response instead of
            raising.
    """
    try:
        with GoogleSerpSession(profile_dir=profile_dir, hidden=hidden) as session:
            return session.search(query, resolve_urls=resolve_urls, page=page)
    except Exception:
        if strict:
            raise
        log.exception("Search for %r (page %d) failed", query, page)
        return SearchResponse(results=[], metadata=SearchMetadata(query=query, page=page))
