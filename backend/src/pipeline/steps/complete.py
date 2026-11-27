"""Completing found jobs into `JobPosting`s: the posting's full text, one read per job.

`filter` calls `complete_jobs` on the jobs worth ranking (at most `RANK_MAX_JOBS`), not on
everything the boards returned.

Where the text comes from, in order:

1. the board's search API already returned it (`Job.description`, USAJOBS): `text_source="api"`,
   no read;
2. `postings.reader_for(url)`: the per-posting API of Greenhouse, Lever and Ashby (`api`;
   their list responses reach the pipeline as card dicts without the text), BuiltIn and
   Workable page parsers (`parser`);
3. the generic `read_page` (`page`).

A read that fails, times out or is rate limited (builtinnyc.com answers a repeat burst with
HTTP 429) keeps the job with its card text and `text_source="none"`. Each read trace step has
`args["outcome"]`: ok, error, rate_limited or timeout.
"""

import threading
import time
from concurrent.futures import Future, InvalidStateError, wait
from typing import cast
from urllib.parse import urlsplit

import requests

import config
import postings
import tools
from experience import years_required
from pipeline.state import Job, JobPosting, TextSource
from pipeline.steps.common import call
from pipeline.steps.reading import page_pool, posting_excerpt
from schemas import TraceStep

REQUIREMENTS_CHARS = 1200
"""Length of `JobPosting.requirements`, the part of the text the ranking card carries."""
PAGE_MAX_CHARS = 12_000
"""Characters kept of a generic page read."""
RETRY_STATUS = 429

_host_slots: dict[str, threading.Semaphore] = {}
_host_lock = threading.Lock()


def _slot(url: str) -> threading.Semaphore:
    host = urlsplit(url).netloc.lower()
    with _host_lock:
        return _host_slots.setdefault(host, threading.Semaphore(config.READ_HOST_CONCURRENCY))


class _Batch:
    """What the reads of one `complete_jobs` call share: the hosts that answered 429."""

    def __init__(self) -> None:
        self.limited: set[str] = set()
        self.lock = threading.Lock()

    def is_limited(self, host: str) -> bool:
        with self.lock:
            return host in self.limited

    def mark(self, host: str) -> None:
        with self.lock:
            self.limited.add(host)


_Outcome = tuple[postings.ParsedPosting | None, TextSource, TraceStep]


def _read(
    job: Job, step: str, deadline: float, batch: _Batch, first: bool = True
) -> _Outcome | None:
    """One read: (what was found, text_source, trace step).

    Returns None when the site answered 429 and a retry should be scheduled (the caller does
    that after `config.READ_RETRY_BACKOFF_S`, without holding a worker). Once a host has
    answered 429, the batch sends it no new first reads: they fall back to the card text
    at once with outcome "rate_limited"."""
    host = urlsplit(job.url).netloc.lower()
    known = postings.reader_for(job.url)
    if known is not None:
        source, kind, reader = known
        text_source = cast(TextSource, kind)

        def fetch() -> postings.ParsedPosting | None:
            return reader(job.url)

    else:
        source, text_source = "read_page", "page"

        def fetch() -> postings.ParsedPosting | None:
            page = tools.read_page(job.url, max_chars=PAGE_MAX_CHARS)
            return postings.ParsedPosting(description=page.markdown.strip())

    if first and batch.is_limited(host):
        trace = TraceStep(
            step=step,
            source=source,
            args={"url": job.url, "outcome": "rate_limited"},
            error=f"HTTP {RETRY_STATUS}: {host} rate limited this batch; not read",
        )
        return None, text_source, trace

    limited: list[bool] = []

    def guarded() -> postings.ParsedPosting | None:
        try:
            return fetch()
        except requests.HTTPError as exc:
            if getattr(exc.response, "status_code", None) == RETRY_STATUS:
                limited.append(True)
            raise

    with _slot(job.url):
        parsed, trace = call(step, source, {"url": job.url}, guarded)
    if limited:
        batch.mark(host)
        if first and time.monotonic() + config.READ_RETRY_BACKOFF_S < deadline:
            return None
        trace.args["outcome"] = "rate_limited"
    elif parsed is not None and parsed.description:
        trace.count = len(parsed.description)
        trace.note = f"text_source={text_source}; count = characters"
        trace.args["outcome"] = "ok"
    else:
        trace.args["outcome"] = "error"
        if not trace.error:
            trace.error = "No posting text found on the page"
    return parsed, text_source, trace


def _submit(job: Job, step: str, deadline: float, batch: _Batch) -> Future[_Outcome]:
    """Run the read on the page pool. A 429 schedules the one retry on a timer, as a new pool
    task, so no worker sleeps through the backoff."""
    result: Future[_Outcome] = Future()

    def finish(outcome: _Outcome | None = None, error: BaseException | None = None) -> None:
        try:
            if error is not None:
                result.set_exception(error)
            elif outcome is not None:
                result.set_result(outcome)
        except InvalidStateError:  # the batch timed out and cancelled it
            pass

    def run(first: bool) -> None:
        if result.done():
            return
        try:
            outcome = _read(job, step, deadline, batch, first)
        except BaseException as exc:  # noqa: BLE001
            finish(error=exc)
            return
        if outcome is not None:
            finish(outcome)
            return
        timer = threading.Timer(config.READ_RETRY_BACKOFF_S, lambda: page_pool.submit(run, False))
        timer.daemon = True
        timer.start()

    page_pool.submit(run, True)
    return result


def _posting(
    job: Job, parsed: postings.ParsedPosting | None, text_source: TextSource
) -> JobPosting:
    """`job` plus the text read (`parsed` is None or empty when the read failed)."""
    base = job.model_dump()
    if parsed is None or not parsed.description:
        return JobPosting(**base, requirements=job.summary, text_source="none")
    base.update(
        description=parsed.description,
        location=job.location or parsed.location,
        salary=job.salary or parsed.salary,
        posted_at=job.posted_at or parsed.posted_at,
        level=job.level or parsed.level,
        company=job.company or parsed.company,
        years_required=parsed.years_required
        or years_required(parsed.description)
        or job.years_required,
    )
    return JobPosting(
        **base,
        requirements=posting_excerpt(parsed.description, REQUIREMENTS_CHARS),
        text_source=text_source,
    )


def complete_jobs(
    jobs: list[Job], max_reads: int, step: str = "complete"
) -> tuple[list[JobPosting], list[TraceStep]]:
    """Turn `jobs` into `JobPosting`s, in the same order and never dropping one.

    Jobs whose board API gave the text are completed without a read. Of the others, the first
    `max_reads` are read in parallel (the shared page pool, each site at most
    `config.READ_HOST_CONCURRENCY` at a time; a 429 is retried once after a short backoff on a
    timer, not in a worker, and a host that answered 429 gets no new reads this batch) and the
    whole batch waits at most `config.READ_BUDGET_S`. Jobs beyond the cap, and
    reads that fail, time out or get HTTP 429, keep the card text with `text_source="none"`.

    The trace has one step per read (url, source, characters or error) and one summary step.
    """
    to_read = [j for j in jobs if not j.description][: max(0, max_reads)]
    deadline = time.monotonic() + config.READ_BUDGET_S
    batch = _Batch()
    futures = {id(j): _submit(j, step, deadline, batch) for j in to_read}
    wait(futures.values(), timeout=config.READ_BUDGET_S)

    completed: list[JobPosting] = []
    trace: list[TraceStep] = []
    for job in jobs:
        future = futures.get(id(job))
        if job.description:
            completed.append(
                _posting(job, postings.ParsedPosting(description=job.description), "api")
            )
        elif future is None:
            completed.append(_posting(job, None, "none"))
        elif not future.done():
            future.cancel()  # Not started: never runs. Running: its result is ignored.
            known = postings.reader_for(job.url)
            trace.append(
                TraceStep(
                    step=step,
                    source=known[0] if known else "read_page",
                    args={"url": job.url, "outcome": "timeout"},
                    error=f"Timeout: not read within {config.READ_BUDGET_S:g} s",
                    duration_ms=round(config.READ_BUDGET_S * 1000),
                )
            )
            completed.append(_posting(job, None, "none"))
        else:
            parsed, text_source, read_trace = future.result()
            trace.append(read_trace)
            completed.append(_posting(job, parsed, text_source))

    counts = {
        s: sum(p.text_source == s for p in completed) for s in ("api", "parser", "page", "none")
    }
    trace.append(
        TraceStep(
            step=step,
            source="complete",
            args={"jobs": len(jobs), "max_reads": max_reads, **counts},
            count=len(completed),
            note="args: jobs per text_source",
        )
    )
    return completed, trace
