"""Test Google SERP rate limiting by making requests every second."""

import subprocess
import time
import re
from pathlib import Path


def extract_url_and_cookies(curl_file: Path):
    """Extract URL and cookies from the saved curl command."""
    with open(curl_file) as f:
        content = f.read()
    
    # Extract cookies
    cookie_match = re.search(r'-b "([^"]+)"', content)
    if not cookie_match:
        raise ValueError("Could not extract cookies")
    cookies = cookie_match.group(1)
    
    # Extract URL
    url_match = re.search(r'"(https://www\.google\.com/search\?[^\"]+)"$', content)
    if not url_match:
        raise ValueError("Could not extract URL")
    url = url_match.group(1)
    
    return cookies, url


def test_request(url: str, cookies: str, request_num: int):
    """Make a single request and return the result."""
    # Save to temp file to get actual size
    temp_file = Path(__file__).resolve().parent / "captures" / "temp_response.html"
    cmd = f'curl -s -b "{cookies}" "{url}" -o "{temp_file}" -w "%{{http_code}}"'
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        status = result.stdout.strip()
        
        # Get actual file size
        if temp_file.exists():
            size = temp_file.stat().st_size
            # Clean up
            temp_file.unlink()
            return status, size
        return status, 0
    except subprocess.TimeoutExpired:
        return "TIMEOUT", 0
    except Exception as e:
        return f"ERROR: {e}", 0


def main():
    captures_dir = Path(__file__).resolve().parent / "captures"
    curl_file = captures_dir / "curl_command.txt"
    
    if not curl_file.exists():
        print("ERROR: No curl command found. Run research/get_curl_command.py first.")
        return
    
    cookies, url = extract_url_and_cookies(curl_file)
    
    print("=" * 70)
    print("RATE LIMIT TEST: Making requests every second")
    print("=" * 70)
    print(f"URL: {url[:80]}...")
    print(f"Cookies: {len(cookies)} characters")
    print("\nStarting test (20 requests, 1 second apart)...\n")
    print(f"{'#':>2} | {'Status':>7} | {'Size':>10} | Result")
    print("-" * 70)
    
    results = []
    
    for i in range(1, 21):
        status, size = test_request(url, cookies, i)
        
        # Determine result
        if status == "200" and size > 10000:
            result = "✓ SUCCESS"
        elif status == "200":
            result = "⚠ SMALL"
        elif status == "429":
            result = "✗ RATE LIMITED"
        elif status == "TIMEOUT":
            result = "✗ TIMEOUT"
        else:
            result = f"✗ {status}"
        
        results.append((status, size, result))
        print(f"{i:>2} | {status:>7} | {size:>10} | {result}")
        
        # Wait 1 second between requests
        if i < 20:
            time.sleep(1)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    success_count = sum(1 for s, sz, _ in results if s == "200" and sz > 10000)
    rate_limited = sum(1 for s, _, _ in results if s == "429")
    
    print(f"\nSuccessful requests: {success_count}/20")
    print(f"Rate limited (429): {rate_limited}/20")
    
    if rate_limited > 0:
        first_429 = next((i for i, (s, _, _) in enumerate(results, 1) if s == "429"), None)
        print(f"First 429 occurred at request #{first_429}")
        print(f"\n⚠ Rate limit threshold: ~{first_429 - 1} requests")
    
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    if rate_limited == 0:
        print("✓ No rate limiting observed with 1 request/second")
        print("  However, this may vary based on your IP, session age, etc.")
    else:
        print(f"✗ Rate limiting occurred after {first_429 - 1} requests")
        print("  Consider waiting 5-10 seconds between requests")
    
    print("\nGeneral recommendations:")
    print("  - Wait 5-10 seconds between requests for safety")
    print("  - Refresh tokens every 15-30 minutes")
    print("  - Monitor for HTTP 429 responses")
    print("  - Consider rotating user agents for high-volume use")


if __name__ == "__main__":
    main()
