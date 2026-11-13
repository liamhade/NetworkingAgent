"""Throwaway: polite single-URL fetch for researching conservationjobboard.com.

Usage: fetch.py <url> <outfile>. Waits 3.5 s before the request, logs to requests.log,
and stops (non-zero exit) on 403/429/captcha/Cloudflare challenge.
"""

import sys
import time
from pathlib import Path

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

url, name = sys.argv[1], sys.argv[2]
time.sleep(3.5)
r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}, timeout=30)
(OUT / name).write_bytes(r.content)
with open(OUT / "requests.log", "a", encoding="utf-8") as f:
    f.write(f"{r.status_code} {len(r.content)} {r.url}\n")
body = r.text.lower()
blocked = r.status_code in (403, 429, 503) or "cf-chl" in body or "captcha" in body
print(r.status_code, len(r.content), r.url, r.headers.get("content-type"), r.headers.get("server"))
sys.exit(2 if blocked else 0)
