"""Extract a working curl command from a browser search session.

Opens Google, performs a search, and outputs a complete curl command
with all the necessary cookies, headers, and URL parameters.

Usage:
    python get_curl_command.py "your search query"
    
If a CAPTCHA appears, solve it in the browser window.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

QUERY = sys.argv[1] if len(sys.argv) > 1 else "test query"
OUT = Path(__file__).resolve().parent / "captures"
OUT.mkdir(exist_ok=True)


def extract_search_data(har_path: Path):
    """Extract the search request data from the HAR file."""
    with open(har_path, encoding='utf-8') as f:
        har = json.load(f)
    
    # Find the successful search request
    search_entry = None
    for entry in har["log"]["entries"]:
        req = entry["request"]
        resp = entry["response"]
        
        # Look for the final successful search (not the CAPTCHA page)
        if (
            "/search?" in req["url"]
            and "q=" in req["url"]
            and resp["status"] == 200
        ):
            # Make sure it contains our query
            query_decoded = QUERY.replace(" ", "+")
            if query_decoded in req["url"]:
                search_entry = entry
                break
    
    if not search_entry:
        print("ERROR: Could not find successful search request in HAR")
        sys.exit(1)
    
    return search_entry


def generate_curl_command(entry):
    """Generate a curl command from the search request."""
    request = entry["request"]
    url = request["url"]
    
    # Build cookie string
    cookies = "; ".join([f"{c['name']}={c['value']}" for c in request["cookies"]])
    
    # Build headers (exclude HTTP/2 pseudo-headers)
    headers = []
    for h in request["headers"]:
        name = h["name"]
        value = h["value"]
        # Skip HTTP/2 pseudo-headers
        if name.startswith(":"):
            continue
        # Skip some headers that curl handles automatically
        if name in ["host", "connection", "transfer-encoding"]:
            continue
        headers.append(f"-H \"{name}: {value}\"")
    
    # Build the curl command
    headers_str = " \\\n    ".join(headers)
    curl_cmd = f'curl -s \\\n    -b "{cookies}" \\\n    {headers_str} \\\n    "{url}"'
    
    return curl_cmd


def main():
    print(f"Searching for: {QUERY}")
    print("Opening browser... Solve CAPTCHA if it appears.\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        context = browser.new_context(
            record_har_path=str(OUT / "traffic.har"),
            record_har_content="embed",
            locale="en-US",
        )
        page = context.new_page()
        
        page.goto("https://www.google.com/", wait_until="domcontentloaded")
        
        # Dismiss cookie consent
        for label in ("Accept all", "I agree", "Reject all"):
            button = page.get_by_role("button", name=label)
            if button.count():
                button.first.click()
                break
        
        # Perform search
        search_box = page.locator("textarea[name='q'], input[name='q']").first
        search_box.click()
        search_box.fill(QUERY)
        search_box.press("Enter")
        
        page.wait_for_load_state("load", timeout=30000)
        
        # Handle CAPTCHA
        if "/sorry/" in page.url:
            print("CAPTCHA shown; solve it in the browser window (waiting up to 3 min)...")
            page.wait_for_url("**/search?**", timeout=180000)
            page.wait_for_load_state("load", timeout=30000)
        
        page.wait_for_timeout(3000)
        
        context.close()
        browser.close()
    
    # Extract data from HAR
    print("\nExtracting search data from HAR...")
    entry = extract_search_data(OUT / "traffic.har")
    
    # Generate and display curl command
    curl_cmd = generate_curl_command(entry)
    
    print("\n" + "=" * 80)
    print("WORKING CURL COMMAND")
    print("=" * 80)
    print("\nCopy and run this command (tokens are valid for ~15-30 minutes):\n")
    print(curl_cmd)
    print("\n" + "=" * 80)
    
    # Also save to file
    with open(OUT / "curl_command.txt", "w") as f:
        f.write(curl_cmd)
    
    print(f"\nCommand also saved to: {OUT / 'curl_command.txt'}")
    
    # Show parameter breakdown
    print("\n" + "=" * 80)
    print("URL PARAMETERS BREAKDOWN")
    print("=" * 80)
    
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(entry["request"]["url"])
    params = parse_qs(parsed.query)
    
    for key in ["q", "sclient", "source", "sca_esv", "sxsrf", "ei", "iflsig", "ved", "uact", "oq", "gs_lp"]:
        if key in params:
            value = params[key][0]
            if len(value) > 60:
                value = value[:60] + "..."
            print(f"  {key:12} = {value}")


if __name__ == "__main__":
    main()
