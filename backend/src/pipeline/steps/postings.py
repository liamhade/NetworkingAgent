"""The `read_postings` node."""

import logging
from typing import TypeVar

from pydantic import BaseModel

import config
from pipeline.state import (
    PipelineState,
)
from pipeline.steps.common import short, status
from pipeline.steps.reading import read_pages
from schemas import (
    TraceStep,
)

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# --------------------------------------------------------------------- read_postings


def read_postings_node(state: PipelineState) -> dict:
    """read_page on the best posting of the top companies (`READ_POSTINGS` of them).

    Postings `rescore_jobs` already read are reused; only these few go on to compile."""
    already: dict[str, str] = state.get("postings") or {}
    postings: dict[str, str] = {}
    trace: list[TraceStep] = []
    urls = [c.jobs[0].url for c in state["chosen"] if c.jobs][: config.READ_POSTINGS]
    for url in urls:
        if url in already:
            postings[url] = already[url][: config.READ_POSTING_MAX_CHARS]
    missing = [url for url in urls if url not in postings]
    if missing:
        for url in missing:
            status(f"Reading {short(url.split('://', 1)[-1].removeprefix('www.'))}")
        read, trace = read_pages("read_postings", missing, config.READ_POSTING_MAX_CHARS)
        postings.update(read)
    return {"postings": postings, "trace": trace}
