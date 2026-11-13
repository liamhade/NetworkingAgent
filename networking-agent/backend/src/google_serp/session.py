"""Run Google searches in a real Chrome browser with a persistent profile.

Google's cookies, including CAPTCHA clearance, live in the profile, so a
CAPTCHA only has to be solved once. Later runs reuse the same session.

A browser is required: plain HTTP clients (requests, curl) get Google's
"enable JavaScript" page instead of results, even with fresh cookies.
Headless Chrome is flagged more often, so the browser always runs headed. Its
window sits off-screen and only comes forward for a CAPTCHA.
"""

import logging
import os
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlencode, urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from .models import SearchResponse, SearchResult
from .parser import parse_meta_refresh, parse_results

log = logging.getLogger(__name__)

CAPTCHA_TIMEOUT_S = 180
"""How long a person has to solve a CAPTCHA in the Chrome window."""
_OFFSCREEN = (-32000, -32000)
_REDIRECT_STATUSES = (301, 302, 303, 307, 308)


class CaptchaTimeoutError(Exception):
    """Google showed a CAPTCHA and nobody solved it in time."""


def default_profile_dir() -> Path:
    """The Chrome profile directory: ``GOOGLE_SERP_PROFILE_DIR``, else
    ``%LOCALAPPDATA%\\google-serp\\chrome-profile`` (``~/.local/share/...`` elsewhere)."""
    override = os.environ.get("GOOGLE_SERP_PROFILE_DIR")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share"
    return Path(base) / "google-serp" / "chrome-profile"


class GoogleSerpSession:
    """One Chrome window that runs many searches.

    Call ``start()`` before use (``search`` also starts it) and ``close()`` when done.
    Only one process can use the Chrome profile at a time.
    """

    def __init__(self) -> None:
        self.profile_dir = default_profile_dir()
        self._pw = None
        self._context = None
        self._page = None

    def start(self) -> "GoogleSerpSession":
        """Launch Chrome (off-screen). Does nothing if it is already running."""
        if self._context is not None:
            return self
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        try:
            self._context = self._pw.chromium.launch_persistent_context(
                str(self.profile_dir),
                channel="chrome",
                headless=False,
                locale="en-US",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    f"--window-position={_OFFSCREEN[0]},{_OFFSCREEN[1]}",
                ],
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

    def search(self, query: str) -> SearchResponse:
        """Search Google and return the first results page.

        Result ``url``s are Google's /goto redirect links; pass the results you
        will use to :meth:`resolve_results` to get their real URLs.

        Raises:
            CaptchaTimeoutError: A CAPTCHA appeared and was not solved in time.
        """
        tab = self.start()._page
        url = "https://www.google.com/search?" + urlencode({"q": query, "hl": "en"})
        # The results are server-rendered, so they are in the DOM well before
        # 'load' (images, scripts). Don't wait for 'networkidle' at all: results
        # pages keep connections open.
        tab.goto(url, wait_until="domcontentloaded", timeout=30_000)
        if "/sorry/" in tab.url:
            self._wait_for_captcha()
        if "consent.google." in tab.url:
            self._accept_consent()
        try:
            tab.wait_for_selector("#search, #rso", timeout=10_000)
        except PlaywrightTimeout:
            pass  # e.g. a query with no results; parse whatever loaded
        return SearchResponse(results=parse_results(tab.content()), query=query)

    def resolve_results(self, results: Iterable[SearchResult]) -> None:
        """Replace each result's /goto ``url`` with its real destination, in place.

        Results with no redirect link, or already resolved, are skipped. A link
        that can't be resolved keeps its /goto URL. Google throttles after a few
        links (about 5-25 s per search), so resolve only the results you use.
        """
        for result in results:
            if not result.google_url or result.url != result.google_url:
                continue
            try:
                result.url = self._resolve_url(result.google_url) or result.google_url
            except Exception as e:
                log.warning("Could not resolve %s: %s", result.google_url, e)

    def _resolve_url(self, google_url: str, depth: int = 0) -> str | None:
        """Follow one /goto link and return its destination.

        Google answers with a 302 for the first few links, then throttles by
        returning a page with a meta refresh of a few seconds. That delay is
        honoured rather than skipped.
        """
        response = self.start()._page.request.get(google_url, max_redirects=0)
        if response.status in _REDIRECT_STATUSES:
            return response.headers.get("location")
        refresh = parse_meta_refresh(response.text())
        if refresh and depth < 3:
            delay, next_url = refresh
            self._page.wait_for_timeout(delay * 1000)
            return self._resolve_url(urljoin(google_url, next_url), depth + 1)
        return None

    def _wait_for_captcha(self) -> None:
        """Bring the window on-screen until a person solves the CAPTCHA."""
        log.warning(
            "CAPTCHA shown; solve it in the Chrome window (waiting up to %ds)", CAPTCHA_TIMEOUT_S
        )
        self._move_window(100, 100, bring_to_front=True)
        try:
            self._page.wait_for_url(
                lambda u: "/search?" in u and "/sorry/" not in u,
                timeout=CAPTCHA_TIMEOUT_S * 1000,
            )
            self._page.wait_for_load_state("load", timeout=30_000)
        except PlaywrightTimeout as e:
            raise CaptchaTimeoutError("CAPTCHA was not solved in time") from e
        finally:
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
            # A maximized/minimized window ignores bounds, so restore it first.
            cdp.send(
                "Browser.setWindowBounds",
                {"windowId": window_id, "bounds": {"windowState": "normal"}},
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
