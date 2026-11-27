"""Shared helpers of the graph nodes and the on-demand people search."""

import json
import logging
import time
from collections.abc import Callable, Iterable
from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from pydantic import BaseModel

from entities.keys import normalize_company_name, normalize_url
from llm_usage import run_config
from schemas import (
    SearchRequest,
    StatusEvent,
    TraceStep,
)

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# --------------------------------------------------------------------------- helpers


def status(message: str) -> None:
    """Report progress as a `StatusEvent` (a no-op outside a running graph)."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        return
    writer(StatusEvent(message=message))


def call(
    step: str, source: str, args: dict[str, Any], fn: Callable[[], Any]
) -> tuple[Any, TraceStep]:
    """Run `fn`, timing it; an exception becomes the trace step's `error` (value None)."""
    started = time.perf_counter()
    value, error = None, ""
    try:
        value = fn()
    except Exception as exc:  # noqa: BLE001
        log.warning("%s/%s failed: %s", step, source, exc)
        error = f"{type(exc).__name__}: {exc}"
    trace = TraceStep(
        step=step,
        source=source,
        args=args,
        count=len(value) if isinstance(value, list) else None,
        error=error,
        duration_ms=round((time.perf_counter() - started) * 1000),
    )
    return value, trace


def structured(llm: BaseChatModel, schema: type[T], system: str, human: str, purpose: str) -> T:
    """One structured-output call, logged under `purpose` in the LLM usage CSV."""
    model = llm.with_structured_output(schema, method="json_schema")
    result = model.invoke([SystemMessage(system), HumanMessage(human)], config=run_config(purpose))
    return result if isinstance(result, schema) else schema.model_validate(result)


def clean_schools(education: Iterable[str]) -> list[str]:
    """School names with blanks and repeats (any case) removed, order kept."""
    schools: list[str] = []
    for name in education:
        name = " ".join(name.split())
        if name and name.lower() not in {s.lower() for s in schools}:
            schools.append(name)
    return schools


def format_profile(request: SearchRequest) -> str:
    schools = clean_schools(request.education)
    education = f"<education>{'; '.join(schools)}</education>\n" if schools else ""
    return (
        f"<background>\n{request.background.strip()}\n</background>\n"
        f"{education}"
        f"<location>{request.location.strip() or 'not specified'}</location>\n"
        f"<looking_for>\n{request.looking_for.strip()}\n</looking_for>"
    )


def short(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def url_key(url: str) -> str:
    return normalize_url(url) or url.strip()


def name_key(name: str) -> str:
    return normalize_company_name(name)


def dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1)


def scored(value: int) -> int:
    return max(0, min(100, int(value)))
