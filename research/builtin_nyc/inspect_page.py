"""Minimal Playwright scaffold for inspecting a page.

Usage: python inspect_page.py <url> [--headed]
Logs network requests/responses and saves a screenshot + HTML to out/ (next to this script).

Helpful for investigating websites.
"""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "out"


def inspect(url: str, headed: bool = False) -> None:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        page = browser.new_context().new_page()

        page.on("request", lambda r: print(f"> {r.method} {r.resource_type:10} {r.url}"))
        page.on("response", lambda r: print(f"< {r.status} {r.url}"))

        page.goto(url, wait_until="networkidle")
        print("title:", page.title())

        page.screenshot(path=OUT / "page.png", full_page=True)
        (OUT / "page.html").write_text(page.content(), encoding="utf-8")

        # Scratch space: poke at the page here, e.g. page.locator("css=...").all_inner_texts()
        if headed:
            page.pause()

        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    inspect(args.url, args.headed)
