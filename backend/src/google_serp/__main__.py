"""Print one page of Google results and how long it took.

python -m google_serp "playwright python"          # SERP API (needs a key)
python -m google_serp --chrome "playwright python" # the Chrome session
"""

import argparse
import sys
import time

import config  # noqa: F401  (loads .env)

from .api import client_from_env
from .session import GoogleSerpSession


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m google_serp")
    parser.add_argument("query")
    parser.add_argument("--chrome", action="store_true", help="use Chrome, not the API")
    args = parser.parse_args()

    started = time.monotonic()
    if args.chrome:
        session = GoogleSerpSession().start()
        try:
            response = session.search(args.query)
        finally:
            session.close()
    else:
        client = client_from_env()
        if client is None:
            print("Set SERPER_API_KEY or SERPAPI_API_KEY in .env", file=sys.stderr)
            return 2
        response = client.search(args.query)
    elapsed = time.monotonic() - started

    for r in response.results:
        print(f"{r.position:>2}. {r.title}\n    {r.url}")
        meta = " · ".join(x for x in (r.site_name, r.date) if x)
        if meta:
            print(f"    [{meta}]")
        if r.snippet:
            print(f"    {r.snippet[:160]}")
    print(f"\n{len(response.results)} results in {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
