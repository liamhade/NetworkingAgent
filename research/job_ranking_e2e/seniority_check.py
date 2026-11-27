"""Live check of the ranker's seniority rule: do clearly-too-senior jobs score <= 40?

Usage (repo root, backend venv; spends a few cents of real LLM calls, nothing is saved to
`database/`, usage goes to a scratch CSV):

    backend/.venv/Scripts/python research/job_ranking_e2e/seniority_check.py [--user TEST_USER]
        [--senior 8] [--normal 8] [--usage-log PATH]

Takes the user's newest finished saved search request, plans and finds jobs as the pipeline
does (level-appropriate jobs: the normal `filter` output), searches BuiltInNYC for "senior
software engineer", "staff engineer" and "engineering manager" for real too-senior postings,
completes them with `complete_jobs`, mixes both sets and calls `rank_jobs_node` with the real
`RANK_MODEL`. Prints each job's title, years_required, level and score; PASS means every job
asking for 3+ years or titled Senior/Staff/Principal/Lead/Manager scored <= 40 (or was left
out by the ranker). Personal data (background text) is never printed.
"""

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

SENIOR_QUERIES = ("senior software engineer", "staff engineer", "engineering manager")
ATS_BOARDS = (
    ("greenhouse", "cloudflare"),
    ("greenhouse", "twilio"),
    ("greenhouse", "coinbase"),
    ("greenhouse", "robinhood"),
    ("greenhouse", "okta"),
    ("greenhouse", "datadog"),
    ("greenhouse", "stripe"),
    ("greenhouse", "airbnb"),
    ("lever", "palantir"),
    ("ashby", "ramp"),
    ("ashby", "notion"),
)
"""Greenhouse boards searched for too-senior engineering postings: their API gives the full
text without the HTTP 429 that builtinnyc.com answers a burst of page reads with."""
SENIOR_TITLE = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director)\b", re.I)
LIMIT = 40


def years_number(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", text or "")
    return float(match.group(1)) if match else None


def too_senior(title: str, years: str) -> bool:
    n = years_number(years)
    return bool(SENIOR_TITLE.search(title)) or (n is not None and n >= 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--user", default="TEST_USER")
    parser.add_argument("--senior", type=int, default=8)
    parser.add_argument("--normal", type=int, default=8)
    parser.add_argument(
        "--score-all",
        action="store_true",
        help="ask the ranker to return and score every job (it normally leaves clear "
        "misfits out, which also counts as a pass)",
    )
    parser.add_argument("--usage-log")
    args = parser.parse_args()

    log = Path(args.usage_log or Path(tempfile.mkdtemp()) / "llm_usage.csv")
    os.environ["LLM_USAGE_LOG"] = str(log)  # before `config` is imported

    from run import pick_request, usage_by_purpose

    import ats
    import config
    import postings
    import tools
    from builtin_nyc.models import JobFilter
    from llm import get_llm
    from llm_usage import usage_context
    from pipeline import steps
    from pipeline.state import Job
    from pipeline.steps.find_jobs import _job_from

    # builtinnyc.com answers a burst of reads with 429: read slowly so the texts arrive.
    config.READ_HOST_CONCURRENCY = 2
    config.READ_BUDGET_S = 120.0
    config.READ_RETRY_BACKOFF_S = 4.0
    request = pick_request(args.user, None)
    llm, ranker = get_llm(), get_llm(config.RANK_MODEL)
    state: dict = {"request": request, "trace": []}

    def apply(update: dict) -> None:
        for key, value in update.items():
            state[key] = state.get(key, []) + value if key == "trace" else value

    with usage_context(user_id="e2e", request_id="e2e", search_id="e2e"):
        for node in (steps.plan_node, steps.find_jobs_node, steps.filter_node):
            apply(node(state, llm) if node is steps.plan_node else node(state))
        print(f"user_years: {steps.user_years(request)}")
        normal = [
            p
            for p in state.get("postings", [])
            if not too_senior(p.title, p.years_required) and p.text_source != "none"
        ][: args.normal]
        print(f"level-appropriate jobs with text: {len(normal)} of {len(state['postings'])}")

        seen = {p.url for p in normal}
        senior_jobs = []
        for provider, board in ATS_BOARDS:
            try:
                listed = ats.get_provider(provider).list_jobs(board)
            except Exception as exc:  # a board that fails is skipped
                print(f"{provider}/{board}: {exc}", file=sys.stderr)
                continue
            for j in listed:
                if (
                    re.search(r"engineer|developer", j.title, re.I)
                    and SENIOR_TITLE.search(j.title)
                    and postings.reader_for(j.url)
                    and sum(x.company == j.company for x in senior_jobs) < 2
                    and len(senior_jobs) < args.senior
                ):
                    senior_jobs.append(
                        Job(
                            id="",
                            source="ats_jobs",
                            title=j.title,
                            url=j.url,
                            company=j.company,
                            location=j.location,
                        )
                    )
        # BuiltInNYC only tops up: its pages are 429-limited after a burst of reads.
        for query in SENIOR_QUERIES if len(senior_jobs) < args.senior else ():
            for raw in tools.builtin_jobs(JobFilter(search=query), 15):
                if raw["url"] not in seen and SENIOR_TITLE.search(raw["title"]):
                    seen.add(raw["url"])
                    senior_jobs.append(_job_from("builtin_jobs", raw))
        senior_jobs = senior_jobs[: args.senior]
        for i, job in enumerate(senior_jobs, 1):
            job.id = f"s{i}"
        senior_postings, _ = steps.complete_jobs(senior_jobs, len(senior_jobs), "seniority")
        print(f"too-senior jobs found: {len(senior_postings)}")

        everything = normal + senior_postings
        for i, job in enumerate(everything, 1):
            job.id = f"j{i}"
        senior_urls = {p.url for p in senior_postings}
        if args.score_all:
            import prompts

            original = prompts.rank_jobs_prompt
            extra = "\n- For this evaluation return EVERY job, with its score, even misfits."
            prompts.rank_jobs_prompt = lambda max_jobs=None: original(max_jobs) + extra
        config.MAX_JOBS = len(everything)  # score every job, so none is cut by the top-N
        apply(steps.rank_jobs_node({**state, "postings": everything}, ranker))

    scores = {r.job.url: r for r in state["ranked"]}
    print("\n| Set | Company | Title | years_required | level | text | Score | Verdict |")
    print("|---|---|---|---|---|---|---|---|")
    failures, senior_scores = [], []
    for p in everything:
        r = scores.get(p.url)
        years = (r.years_required if r else "") or p.years_required
        flagged = too_senior(p.title, years)
        score = r.score if r else None
        verdict = ""
        if flagged:
            ok = score is None or score <= LIMIT
            verdict = "ok" if ok else "FAIL"
            if score is not None:
                senior_scores.append(score)
            if not ok:
                failures.append(p.title)
        print(
            f"| {'senior' if p.url in senior_urls else 'normal'} | {p.company} | {p.title} "
            f"| {years or '-'} | {p.level or '-'} | {p.text_source} "
            f"| {score if score is not None else 'left out'} | {verdict} |"
        )
    if senior_scores:
        print(f"\nFlagged jobs scored: min {min(senior_scores)}, max {max(senior_scores)}")
    print(f"Result: {'FAIL ' + str(failures) if failures else 'PASS'}")
    for purpose, t in usage_by_purpose(log).items():
        print(f"{purpose}: {t['calls']} calls, ${t['cost']:.4f}")
    print(f"Total: ${sum(t['cost'] for t in usage_by_purpose(log).values()):.4f}")


if __name__ == "__main__":
    main()
