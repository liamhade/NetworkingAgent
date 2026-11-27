"""Reading posting pages in parallel, and cutting out the requirements."""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any, TypeVar

from pydantic import BaseModel

import config
import tools
from pipeline.steps.common import call, short
from schemas import (
    TraceStep,
)

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------- rescore_jobs

PAGE_READERS = 6
"""Postings read at once (plain HTTP for most boards, so they can run side by side)."""
page_pool = ThreadPoolExecutor(max_workers=PAGE_READERS, thread_name_prefix="read-page")


def read_pages(
    step: str, urls: list[str], max_chars: int
) -> tuple[dict[str, str], list[TraceStep]]:
    """`read_page` on every URL in parallel, waiting at most `config.READ_TIMEOUT_S` in all.

    Returns the Markdown of the pages read in time and one trace step per URL; a page still
    loading at the deadline is recorded as timed out and left to finish in the background."""

    def read(url: str) -> tuple[Any, TraceStep]:
        page, trace = call(
            step, "read_page", {"url": url}, lambda: tools.read_page(url, max_chars=max_chars)
        )
        if page is not None:
            trace.count = len(page.markdown)
            trace.note = "count = characters"
        return page, trace

    futures = {url: page_pool.submit(read, url) for url in dict.fromkeys(urls)}
    wait(futures.values(), timeout=config.READ_TIMEOUT_S)
    pages: dict[str, str] = {}
    trace: list[TraceStep] = []
    for url, future in futures.items():
        if not future.done():
            future.cancel()  # Not started yet: never runs. Running: its result is ignored.
            trace.append(
                TraceStep(
                    step=step,
                    source="read_page",
                    args={"url": url},
                    error=f"Timeout: not read within {config.READ_TIMEOUT_S:g} s",
                    duration_ms=round(config.READ_TIMEOUT_S * 1000),
                )
            )
            continue
        page, read_trace = future.result()
        trace.append(read_trace)
        if page is not None:
            pages[url] = page.markdown
    return pages, trace


_REQUIREMENTS = re.compile(
    r"^#*\s*\**\s*(?:requirements|qualifications|what you(?:'|’)ll need|what we(?:'|’)re "
    r"looking for|who you are|about you|you have|minimum qualifications|must have)",
    re.IGNORECASE | re.MULTILINE,
)


def posting_excerpt(text: str, limit: int) -> str:
    """At most `limit` characters of a posting, starting at its requirements section when it
    has a recognizable one (that is where experience and must-haves are listed)."""
    match = _REQUIREMENTS.search(text)
    if match and match.start() > limit // 4:
        head = text[: limit // 4].rstrip()
        return short(f"{head}\n…\n{text[match.start() :]}", limit)
    return short(text, limit)
