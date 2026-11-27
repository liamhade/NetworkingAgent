"""Measure the experimental `rescore_jobs` step on saved searches: time, tokens and cost.

Usage (from the repo root, with the backend venv):

    backend/.venv/Scripts/python research/rescore_experiment/run.py [--per-company 2]
        [--usage-log PATH] [--max-chars 2500]

For each finished search under `database/`, it rebuilds the ranked companies from the saved
results, then runs `pipeline.steps.rescore_jobs_node` with the real LLM and `read_page`:
the top `--per-company` postings of every company are read in full and scored again.
It prints the reads' wall time, the LLM call's tokens/cost/latency (from the usage log,
written to `--usage-log` so the app's own log is left alone) and each job's score before
and after. Nothing is saved back to the searches.
"""

import argparse
import csv
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-company", type=int, default=2)
    parser.add_argument("--max-chars", type=int, default=2500)
    parser.add_argument("--usage-log", default=str(Path(tempfile.gettempdir()) / "rescore.csv"))
    args = parser.parse_args()

    os.environ["LLM_USAGE_LOG"] = args.usage_log
    os.environ["RESCORE_POSTINGS"] = str(args.per_company)
    os.environ["RESCORE_POSTING_MAX_CHARS"] = str(args.max_chars)
    sys.path.insert(0, str(ROOT / "backend" / "src"))

    import read_page
    from llm import get_llm
    from pipeline import steps
    from pipeline.state import ChosenCompany, Job
    from userdata import history

    log = Path(args.usage_log)
    log.unlink(missing_ok=True)
    import config

    llm = get_llm(config.RESCORE_MODEL)  # LLM_MODEL-independent; set RESCORE_MODEL to compare
    users = ROOT / "database" / "users"
    for user_dir in sorted(p for p in users.iterdir() if p.is_dir()):
        for record in history.load_searches(user_dir.name, only_done=True):
            chosen = []
            n = 0
            for company in record.results.companies:
                jobs, scores = [], {}
                for job in company.jobs:
                    n += 1
                    jobs.append(Job(id=f"j{n}", source="saved", title=job.title, url=job.url))
                    scores[f"j{n}"] = job.score or 0
                chosen.append(
                    ChosenCompany(
                        name=company.name,
                        score=company.score or 0,
                        jobs=jobs,
                        job_scores=scores,
                    )
                )
            read_page.clear_cache()
            started = time.perf_counter()
            out = steps.rescore_jobs_node({"request": record.request, "chosen": chosen}, llm)
            total = time.perf_counter() - started
            reads = [s for s in out.get("trace", []) if s.source == "read_page"]
            llm_steps = [s for s in out.get("trace", []) if s.source == "llm"]
            ok = [s for s in reads if not s.error]
            print(f"\n=== {record.title} ({len(chosen)} companies) ===")
            print(
                f"postings read: {len(ok)}/{len(reads)} ok, slowest read "
                f"{max((s.duration_ms or 0) for s in reads) / 1000:.1f}s, "
                f"avg {sum(len(t) for t in out.get('postings', {}).values()) // max(1, len(ok))}"
                " chars"
            )
            for s in reads:
                if s.error:
                    print(f"  read failed: {s.args['url']} ({s.error[:80]})")
            if llm_steps:
                print(f"llm: {llm_steps[0].duration_ms / 1000:.1f}s {llm_steps[0].error or ''}")
            print(f"step total: {total:.1f}s")
            before = {c.name: c for c in chosen}
            for c in out.get("chosen", []):
                old = before[c.name]
                print(f"  {c.name}: {old.score} -> {c.score}")
                for j in c.jobs[: args.per_company]:
                    print(
                        f"    {j.title[:60]}: {old.job_scores.get(j.id)} -> "
                        f"{c.job_scores.get(j.id)}  [{j.years_required or '?'}]"
                    )
    if log.exists():
        rows = list(csv.DictReader(log.open(encoding="utf-8")))
        print("\n=== LLM usage (rescore_jobs) ===")
        for r in rows:
            print(
                f"model {r['model']}: in {r['input_tokens']} / out {r['output_tokens']} tokens, "
                f"${float(r['cost_usd']):.5f}, {int(r['latency_ms']) / 1000:.1f}s"
            )
    read_page.shutdown()


if __name__ == "__main__":
    main()
