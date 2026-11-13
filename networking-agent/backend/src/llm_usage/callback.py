"""LangChain callback that turns every chat-model call into a `UsageRow`.

It fires once per model request, so a tool-calling agent logs one row per turn and a
`with_structured_output` call logs one row too. Context (user, search, purpose) is
captured when the call starts; purpose comes from run metadata `llm_purpose` first, then
from `usage_context(purpose=...)`.
"""

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from llm_usage import context, pricing, recorder

log = logging.getLogger(__name__)

PURPOSE_KEY = "llm_purpose"


class UsageCallbackHandler(BaseCallbackHandler):
    """Writes one CSV row per LLM call. Errors here are logged, never raised."""

    raise_error = False

    def __init__(self) -> None:
        self._pending: dict[UUID, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # -- start -------------------------------------------------------------------------

    def _start(self, run_id: UUID, metadata: dict[str, Any] | None) -> None:
        try:
            metadata = metadata or {}
            ctx = context.current()
            with self._lock:
                self._pending[run_id] = {
                    "started": time.perf_counter(),
                    "ctx": ctx,
                    "purpose": str(metadata.get(PURPOSE_KEY) or ctx.purpose or "unknown"),
                    "provider": str(metadata.get("ls_provider") or ""),
                    "model": str(metadata.get("ls_model_name") or ""),
                }
        except Exception:  # noqa: BLE001
            log.warning("LLM usage start hook failed", exc_info=True)

    def on_chat_model_start(
        self, serialized: Any, messages: Any, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._start(run_id, kwargs.get("metadata"))

    def on_llm_start(self, serialized: Any, prompts: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._start(run_id, kwargs.get("metadata"))

    # -- end ---------------------------------------------------------------------------

    def _pop(self, run_id: UUID) -> dict[str, Any]:
        with self._lock:
            pending = self._pending.pop(run_id, None)
        return pending or {
            "started": None,
            "ctx": context.current(),
            "purpose": context.current().purpose or "unknown",
            "provider": "",
            "model": "",
        }

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        try:
            pending = self._pop(run_id)
            usage, model = _usage_and_model(response)
            self._write(pending, usage, model or pending["model"], status="ok")
        except Exception:  # noqa: BLE001
            log.warning("Could not record LLM usage", exc_info=True)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        try:
            pending = self._pop(run_id)
            self._write(pending, None, pending["model"], status="error", error=repr(error)[:300])
        except Exception:  # noqa: BLE001
            log.warning("Could not record LLM usage", exc_info=True)

    def _write(
        self,
        pending: dict[str, Any],
        usage: dict[str, Any] | None,
        model: str,
        *,
        status: str,
        error: str = "",
    ) -> None:
        ctx: context.UsageContext = pending["ctx"]
        provider = pending["provider"]
        started = pending["started"]
        latency = round((time.perf_counter() - started) * 1000) if started is not None else None
        tokens = split_usage(usage) if usage else None
        cost = None
        if tokens is not None:
            cost = pricing.cost_usd(
                provider,
                model,
                uncached_input=tokens["input"],
                output=tokens["output"],
                cache_read=tokens["cache_read"],
                cache_write_5m=tokens["cache_write_5m"],
                cache_write_1h=tokens["cache_write_1h"],
            )
        recorder.write_row(
            recorder.UsageRow(
                timestamp=datetime.now(UTC).isoformat(timespec="milliseconds"),
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                search_id=ctx.search_id,
                purpose=pending["purpose"],
                provider=provider,
                model=model,
                status=status,
                input_tokens=tokens["input"] if tokens else None,
                cache_read_tokens=tokens["cache_read"] if tokens else None,
                cache_write_5m_tokens=tokens["cache_write_5m"] if tokens else None,
                cache_write_1h_tokens=tokens["cache_write_1h"] if tokens else None,
                output_tokens=tokens["output"] if tokens else None,
                total_tokens=tokens["total"] if tokens else None,
                cost_usd=cost,
                latency_ms=latency,
                error=error,
            )
        )


def _usage_and_model(response: LLMResult) -> tuple[dict[str, Any] | None, str]:
    """Summed `usage_metadata` of the generations, and the model that answered."""
    usage: dict[str, Any] | None = None
    model = ""
    for generation in (g for batch in response.generations for g in batch):
        message = getattr(generation, "message", None)
        if message is None:
            continue
        meta = getattr(message, "response_metadata", None) or {}
        model = model or str(meta.get("model_name") or meta.get("model") or "")
        found = getattr(message, "usage_metadata", None)
        if found:
            usage = _add(usage, dict(found))
    if usage is None and isinstance(response.llm_output, dict):
        model = model or str(response.llm_output.get("model_name") or "")
    return usage, model


def _add(total: dict[str, Any] | None, usage: dict[str, Any]) -> dict[str, Any]:
    if total is None:
        return usage
    details = dict(total.get("input_token_details") or {})
    for key, value in (usage.get("input_token_details") or {}).items():
        details[key] = (details.get(key) or 0) + (value or 0)
    return {
        "input_tokens": total.get("input_tokens", 0) + usage.get("input_tokens", 0),
        "output_tokens": total.get("output_tokens", 0) + usage.get("output_tokens", 0),
        "total_tokens": total.get("total_tokens", 0) + usage.get("total_tokens", 0),
        "input_token_details": details,
    }


def split_usage(usage: dict[str, Any]) -> dict[str, int]:
    """Split LangChain `UsageMetadata` into the billed categories.

    LangChain's `input_tokens` includes cache reads and writes; we report uncached input
    separately. A cache write without a TTL breakdown counts as the default 5-minute TTL.
    """
    details = usage.get("input_token_details") or {}
    cache_read = int(details.get("cache_read") or 0)
    write_5m = details.get("ephemeral_5m_input_tokens")
    write_1h = details.get("ephemeral_1h_input_tokens")
    generic = int(details.get("cache_creation") or 0)
    write_5m = int(write_5m or 0) + generic
    write_1h = int(write_1h or 0)
    all_input = int(usage.get("input_tokens") or 0)
    output = int(usage.get("output_tokens") or 0)
    uncached = max(all_input - cache_read - write_5m - write_1h, 0)
    return {
        "input": uncached,
        "cache_read": cache_read,
        "cache_write_5m": write_5m,
        "cache_write_1h": write_1h,
        "output": output,
        "total": uncached + cache_read + write_5m + write_1h + output,
    }


usage_handler = UsageCallbackHandler()
"""The one shared handler (LangChain de-duplicates it when attached in several places)."""


def run_config(purpose: str, **extra: Any) -> dict[str, Any]:
    """A LangChain `config` that logs usage and labels the call site."""
    return {"callbacks": [usage_handler], "metadata": {PURPOSE_KEY: purpose}, **extra}
