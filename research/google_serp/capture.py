"""Open google.com, run a search, and record all network traffic.

Outputs (in ./captures/):
  traffic.har      - full HAR with response bodies
  requests.json    - one summary row per request
  screenshot.png   - the results page as rendered
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

QUERY = sys.argv[1] if len(sys.argv) > 1 else "playwright python tutorial"
OUT = Path(__file__).resolve().parent / "captures"
OUT.mkdir(exist_ok=True)

rows = []


def on_response(response):
    request = response.request
    row = {
        "method": request.method,
        "url": request.url,
        "resource_type": request.resource_type,
        "status": response.status,
        "content_type": response.headers.get("content-type", ""),
        "size": None,
        "contains_query": False,
    }
    try:
        body = response.body()
        row["size"] = len(body)
        text = body.decode("utf-8", errors="ignore").lower()
        # Check for a distinctive word from the query in the body.
        row["contains_query"] = all(w in text for w in QUERY.lower().split())
    except Exception:
        pass  # redirects and some aborted requests have no body
    rows.append(row)


with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, channel="chrome")
    context = browser.new_context(
        record_har_path=str(OUT / "traffic.har"),
        record_har_content="embed",
        locale="en-US",
    )
    page = context.new_page()
    page.on("response", on_response)

    page.goto("https://www.google.com/", wait_until="domcontentloaded")

    # Dismiss the cookie consent dialog if it appears (EU/UK regions).
    for label in ("Accept all", "I agree", "Reject all"):
        button = page.get_by_role("button", name=label)
        if button.count():
            button.first.click()
            break

    search_box = page.locator("textarea[name='q'], input[name='q']").first
    search_box.click()
    search_box.fill(QUERY)
    search_box.press("Enter")

    page.wait_for_load_state("load", timeout=30000)
    if "/sorry/" in page.url:
        # Google served a CAPTCHA. Leave the window open so a person can solve it.
        print("CAPTCHA shown; solve it in the browser window (waiting up to 3 min)...")
        page.wait_for_url("**/search?**", timeout=180000)
        page.wait_for_load_state("load", timeout=30000)
    page.wait_for_timeout(5000)  # let post-load XHRs (more results, etc.) fire
    print("Final URL:", page.url)
    page.screenshot(path=str(OUT / "screenshot.png"), full_page=True)

    context.close()  # flushes the HAR
    browser.close()

(OUT / "requests.json").write_text(json.dumps(rows, indent=2))
print(f"Captured {len(rows)} responses")
for r in rows:
    if r["contains_query"]:
        print(f"[query match] {r['status']} {r['method']} {r['resource_type']:10} "
              f"{r['size']!s:>8}B {r['content_type'][:30]:30} {r['url'][:160]}")
