"""Completing found jobs into `JobPosting`s: the posting's full text, one read per job.

Not wired into the graph yet; `filter` and `rank_jobs` call `complete_jobs` on the jobs worth
ranking (at most `RANK_MAX_JOBS`), not on everything the boards returned.

Where the text comes from, in order:

1. the board's search API already returned it (`Job.description`, USAJOBS): `text_source="api"`,
   no read;
2. `postings.reader_for(url)`: the per-posting API of Greenhouse, Lever and Ashby (`api`;
   their list responses reach the pipeline as card dicts without the text), BuiltIn and
   Workable page parsers (`parser`);
3. the generic `read_page` (`page`).

A read that fails, times out or is rate limited (builtinnyc.com answers a repeat burst with
HTTP 429) keeps the job with its card text and `text_source="none"`.
"""

import threading
from concurrent.futures import Future, wait
from typing import cast
from urllib.parse import urlsplit

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
HOST_READS = 3
"""Reads of one site at once, so a burst doesn't trip its rate limit."""

_host_slots: dict[str, threading.Semaphore] = {}
_host_lock = threading.Lock()


def _slot(url: str) -> threading.Semaphore:
    host = urlsplit(url).netloc.lower()
    with _host_lock:
        return _host_slots.setdefault(host, threading.Semaphore(HOST_READS))


def _read(job: Job, step: str) -> tuple[postings.ParsedPosting | None, TextSource, TraceStep]:
    """One read: (what was found, text_source, trace step)."""
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

    with _slot(job.url):
        parsed, trace = call(step, source, {"url": job.url}, fetch)
    if parsed is not None and parsed.description:
        trace.count = len(parsed.description)
        trace.note = f"text_source={text_source}; count = characters"
    elif not trace.error:
        trace.error = "No posting text found on the page"
    return parsed, text_source, trace


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
    `max_reads` are read in parallel (the shared page pool, each site at most `HOST_READS` at
    a time) and the whole batch waits at most `config.READ_TIMEOUT_S`. Jobs beyond the cap, and
    reads that fail, time out or get HTTP 429, keep the card text with `text_source="none"`.

    The trace has one step per read (url, source, characters or error) and one summary step.
    """
    to_read = [j for j in jobs if not j.description][: max(0, max_reads)]
    futures: dict[int, Future] = {id(j): page_pool.submit(_read, j, step) for j in to_read}
    wait(futures.values(), timeout=config.READ_TIMEOUT_S)

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
            trace.append(
                TraceStep(
                    step=step,
                    source="read_page",
                    args={"url": job.url},
                    error=f"Timeout: not read within {config.READ_TIMEOUT_S:g} s",
                    duration_ms=round(config.READ_TIMEOUT_S * 1000),
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
