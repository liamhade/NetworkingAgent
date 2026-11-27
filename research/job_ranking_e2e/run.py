"""End-to-end run of the job-ranking pipeline, scripted (no UI, no saved search).

Usage (from the repo root, with the backend venv):

    backend/.venv/Scripts/python research/job_ranking_e2e/run.py [--user TEST_USER]
        [--search-id ID] [--usage-log PATH] [--json OUT.json]

Runs plan -> find_jobs -> filter -> rank_jobs -> find_people -> compile for the request of
the user's newest finished saved search (or `--search-id`), with the real boards, LLMs and
LinkedIn people search. Nothing is written to `database/`.

LLM usage goes to a scratch CSV (default: a temp file, so `backend/logs/llm_usage.csv` is
untouched); the rows it appends are summed per purpose. Prints, in markdown: LLM cost,
tokens and latency per step, wall time per node, job counts (found, after filter,
`text_source`, ranked, returned), the seniority check (jobs asking for more than the
user's experience, new-grad programmes) and the top jobs. Personal data (background text)
is never printed. Needs the API keys in the repo-root `.env`.
"""

import argparse
import csv
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

NEW_GRAD = re.compile(r"new[\s-]?grad|graduate|university|early career|class of|20(2[6-9])", re.I)
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director)\b", re.I)
INPUT_COLUMNS = (
    "input_tokens",
    "cache_read_tokens",
    "cache_write_5m_tokens",
    "cache_write_1h_tokens",
)


def pick_request(user: str, search_id: str | None):
    from userdata import history

    searches = history.load_searches(user, only_done=True)
    if search_id:
        searches = [s for s in searches if s.id == search_id]
    if not searches:
        sys.exit(f"No finished saved search for {user}.")
    return searches[0].request


def run_graph(request) -> tuple[dict, list[tuple[str, float]]]:
    """Run the graph, returning the merged node updates and (node, seconds) per node."""
    import config
    from llm import get_llm
    from llm_usage import usage_context
    from pipeline.graph import build_graph

    graph = build_graph(get_llm(), get_llm(config.RANK_MODEL))
    state: dict = {"trace": []}
    times: list[tuple[str, float]] = []
    last = time.perf_counter()
    with usage_context(user_id="e2e", request_id="e2e", search_id="e2e"):
        for mode, chunk in graph.stream(
            {"request": request, "trace": []}, stream_mode=["custom", "updates"]
        ):
            if mode != "updates":
                continue
            now = time.perf_counter()
            for node, update in chunk.items():
                times.append((node, now - last))
                for key, value in (update or {}).items():
                    if key == "trace":
                        state["trace"] = state["trace"] + value
                    else:
                        state[key] = value
            last = now
    return state, times


def usage_by_purpose(path: Path) -> dict[str, dict]:
    totals: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "in": 0, "out": 0, "cost": 0.0, "latency_s": 0.0, "models": set()}
    )
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            t = totals[row["purpose"]]
            t["calls"] += 1
            t["in"] += sum(int(row[k] or 0) for k in INPUT_COLUMNS)
            t["out"] += int(row["output_tokens"] or 0)
            t["cost"] += float(row["cost_usd"] or 0)
            t["latency_s"] += int(row["latency_ms"] or 0) / 1000
            t["models"].add(row["model"])
    return totals


def years_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", text or "")
    return float(match.group(1)) if match else None


def report(state: dict, times: list[tuple[str, float]], usage: dict, wall: float) -> str:
    out: list[str] = ["## LLM usage per step\n"]
    out.append("| Purpose | Model | Calls | Input tok | Output tok | Cost | Latency (sum) |")
    out.append("|---|---|---|---|---|---|---|")
    for purpose, t in usage.items():
        models = ", ".join(sorted(t["models"]))
        out.append(
            f"| {purpose} | {models} | {t['calls']} | {t['in']:,} | {t['out']:,} "
            f"| ${t['cost']:.4f} | {t['latency_s']:.1f} s |"
        )
    total = sum(t["cost"] for t in usage.values())
    out.append(f"\nTotal LLM cost: **${total:.4f}**\n")

    out.append("## Wall time per node\n")
    out.append("| Node | Seconds |\n|---|---|")
    out.extend(f"| {node} | {secs:.1f} |" for node, secs in times)
    out.append(f"\nTotal wall time: **{wall:.1f} s**\n")

    postings = state.get("postings", [])
    ranked = state.get("ranked", [])
    filt = [s for s in state.get("trace", []) if s.step == "filter"]
    out.append("## Job counts\n")
    out.append(f"- Found (find_jobs): {len(state.get('jobs', []))}")
    out.extend(f"- filter trace: {json.dumps(s.args)} -> {s.count}" for s in filt)
    out.append(f"- Sent to the ranker: {len(postings)}")
    out.append(f"- text_source: {dict(Counter(p.text_source for p in postings))}")
    out.append(f"- Ranked and returned: {len(ranked)}\n")

    unread = [p for p in postings if p.text_source == "none"]
    if unread:
        out.append("## Unread postings (text_source none)\n")
        out.append("| Host | Company | Title | Read outcome |")
        out.append("|---|---|---|---|")
        reads = {s.args.get("url"): s for s in state.get("trace", []) if s.source != "complete"}
        for p in unread:
            step = reads.get(p.url)
            outcome = "no read attempted (over max_reads)"
            if step is not None:
                outcome = f"{step.error or 'ok'} ({step.source}, {step.duration_ms} ms)"
            where = urlsplit(p.url)
            out.append(f"| {where.netloc}{where.path[:60]} | {p.company} | {p.title} | {outcome} |")
        out.append("")

    user_years = next((s.args.get("user_years") for s in filt if "user_years" in s.args), None)
    out.append(f"## Seniority check (user_years used by the filter: {user_years})\n")
    out.append("| Rank | Company | Title | Score | years_required | Flag |")
    out.append("|---|---|---|---|---|---|")
    for r in ranked:
        years = years_number(r.years_required)
        flags = []
        if years is not None and years >= 3:
            flags.append("asks 3+ yrs")
        if SENIOR.search(r.job.title):
            flags.append("senior title")
        if NEW_GRAD.search(r.job.title):
            flags.append("new-grad/year")
        if flags:
            out.append(
                f"| {r.rank} | {r.job.company} | {r.job.title} | {r.score} "
                f"| {r.years_required or '-'} | {', '.join(flags)} |"
            )

    out.append("\n## Top 12\n")
    out.append("| Rank | Company | Title | Score | years_required |")
    out.append("|---|---|---|---|---|")
    out.extend(
        f"| {r.rank} | {r.job.company} | {r.job.title} | {r.score} | {r.years_required or '-'} |"
        for r in ranked[:12]
    )
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--user", default="TEST_USER")
    parser.add_argument("--search-id")
    parser.add_argument("--usage-log", help="scratch CSV for LLM usage (default: a temp file)")
    parser.add_argument("--json", help="also dump the ranked jobs as JSON to this path")
    args = parser.parse_args()

    log = Path(args.usage_log or Path(tempfile.mkdtemp()) / "llm_usage.csv")
    os.environ["LLM_USAGE_LOG"] = str(log)  # before `config` is imported
    request = pick_request(args.user, args.search_id)
    start = time.perf_counter()
    state, times = run_graph(request)
    wall = time.perf_counter() - start
    if "results" not in state:
        sys.exit(f"Search ended without results: {state.get('error')}")
    print(report(state, times, usage_by_purpose(log), wall))
    if args.json:
        rows = [r.model_dump(exclude={"job": {"description"}}) for r in state["ranked"]]
        Path(args.json).write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
