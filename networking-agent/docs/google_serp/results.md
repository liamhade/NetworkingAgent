# Google SERP Endpoint Guide

> Since this was written, the scripts moved to `networking-agent/research/google_serp/` and write to
> `research/google_serp/captures/` (gitignored). The paths below are from the original repo layout.

**Date:** 2026-11-10  
**Method:** Playwright (Python) driving visible Chrome, recording HAR, extracting curl command  
**Query used:** `python requests library`

---

## Quick Answer

**Endpoint:**
```
GET https://www.google.com/search?q=<query>
```

**Response:** Server-rendered HTML (`text/html`, ~400-900 KB)

**To use it:** You need fresh session tokens from a browser. See the "Working curl Example" section below.

---

## Working curl Example

### Step 1: Get Fresh Tokens

Run this script to extract a working curl command with fresh tokens:

```powershell
.\.venv\Scripts\python.exe research\get_curl_command.py "your search query"
```

- Opens Chrome and performs the search
- Waits for you to solve CAPTCHA if it appears
- Outputs a complete curl command with all cookies, headers, and parameters
- Saves the command to `captures/curl_command.txt`

### Step 2: Run the curl Command

Copy the output and run it. Tokens are valid for **~15-30 minutes**.

Example output (your tokens will be different):

```bash
curl -s \
    -b "SEARCH_SAMESITE=...; AEC=...; NID=...; __Secure-STRP=..." \
    -H "accept: text/html,application/xhtml+xml,...\" \
    -H "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36\" \
    -H "referer: https://www.google.com/" \
    "https://www.google.com/search?q=your+query&sca_esv=...&sxsrf=...&ei=...&iflsig=...&sclient=gws-wiz"
```

**Success indicators:**
- HTTP 200
- Response size > 10,000 bytes
- HTML contains your search results

## URL Parameters Reference

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `q` | **YES** | The search query (URL-encoded) | `python+requests+library` |
| `sclient` | Recommended | Client identifier | `gws-wiz` |
| `sxsrf` | Recommended | Anti-CSRF token from session | `AKL5yDhwN0QizmwkbA_...` |
| `ei` | Recommended | Event ID for tracking | `mX_zavPwF42FmLQP1rirQA` |
| `iflsig` | Recommended | Request signature | `AHSINFcAAAAAavONqRE8f_...` |
| `sca_esv` | Recommended | Session/anti-bot token | `03485a6e2a67408f` |
| `source` | Optional | Search origin | `hp` (homepage) |
| `ved` | Optional | Navigation tracking | `2ahUKEwj...` |
| `uact` | Optional | User action type | `5` |
| `oq` | Optional | Original query | Same as `q` |
| `gs_lp` | Optional | Autocomplete state | Long base64 string |

### Minimal Working URL

```
https://www.google.com/search?q=your+query&sclient=gws-wiz
```

This works but may trigger CAPTCHA more often.

### Full URL (Best Success Rate)

Include all parameters from `get_curl_command.py` output for best results.

---

## Required Cookies

| Cookie | Required | Purpose |
|--------|----------|---------|
| `NID` | **YES** | Google user ID (~500 chars) |
| `AEC` | Recommended | Account eligibility |
| `SEARCH_SAMESITE` | Recommended | Search session |
| `__Secure-STRP` | Recommended | Secure tracking |

**All cookies should be passed together** using curl's `-b` flag:

```bash
-b "NID=...; AEC=...; SEARCH_SAMESITE=...; __Secure-STRP=..."
```

---

## Required Headers

**Essential:**
```
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Referer: https://www.google.com/
Accept-Language: en-US
```

**Recommended (Chrome-specific):**
```
Sec-Ch-Ua: "Not-A.Brand";v="99", "Google Chrome";v="157", "Chromium";v="157"
Sec-Ch-Ua-Mobile: ?0
Sec-Ch-Ua-Platform: "Windows"
Sec-Fetch-Dest: document
Sec-Fetch-Mode: navigate
Sec-Fetch-Site: same-origin
X-Browser-Channel: stable
X-Browser-Year: 2026
```

## Bot Detection & CAPTCHA

### When CAPTCHA Appears

1. **First search from a new session** - Almost always triggers CAPTCHA
2. **Too many requests** - Rate limiting (HTTP 429)
3. **Missing/old tokens** - Tokens expire after ~15-30 minutes
4. **Missing cookies** - Especially `NID` cookie
5. **Non-browser headers** - Missing `sec-ch-ua-*` or `x-browser-*` headers

### CAPTCHA Flow

```
1. GET /search?q=... → 302 redirect to /sorry/
2. GET /sorry/index?continue=... → 429 with reCAPTCHA
3. Person solves CAPTCHA in browser
4. POST /sorry/index → 302 back to /search
5. GET /search?q=... → 200 with results
```

### Rate Limiting (Tested)

**Test Results:** Made 20 requests at 1 request/second (20 seconds total)
- **All 20 requests succeeded** with full ~93KB responses
- **No HTTP 429 (rate limit)** observed
- **No CAPTCHA** triggered during the test

**Conclusion:** Google allows at least **1 request per second** without rate limiting when using fresh tokens and proper cookies.

**Caveats:**
- This may vary based on your IP address, session age, and Google's current thresholds
- Tests were done with identical queries (different queries might be treated differently)
- Long-term behavior (hours/days) is untested

### How to Minimize CAPTCHA

1. **Use fresh tokens** - Extract with `get_curl_command.py` before each batch of requests
2. **Include all cookies** - Don't omit any cookies from the browser session
3. **Use all headers** - Include Chrome-specific headers
4. **Warm up the session** - Visit google.com first, then search
5. **Rate limit** - 1 request/second is safe; 5-10 seconds is more conservative
6. **Rotate user agents** - Use different Chrome versions if making many requests

### Unverified (needs testing)

- Whether HTTP/3 (QUIC) helps avoid bot detection
- Whether `x-browser-validation` header is required
- Exact token expiration time (estimated 15-30 min)
- Whether cookies can be reused across sessions
- What happens with 50+ requests in a row
- What happens with different queries vs. same query

---

## Complete Workflow

### For One-Off Searches

```powershell
# Get fresh curl command
.\.venv\Scripts\python.exe research\get_curl_command.py "your query"

# Copy the output and run it
curl -s -b "..." -H "..." "https://www.google.com/search?q=..."
```

### For Automated Scripts

```python
import subprocess
import re

# Step 1: Get fresh tokens
subprocess.run([
    ".\\.venv\\Scripts\\python.exe",
    "research/get_curl_command.py",
    "your query"
])

# Step 2: Read the curl command
with open("captures/curl_command.txt") as f:
    curl_cmd = f.read()

# Step 3: Execute it
result = subprocess.run(curl_cmd, shell=True, capture_output=True, text=True)
html = result.stdout

# Parse results from HTML
# (use BeautifulSoup or regex to extract titles, URLs, snippets)
```

## Can you call the endpoint directly (e.g. with curl)?

**No.** We tested it on 2026-11-10. We replayed the saved curl command, and the same request from Python `requests`, with cookies and headers captured 5 minutes earlier. Both got HTTP 200, but the body was Google's "enable JavaScript" page (a `<noscript>` refresh to `/httpservice/retry/enablejs`), not results. That page is about 93 KB, close to the size of a real response, so a status code or size check alone can't tell them apart. Check for `/httpservice/retry/enablejs` or for result `<h3>` elements instead.

Reasons this fails:

- **A real browser was blocked.** A genuine Chrome, running JavaScript and holding cookies, was still sent to the CAPTCHA. A bare HTTP client looks even less like a browser.
- **The page needs JavaScript.** Since early 2025, Google's search page expects JavaScript to run. Clients that can't run it (curl among them) generally get a page asking them to enable JavaScript instead of results. *This comes from public reporting, not from our capture.*
- **The tokens are tied to a session.** `sxsrf`, `iflsig`, `ei` and similar values come from a browser session and its cookies. Copying a URL from the capture into curl doesn't bring that session along.
- **Terms of service.** Google's terms don't allow automated querying of its search pages. If the research goes beyond observing the endpoint, check with legal/compliance before building anything that calls it automatically.

**If you need search results in code**, these are the routes Google allows:

- Google's **Programmable Search Engine / Custom Search JSON API** (has a free daily quota). Google has said this API is closing to new customers, with a move to Vertex AI Search, so check whether it is still available before relying on it.
- A commercial SERP API provider that handles access and compliance on its side.

## Result links are Google redirects

Organic results don't link to the destination site. Each title links to `/goto?url=<opaque token>` (with a `ping` to `/url?...`), and the real URL isn't anywhere in the result's HTML. Requesting the `/goto` link from inside the browser session returns a `302` with the real URL in `Location`. After a few quick requests, Google returns a page with a 3–5 second meta refresh instead, so resolving a full page of 10 results took about 20 seconds.

`<cite>` isn't always the site URL either. For forums and videos it holds metadata such as "8 comments · 3 years ago". The site name is in `span.VuuXrf`.

## Python package (`google_serp`)

The API runs searches in real Chrome with a persistent profile, kept outside the repo by default (see README.md). Google's cookies, including CAPTCHA clearance, stay in that profile, so a person solves a CAPTCHA once and later runs reuse the session. In testing, 6 separate runs on one profile got no CAPTCHA. Each search is one page load, plus one request per result to resolve its `/goto` link.

## Reproducing this

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe research\capture.py "your query"
```

`research/capture.py` opens Chrome, runs the search, and waits up to 3 minutes if a CAPTCHA appears so someone can solve it. Output goes to `captures/`:

- `traffic.har`: every request and response, including bodies (open it in Chrome DevTools → Network → Import HAR)
- `requests.json`: one summary line per request
- `screenshot.png`: the results page

---

## Limitations

1. **Tokens expire** - Need to refresh every 15-30 minutes
2. **CAPTCHA required** - At least once per session (person must solve it)
3. **Rate limited** - Too many requests triggers CAPTCHA or 429
4. **Terms of Service** - Google doesn't officially allow automated scraping
5. **HTML parsing required** - Response is HTML, not JSON (unlike official APIs)

---

## Alternatives

If you need a more stable solution:

1. **Google Custom Search JSON API** - Official API, free tier available
2. **SERP API providers** - Commercial services (serpapi.com, serply.io, etc.)
3. **Google Vertex AI Search** - Google's newer offering

---

## Files

- `src/google_serp/` - Python package for running searches (see README.md)
- `research/capture.py` - Original capture script (records HAR)
- `research/get_curl_command.py` - Extracts a curl command from a browser session
- `research/minimal_params.py` - Tests which parameters are required
- `research/rate_limit.py` - Rate limit test
- `captures/traffic.har` - Full network trace
- `captures/curl_command.txt` - **NEW** Last generated curl command
- `captures/requests.json` - Request summary
- `captures/screenshot.png` - Results page screenshot

---

## Testing Results

### What Works

✓ Full URL with all parameters + all cookies + all headers  
✓ Minimal URL (`q` + `sclient`) with cookies (may trigger CAPTCHA)  
✓ Reusing tokens for ~15 minutes  
✓ **1 request per second** (tested 20 requests, all succeeded)

### What Doesn't Work

✗ Just `q` parameter without cookies (always CAPTCHA)  
✗ Old tokens (>30 min) (CAPTCHA or 429)  
✗ Missing `NID` cookie (CAPTCHA)  

### Rate Limit Test

**Test:** 20 requests at 1 request/second with identical query
- **Result:** All 20 requests returned HTTP 200 with ~93KB responses
- **No rate limiting (429)** observed
- **No CAPTCHA** triggered

**Conclusion:** Safe to make at least 1 request per second with fresh tokens.

### Unverified

- Whether `sxsrf` token is strictly required or just helps
- Whether `iflsig` can be omitted
- What happens with 50+ consecutive requests
- What happens with different queries vs. same query
- Long-term behavior (hours/days of requests)
