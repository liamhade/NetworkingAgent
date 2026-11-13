"""Summarize `llm_usage.csv` by user, day, model, purpose or search.

Run from `networking-agent/backend/src`, e.g.
`..\\.venv\\Scripts\\python.exe -m llm_usage --by user day` or
`..\\.venv\\Scripts\\python.exe -m llm_usage --by model --since 2026-11-01 --user TEST_USER`.
"""

import argparse
import csv
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

from llm_usage import recorder

GROUPS = {
    "user": "user_id",
    "day": "timestamp",
    "month": "timestamp",
    "model": "model",
    "purpose": "purpose",
    "search": "search_id",
    "request": "request_id",
}
SUMS = [
    "input_tokens",
    "cache_read_tokens",
    "cache_write_5m_tokens",
    "cache_write_1h_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        # Skip a repeated header line (possible if two processes created the file at once).
        return [r for r in csv.DictReader(file) if r.get("timestamp") != "timestamp"]


def _key(row: dict[str, str], group: str) -> str:
    value = row.get(GROUPS[group], "")
    if group == "day":
        return value[:10]
    if group == "month":
        return value[:7]
    return value or "-"


def summarize(
    rows: Iterable[dict[str, str]], by: Sequence[str] = ()
) -> list[dict[str, str | int | float]]:
    """Totals per group (`by` = [] gives one overall row). Blank costs count as 0."""
    totals: dict[tuple[str, ...], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    unpriced: dict[tuple[str, ...], int] = defaultdict(int)
    for row in rows:
        key = tuple(_key(row, g) for g in by)
        bucket = totals[key]
        bucket["calls"] += 1
        for column in SUMS:
            text = row.get(column) or ""
            if text:
                bucket[column] += float(text)
            elif column == "cost_usd" and row.get("total_tokens"):
                unpriced[key] += 1
    result: list[dict[str, str | int | float]] = []
    for key in sorted(totals):
        bucket = totals[key]
        out: dict[str, str | int | float] = dict(zip(by, key, strict=True))
        out["calls"] = int(bucket["calls"])
        for column in SUMS:
            out[column] = round(bucket[column], 6) if column == "cost_usd" else int(bucket[column])
        out["unpriced_calls"] = unpriced[key]
        result.append(out)
    return result


def _print(table: list[dict[str, str | int | float]]) -> None:
    if not table:
        print("No LLM usage logged yet.")
        return
    headers = list(table[0])
    cells = [[str(row[h]) for h in headers] for row in table]
    widths = [max(len(h), *(len(c[i]) for c in cells)) for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True)))
    for row in cells:
        print("  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)))


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="llm_usage", description=__doc__.split("\n")[0])
    parser.add_argument("--by", nargs="*", default=[], choices=sorted(GROUPS))
    parser.add_argument("--path", type=Path, default=None, help="CSV file (default: config)")
    parser.add_argument("--user", help="only this user_id")
    parser.add_argument("--since", help="only rows on/after this ISO date, e.g. 2026-11-01")
    parser.add_argument("--until", help="only rows before this ISO date")
    args = parser.parse_args(argv)
    rows = read_rows(args.path or recorder.log_path())
    if args.user:
        rows = [r for r in rows if r.get("user_id") == args.user]
    if args.since:
        rows = [r for r in rows if r.get("timestamp", "") >= args.since]
    if args.until:
        rows = [r for r in rows if r.get("timestamp", "") < args.until]
    _print(summarize(rows, args.by))
