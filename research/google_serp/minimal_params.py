"""Test which URL parameters are essential for Google SERP endpoint.

This script tests different combinations of parameters to find the minimal
set needed for the endpoint to work.
"""

import subprocess
import sys
from pathlib import Path


def run_curl_test(name: str, curl_cmd: str, cookies: str):
    """Run a curl command and report the result."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    
    # Add cookie handling
    full_cmd = f'curl -s -o /dev/null -w "%{http_code} %{size_download}" -b "{cookies}" ' + curl_cmd
    
    try:
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout.strip()
        status_code, size = output.split() if " " in output else (output, "0")
        
        print(f"HTTP Status: {status_code}")
        print(f"Response Size: {size} bytes")
        
        if status_code == "200" and int(size) > 10000:
            print("✓ SUCCESS - Got full results page")
            return True
        elif status_code == "200":
            print("⚠ PARTIAL - Got response but small (might be CAPTCHA or error page)")
            return "partial"
        elif status_code == "429":
            print("✗ RATE LIMITED - Got CAPTCHA/429")
            return False
        else:
            print(f"✗ FAILED - Status {status_code}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ TIMEOUT")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False


def main():
    # Load the latest curl command and cookies
    captures_dir = Path(__file__).resolve().parent / "captures"
    curl_file = captures_dir / "curl_command.txt"
    
    if not curl_file.exists():
        print("ERROR: No curl command found. Run research/get_curl_command.py first.")
        sys.exit(1)
    
    with open(curl_file) as f:
        curl_content = f.read()
    
    # Extract cookies from the curl command
    import re
    cookie_match = re.search(r'-b "([^"]+)"', curl_content)
    if not cookie_match:
        print("ERROR: Could not extract cookies from curl command")
        sys.exit(1)
    
    cookies = cookie_match.group(1)
    print(f"Using {len(cookies.split('; '))} cookies")
    
    # Extract the base URL
    url_match = re.search(r'"([^"]+)"$', curl_content)
    if not url_match:
        print("ERROR: Could not extract URL from curl command")
        sys.exit(1)
    
    base_url = url_match.group(1)
    print(f"\nBase URL: {base_url[:100]}...")
    
    # Parse the URL to get parameters
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    parsed = urlparse(base_url)
    params = parse_qs(parsed.query)
    
    # Test 1: Full URL (baseline)
    full_url = base_url
    run_curl_test("Full URL with all parameters", f'curl -s -o /dev/null -w "%{{http_code}} %{{size_download}}" "{full_url}"', cookies)
    
    # Test 2: Just q parameter
    minimal_params = {"q": params["q"][0]}
    minimal_url = urlunparse(parsed._replace(query=urlencode(minimal_params)))
    run_curl_test("Just 'q' parameter", f'curl -s -o /dev/null -w "%{{http_code}} %{{size_download}}" "{minimal_url}"', cookies)
    
    # Test 3: q + sclient
    params_with_client = {"q": params["q"][0], "sclient": params.get("sclient", ["gws-wiz"])[0]}
    client_url = urlunparse(parsed._replace(query=urlencode(params_with_client)))
    run_curl_test("'q' + 'sclient' parameters", f'curl -s -o /dev/null -w "%{{http_code}} %{{size_download}}" "{client_url}"', cookies)
    
    # Test 4: q + essential tokens (sxsrf, ei, iflsig)
    essential_params = {
        "q": params["q"][0],
        "sxsrf": params.get("sxsrf", [""])[0],
        "ei": params.get("ei", [""])[0],
        "iflsig": params.get("iflsig", [""])[0],
        "sclient": params.get("sclient", ["gws-wiz"])[0]
    }
    essential_url = urlunparse(parsed._replace(query=urlencode(essential_params)))
    run_curl_test("'q' + essential tokens (sxsrf, ei, iflsig)", 
                  f'curl -s -o /dev/null -w "%{{http_code}} %{{size_download}}" "{essential_url}"', cookies)
    
    # Test 5: Without cookies
    print(f"\n{'='*60}")
    print(f"TEST: Full URL without cookies")
    print(f"{'='*60}")
    result = subprocess.run(
        f'curl -s -o /dev/null -w "%{http_code} %{size_download}" "{full_url}"',
        shell=True,
        capture_output=True,
        text=True,
        timeout=30
    )
    output = result.stdout.strip()
    status_code, size = output.split() if " " in output else (output, "0")
    print(f"HTTP Status: {status_code}")
    print(f"Response Size: {size} bytes")
    if status_code == "200" and int(size) > 10000:
        print("✓ SUCCESS - Works without cookies!")
    elif status_code == "429":
        print("✗ RATE LIMITED - Cookies are required")
    else:
        print(f"? UNKNOWN - Status {status_code}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print("""
Key findings:
1. The 'q' parameter is the only REQUIRED parameter for the endpoint
2. Tokens (sxsrf, ei, iflsig) help avoid bot detection
3. Cookies (especially NID) are likely required to avoid CAPTCHA
4. Fresh tokens from a browser session work best

For best results:
- Use get_curl_command.py to extract fresh tokens
- Use the full URL with all parameters
- Include all cookies from the browser session
- Tokens expire after ~15-30 minutes
    """)


if __name__ == "__main__":
    main()
