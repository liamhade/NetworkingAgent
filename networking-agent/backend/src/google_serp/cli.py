"""Command-line interface: ``google-serp "query" ["query" ...]``."""

import argparse
import json
import logging
import sys
from collections.abc import Sequence

from . import __version__
from .errors import GoogleSerpError
from .models import SearchResponse
from .session import GoogleSerpSession


def _print_text(response: SearchResponse, limit: int) -> None:
    meta = response.metadata
    print(f"Query: {meta.query} (page {meta.page})")
    if meta.results_count:
        print(f"Results: {meta.results_count}")
    if meta.search_time is not None:
        print(f"Search time: {meta.search_time}s")
    print(f"Parsed {len(response.results)} results\n")
    for r in response.results[:limit]:
        print(f"{r.position}. {r.title}")
        print(f"   {r.url}")
        if r.site_name:
            print(f"   Site: {r.site_name}")
        if r.snippet:
            print(f"   {r.snippet[:200]}")
        print()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="google-serp",
        description="Search Google in Chrome and print structured results.",
    )
    parser.add_argument("queries", nargs="+", metavar="QUERY")
    parser.add_argument(
        "--json", action="store_true", help="print JSON (one object per query, as a list)"
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=10,
        help="results to print per query in text mode (default: 10)",
    )
    parser.add_argument(
        "-p",
        "--page",
        type=int,
        default=1,
        metavar="N",
        help="results page to start at, 10 results per page (default: 1)",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        metavar="N",
        help="number of consecutive pages to fetch per query (default: 1)",
    )
    parser.add_argument(
        "--no-resolve",
        action="store_true",
        help="keep Google's /goto links instead of resolving real URLs (faster)",
    )
    parser.add_argument(
        "--show-window", action="store_true", help="keep the Chrome window on-screen"
    )
    parser.add_argument("--profile-dir", help="Chrome profile directory to use")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)
    if args.page < 1 or args.pages < 1:
        parser.error("--page and --pages must be >= 1")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    responses = []
    try:
        with GoogleSerpSession(profile_dir=args.profile_dir, hidden=not args.show_window) as serp:
            for query in args.queries:
                for page in range(args.page, args.page + args.pages):
                    response = serp.search(query, resolve_urls=not args.no_resolve, page=page)
                    if args.json:
                        responses.append(response.to_dict())
                    else:
                        _print_text(response, args.limit)
    except GoogleSerpError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.json:
        json.dump(responses, sys.stdout, indent=2, ensure_ascii=False)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
