"""Throwaway: check in real Chrome whether conservationjobboard.com loads listings by JS.

Adapted from research/builtin_nyc/inspect_page.py.

Usage: python inspect_page.py <search-url> [--click-page-2] [<detail-url>]
Loads the search page and scrolls to the bottom; optionally clicks the pagination link to
page 2 and loads one detail page, 4 s apart. Logs every XHR/fetch/document request (with
status and content type) and saves the bodies of the site's own XHR/fetch responses, the
rendered DOM and the rendered main-results cards to out/ (gitignored). Images, fonts and
media are blocked to keep the load light.
"""

import json
import sys
import time
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page, Response, sync_playwright

OUT = Path(__file__).resolve().parent / "out"
SITE = "conservationjobboard.com"
MAIN = 'a.gtag-job-link[list_name="main-results-page"]'
LOGGED_TYPES = ("xhr", "fetch", "document", "websocket", "eventsource")


def card_summary(page: Page) -> list[dict]:
    """id, title and visible text rows of every main-results card in the rendered DOM."""
    return page.eval_on_selector_all(
        MAIN,
        """links => links.map(a => {
            const art = a.closest('article');
            return {id: a.getAttribute('job_id'), title: a.innerText.trim(),
                    fields: Array.from(art.querySelectorAll('h3,h4,p,div'))
                        .map(e => e.innerText.trim()).filter(Boolean)};
        })""",
    )


def scroll_to_bottom(page: Page, steps: int = 6) -> None:
    for _ in range(steps):
        page.mouse.wheel(0, 4000)
        time.sleep(0.7)


def run(
    search_url: str,
    click_page_2: bool,
    detail_url: str | None,
    on_response: Callable[[Response], None],
) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_context().new_page()
        page.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.resource_type in ("image", "font", "media")
                else route.continue_()
            ),
        )
        page.on("response", on_response)

        print("== load search page")
        # Not "networkidle": the Turnstile widget can keep the network busy.
        page.goto(search_url, wait_until="load")
        time.sleep(3)
        print("main cards after load:", len(card_summary(page)))
        scroll_to_bottom(page)
        time.sleep(3)  # Let late XHRs finish.
        cards = card_summary(page)
        print("main cards after scroll:", len(cards))
        (OUT / "rendered_search.html").write_text(page.content(), encoding="utf-8")
        (OUT / "rendered_cards.json").write_text(json.dumps(cards, indent=1), encoding="utf-8")

        if click_page_2:
            print("== click page 2")
            time.sleep(4)
            url_before = page.url
            page.locator("ul.pagination a.page-link", has_text="2").first.click()
            page.wait_for_load_state("load")
            time.sleep(3)
            cards = card_summary(page)
            print("url:", url_before, "->", page.url, "| page-2 main cards:", len(cards))
            (OUT / "rendered_search_p2.html").write_text(page.content(), encoding="utf-8")

        if detail_url:
            print("== load detail page")
            time.sleep(4)
            # Turnstile keeps the network busy, so networkidle never fires on detail pages.
            page.goto(detail_url, wait_until="load")
            scroll_to_bottom(page, steps=3)
            time.sleep(3)
            (OUT / "rendered_detail.html").write_text(page.content(), encoding="utf-8")
            print("detail title:", page.title())

        browser.close()


def main(search_url: str, click_page_2: bool, detail_url: str | None) -> None:
    OUT.mkdir(exist_ok=True)
    log: list[str] = []
    bodies: list[dict] = []

    def on_response(r: Response) -> None:
        req = r.request
        if req.resource_type not in LOGGED_TYPES:
            return
        ctype = r.headers.get("content-type", "")
        line = f"{r.status} {req.method} {req.resource_type:8} {ctype[:24]:24} {r.url}"
        log.append(line)
        print(line)
        if SITE in r.url and req.resource_type in ("xhr", "fetch"):
            try:
                text = r.text()
            except Exception:  # noqa: BLE001
                text = ""
            bodies.append(
                {
                    "url": r.url,
                    "method": req.method,
                    "post": (req.post_data or "")[:4000],
                    "content_type": ctype,
                    "body": text[:40000],
                }
            )

    try:
        run(search_url, click_page_2, detail_url, on_response)
    finally:
        (OUT / "browser_requests.log").write_text("\n".join(log), encoding="utf-8")
        (OUT / "xhr_bodies.json").write_text(json.dumps(bodies, indent=1), encoding="utf-8")
        print(f"{len(log)} xhr/fetch/document responses, {len(bodies)} site XHR bodies saved")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--click-page-2"]
    main(args[0], "--click-page-2" in sys.argv, args[1] if len(args) > 1 else None)
