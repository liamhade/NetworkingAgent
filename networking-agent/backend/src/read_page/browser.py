"""Headless-Chromium rendering for JS-only pages.

Like `tools._GoogleWorker`: Playwright's sync API is bound to the thread that started it, so
every render runs on one dedicated thread that owns one reusable browser.
"""

import atexit
import importlib.util
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .fetch import USER_AGENT

log = logging.getLogger(__name__)

NAV_TIMEOUT_MS = 20_000
IDLE_TIMEOUT_MS = 8_000


def enabled() -> bool:
    """True unless `READ_PAGE_BROWSER=false` or Playwright isn't installed.

    Without it, pages that need JavaScript are read from their static HTML only.
    """
    if os.environ.get("READ_PAGE_BROWSER", "true").strip().lower() == "false":
        return False
    return importlib.util.find_spec("playwright") is not None


class BrowserWorker:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="read-page-browser")
        self._lock = threading.Lock()
        self._pw: Any = None
        self._browser: Any = None
        self._closed = False

    def _ensure_browser(self) -> Any:
        if self._browser is None or not self._browser.is_connected():
            from playwright.sync_api import sync_playwright

            self._reset()
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
        return self._browser

    def _reset(self) -> None:
        for obj, close in ((self._browser, "close"), (self._pw, "stop")):
            if obj is not None:
                try:
                    getattr(obj, close)()
                except Exception:  # noqa: BLE001
                    log.debug("Ignoring error while closing browser", exc_info=True)
        self._browser = self._pw = None

    def _render(self, url: str) -> tuple[str, str]:
        context = self._ensure_browser().new_context(user_agent=USER_AGENT, locale="en-US")
        try:
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            try:
                page.wait_for_load_state("networkidle", timeout=IDLE_TIMEOUT_MS)
            except Exception:  # noqa: BLE001
                log.debug("networkidle not reached for %s; using current DOM", url)
            return page.url, page.content()
        finally:
            context.close()

    def render(self, url: str) -> tuple[str, str]:
        """Return `(final_url, rendered_html)`."""
        with self._lock:
            return self._executor.submit(self._render, url).result()

    def close(self) -> None:
        """Close the browser; safe to call twice (e.g. shutdown() and then atexit)."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        if self._browser is not None or self._pw is not None:
            try:
                self._executor.submit(self._reset).result()
            except RuntimeError:
                # At interpreter exit, concurrent.futures shuts executors down before
                # atexit callbacks run; the browser exits with the process anyway.
                log.debug("Browser thread already stopped; skipping browser close")
        self._executor.shutdown(wait=False)


_worker: BrowserWorker | None = None
_worker_lock = threading.Lock()


def render(url: str) -> tuple[str, str]:
    """Render `url` in the shared headless browser (patched in tests)."""
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = BrowserWorker()
            atexit.register(_worker.close)
        worker = _worker
    return worker.render(url)


def shutdown() -> None:
    global _worker
    with _worker_lock:
        if _worker is not None:
            _worker.close()
            _worker = None
