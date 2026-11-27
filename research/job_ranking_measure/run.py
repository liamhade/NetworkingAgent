"""Phase 1 of docs/job-ranking/plan.md: how many jobs a search finds, how many already have
full posting text from the board API, and how long reading the rest takes.

Usage (from the repo root, with the backend venv):

    backend/.venv/Scripts/python research/job_ranking_measure/run.py [--user TEST_USER]
        [--no-rerun] [--no-reads] [--read-limit 40]

1. Saved searches (`database/users/<user>/searches`): per-source job counts from the saved
   trace (`find_jobs` steps), listings sent to `rank_companies`, and the postings the real
   run read.
2. Re-run (no LLM): the newest search's saved plan goes through `find_jobs_node` with every
   keyless board on, giving a realistic count of jobs found before ranking.
3. Text availability per job, from the board code (see TEXT_FROM_API) applied to the job URL.
4. Reads: every job without API text goes through `read_page` in parallel (the app's
   `PAGE_READERS` workers). Prints per-read time p50/p90/max, success rate, characters, and
   how many would finish inside `config.READ_TIMEOUT_S` counted from the batch start.
5. `backend/logs/llm_usage.csv`: `rank_companies` input/output token sizes.

Nothing is written back to the database.
"""

import argparse
import csv
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

# Board (by URL host) -> what its search API hands us for a job. Verified in the code:
# ats/lever.py, ats/ashby.py (descriptions are in the response, dropped by AtsJob after
# `years_required`), ats/greenhouse.py (no content: `?content=true` is not used),
# ats/workable.py (list API has no description), usajobs/api.py (QualificationSummary only),
# builtin_nyc/api.py (card tagline), conservation_jobboard (card fields), google_serp (snippet).
TEXT_FROM_API = {
    "lever": "full",
    "ashby": "full",
    "usajobs": "partial",
    "greenhouse": "none",
    "workable": "none",
    "builtin": "card",
    "conservation": "card",
    "other": "none",
}


def board_of(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    for key, needle in (
        ("lever", "lever.co"),
        ("ashby", "ashbyhq.com"),
        ("greenhouse", "greenhouse.io"),
        ("workable", "workable.com"),
        ("usajobs", "usajobs.gov"),
        ("builtin", "builtinnyc.com"),
        ("conservation", "conservationjobboard.com"),
    ):
        if needle in host:
            return key
    return "other"


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def saved_trace_counts(records: list) -> None:
    print("\n## Saved searches (trace)")
    for rec in records:
        added: Counter = Counter()
        for s in rec.trace:
            if s.step == "find_jobs" and s.note and s.note.endswith(" new"):
                added[s.source] += int(s.note.split()[0])
        ranked = [
            s for s in rec.trace if s.step == "rank_companies" and s.source == "llm"
        ]
        listings = ranked[0].args.get("jobs") if ranked else None
        reads = [
            s
            for s in rec.trace
            if s.step == "read_postings" and s.source == "read_page"
        ]
        n_jobs = sum(len(c.jobs) for c in rec.results.companies)
        print(
            f"- {rec.id[:8]} {rec.created_at.date()}: jobs added per source {dict(added)}"
            f" (total {sum(added.values())}); listings ranked {listings}; final jobs {n_jobs}"
            f" in {len(rec.results.companies)} companies; postings read "
            f"{[(s.duration_ms, s.count) for s in reads]} (ms, chars)"
        )


def rerun_find_jobs(record) -> list:
    from boards import default_config
    from pipeline import steps
    from pipeline.state import SearchPlan

    plan_step = next(s for s in record.trace if s.step == "plan" and s.source == "llm")
    plan = SearchPlan.model_validate(plan_step.args)
    request = record.request.model_copy(update={"boards": default_config()})
    started = time.perf_counter()
    out = steps.find_jobs_node({"request": request, "plan": plan})
    print(
        f"\n## Re-run of find_jobs for {record.id[:8]} ({time.perf_counter() - started:.0f}s)"
    )
    for s in out["trace"]:
        if s.source in {"boards", "builtin_companies"}:
            continue
        print(f"- {s.source}: {s.note or s.error or ''} {json.dumps(s.args)[:90]}")
    return out["jobs"]


def availability(jobs: list) -> dict[str, list]:
    by_board: dict[str, list] = defaultdict(list)
    for job in jobs:
        by_board[board_of(job.url)].append(job)
    print("\n## Jobs found by board and text from the board API")
    print("| board | jobs | via Google | API text | share |")
    print("|---|---|---|---|---|")
    for board, group in sorted(by_board.items(), key=lambda kv: -len(kv[1])):
        google = sum(j.source == "google_search" for j in group)
        print(
            f"| {board} | {len(group)} | {google} | {TEXT_FROM_API[board]} "
            f"| {len(group) / len(jobs):.0%} |"
        )
    full = sum(len(g) for b, g in by_board.items() if TEXT_FROM_API[b] == "full")
    print(f"\nFull text from the API: {full}/{len(jobs)} = {full / len(jobs):.0%}")
    print(
        "(jobs found via Google have no API text today: only a board-API search gives it)"
    )
    return by_board


def timed_reads(urls: list[str]) -> None:
    import config
    import read_page
    from pipeline.steps import PAGE_READERS

    read_page.clear_cache()
    started = time.perf_counter()

    def read(url: str) -> tuple[str, float, int, str]:
        t0 = time.perf_counter()
        try:
            page = read_page.read_page(url, max_chars=12_000)
            return url, time.perf_counter() - t0, len(page.markdown), ""
        except Exception as e:  # noqa: BLE001 - any failure is a data point
            return url, time.perf_counter() - t0, 0, f"{type(e).__name__}: {e}"[:80]

    results = []
    with ThreadPoolExecutor(max_workers=PAGE_READERS) as pool:
        futures = [pool.submit(read, u) for u in urls]
        for f in futures:
            url, took, chars, err = f.result()
            results.append((url, took, chars, err, time.perf_counter() - started))
    wall = time.perf_counter() - started
    ok = [r for r in results if not r[3] and r[2] > 0]
    times = [r[1] for r in results]
    in_time = [r for r in ok if r[4] <= config.READ_TIMEOUT_S]
    print(f"\n## Reads ({len(urls)} pages, {PAGE_READERS} in parallel)")
    print(
        f"- wall time for the whole batch: {wall:.1f}s (READ_TIMEOUT_S = {config.READ_TIMEOUT_S:g})"
    )
    print(
        f"- per read p50 {pct(times, 0.5):.1f}s, p90 {pct(times, 0.9):.1f}s, max {max(times):.1f}s"
    )
    print(f"- success {len(ok)}/{len(results)} = {len(ok) / len(results):.0%}")
    chars = [r[2] for r in ok]
    if chars:
        print(
            f"- chars per success: median {int(statistics.median(chars))}, "
            f"min {min(chars)}, max {max(chars)}"
        )
    print(
        f"- ok and finished inside the {config.READ_TIMEOUT_S:g}s batch: {len(in_time)}"
    )
    by_board: dict[str, list] = defaultdict(list)
    for r in results:
        by_board[board_of(r[0])].append(r)
    print("\n| board | reads | ok | p50 s | max s | median chars |")
    print("|---|---|---|---|---|---|")
    for board, rows in by_board.items():
        good = [r for r in rows if not r[3] and r[2] > 0]
        t = [r[1] for r in rows]
        c = [r[2] for r in good]
        med = int(statistics.median(c)) if c else 0
        print(
            f"| {board} | {len(rows)} | {len(good)} | {pct(t, 0.5):.1f} | {max(t):.1f} | {med} |"
        )
    for r in results:
        if r[3] or r[2] == 0:
            print(f"  failed: {r[0][:90]} ({r[3] or 'empty'})")
    read_page.shutdown()


def usage_log() -> None:
    path = ROOT / "backend" / "logs" / "llm_usage.csv"
    if not path.exists():
        return
    rows = [
        r
        for r in csv.DictReader(path.open(encoding="utf-8"))
        if r["purpose"] == "rank_companies" and r["status"] == "ok"
    ]
    if not rows:
        return
    tin = [int(r["input_tokens"]) for r in rows]
    tout = [int(r["output_tokens"]) for r in rows]
    print(f"\n## rank_companies in llm_usage.csv ({len(rows)} calls)")
    print(
        f"- input tokens min {min(tin)}, p50 {int(pct(tin, 0.5))}, max {max(tin)}; "
        f"output min {min(tout)}, p50 {int(pct(tout, 0.5))}, max {max(tout)}"
    )
    print(
        f"- mean cost ${sum(float(r['cost_usd']) for r in rows) / len(rows):.4f} per call"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="TEST_USER")
    parser.add_argument("--no-rerun", action="store_true")
    parser.add_argument("--no-reads", action="store_true")
    parser.add_argument("--read-limit", type=int, default=40)
    args = parser.parse_args()

    from userdata import history

    records = history.load_searches(args.user, only_done=True)
    print(f"{len(records)} finished searches for {args.user}")
    saved_trace_counts(records)

    jobs: list = []
    if records and not args.no_rerun:
        newest = max(records, key=lambda r: r.created_at)
        jobs = rerun_find_jobs(newest)
    if not jobs:  # fall back to the final results of the saved searches
        from pipeline.state import Job

        for rec in records:
            for c in rec.results.companies:
                jobs += [
                    Job(id="", source="saved", title=j.title, url=j.url) for j in c.jobs
                ]
        print("\n(using only the saved final results: jobs after ranking, not before)")
    if jobs:
        by_board = availability(jobs)
        if not args.no_reads:
            need = [
                j.url
                for b, g in by_board.items()
                if TEXT_FROM_API[b] != "full"
                for j in g
            ]
            timed_reads(need[: args.read_limit])
    usage_log()


if __name__ == "__main__":
    main()
