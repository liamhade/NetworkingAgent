"""LLM token usage + cost logging (`llm_usage`). Mocked models only; no network."""

import contextvars
import csv
import json
import logging
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pipeline_fakes import DEFAULT_RANKING as RANKING
from pipeline_fakes import FakeSources, plan
from pydantic import BaseModel

import llm
import pipeline
import server
from llm_usage import (
    bind_context,
    callback,
    pricing,
    recorder,
    run_config,
    summary,
    usage_context,
    usage_handler,
)
from pipeline.state import CompanyRanking, SearchPlan
from schemas import ErrorEvent, ResultEvent, SearchRequest, SearchResults

REQUEST = SearchRequest(background="Analyst", location="NYC", looking_for="Data roles")
RESULTS = SearchResults(summary="ok", companies=[])


def usage(inp: int, out: int, read: int = 0, w5: int = 0, w1h: int = 0) -> dict[str, Any]:
    """`usage_metadata` shaped like langchain-anthropic's (input includes cache tokens)."""
    details: dict[str, int] = {"cache_read": read, "cache_creation": 0}
    if w5 or w1h:
        details |= {"ephemeral_5m_input_tokens": w5, "ephemeral_1h_input_tokens": w1h}
    total_in = inp + read + w5 + w1h
    return {
        "input_tokens": total_in,
        "output_tokens": out,
        "total_tokens": total_in + out,
        "input_token_details": details,
    }


def reply(content: str = "", tool_calls: list | None = None, **tokens: int) -> AIMessage:
    return AIMessage(
        content=content,
        tool_calls=tool_calls or [],
        usage_metadata=usage(**tokens) if tokens else None,
        response_metadata={"model_name": "claude-haiku-5-5"},
    )


class UsageChatModel(BaseChatModel):
    """Scripted chat model that reports token usage like ChatAnthropic does."""

    responses: list[AIMessage] = []
    structured: Any = None
    fail: bool = False

    @property
    def _llm_type(self) -> str:
        return "usage-fake"

    def _get_ls_params(self, stop: list[str] | None = None, **kwargs: Any) -> Any:
        return {"ls_provider": "anthropic", "ls_model_name": "claude-haiku-5-5"}

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.fail:
            raise RuntimeError("provider down")
        message = self.responses.pop(0) if self.responses else reply("Done.", inp=10, out=2)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "UsageChatModel":
        return self

    def with_structured_output(self, schema: type[BaseModel], **kwargs: Any):
        # Like the real thing: one model call, then a parser. `structured` may be a dict
        # with one answer per schema.
        answer = self.structured
        if isinstance(answer, dict) and all(isinstance(k, type) for k in answer):
            answer = answer.get(schema)
        return self | RunnableLambda(lambda _: answer)


def rows(path) -> list[dict[str, str]]:
    return summary.read_rows(path)


def _pipeline_model(**kwargs: Any) -> "UsageChatModel":
    """A model that answers the pipeline's three structured calls (one row each)."""
    return UsageChatModel(
        responses=[
            reply("{}", inp=1000, out=50, read=4000, w5=500),  # plan
            reply("{}", inp=1200, out=60, read=4500),  # rank_companies
            reply("{}", inp=6000, out=900),  # compile_results
        ],
        structured={SearchPlan: plan(), CompanyRanking: RANKING, SearchResults: RESULTS},
        **kwargs,
    )


def test_pipeline_logs_one_row_per_llm_node(usage_log, monkeypatch) -> None:
    FakeSources(monkeypatch)
    model = _pipeline_model()
    with usage_context(user_id="TEST_USER", search_id="s1", request_id="r1"):
        events = list(pipeline.run_search(REQUEST, llm=model))

    assert isinstance(events[-1], ResultEvent)
    logged = rows(usage_log)
    assert [r["purpose"] for r in logged] == ["plan", "rank_companies", "compile_results"]
    assert {(r["user_id"], r["search_id"], r["request_id"]) for r in logged} == {
        ("TEST_USER", "s1", "r1")
    }
    first = logged[0]
    assert first["provider"] == "anthropic"
    assert first["model"] == "claude-haiku-5-5"
    assert first["status"] == "ok"
    assert (first["input_tokens"], first["cache_read_tokens"]) == ("1000", "4000")
    assert (first["cache_write_5m_tokens"], first["cache_write_1h_tokens"]) == ("500", "0")
    assert first["output_tokens"] == "50"
    assert first["total_tokens"] == str(1000 + 4000 + 500 + 50)
    expected = (1000 * 0.10 + 4000 * 0.01 + 500 * 0.125 + 50 * 0.50) / 1e6
    assert float(first["cost_usd"]) == pytest.approx(expected)
    assert int(first["latency_ms"]) >= 0
    assert first["timestamp"].endswith("+00:00")


def test_header_written_once_and_concurrent_appends_stay_whole(usage_log) -> None:
    def write(i: int) -> None:
        recorder.write_row(
            recorder.UsageRow(
                timestamp=f"2026-11-12T00:00:{i:02d}+00:00",
                user_id="u",
                request_id="",
                search_id="",
                purpose="p",
                provider="anthropic",
                model="claude-haiku-5-5",
                status="ok",
                input_tokens=i,
                cache_read_tokens=0,
                cache_write_5m_tokens=0,
                cache_write_1h_tokens=0,
                output_tokens=1,
                total_tokens=i + 1,
                cost_usd=0.0,
                latency_ms=1,
            )
        )

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(write, range(40)))
    lines = usage_log.read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == recorder.COLUMNS
    assert sum(line.startswith("timestamp,") for line in lines) == 1
    assert len(lines) == 41
    parsed = list(csv.DictReader(lines))
    assert sorted(int(r["input_tokens"]) for r in parsed) == list(range(40))


def test_cost_math() -> None:
    cost = pricing.cost_usd(
        "anthropic",
        "claude-opus-5-5",
        uncached_input=1_000_000,
        output=1_000_000,
        cache_read=1_000_000,
        cache_write_5m=1_000_000,
        cache_write_1h=1_000_000,
    )
    assert cost == pytest.approx(4 + 20 + 0.20 + 5 + 8)
    # Dated snapshot ids use the base model's price.
    assert pricing.cost_usd(
        "anthropic", "claude-haiku-4-5-20251001", uncached_input=1_000_000, output=0
    ) == pytest.approx(1.0)


def test_haiku_long_context_prices_apply_over_100k_prompt_tokens() -> None:
    small = pricing.cost_usd("anthropic", "claude-haiku-5-5", uncached_input=100_000, output=0)
    assert small == pytest.approx(100_000 * 0.10 / 1e6)
    # Cache reads count toward prompt length: 60k + 50k > 100k, so everything is repriced.
    big = pricing.cost_usd(
        "anthropic", "claude-haiku-5-5", uncached_input=60_000, cache_read=50_000, output=1_000
    )
    assert big == pytest.approx((60_000 * 0.50 + 50_000 * 0.05 + 1_000 * 2.50) / 1e6)


def test_split_usage_generic_cache_creation_counts_as_5m() -> None:
    split = callback.split_usage(
        {
            "input_tokens": 1300,
            "output_tokens": 7,
            "input_token_details": {"cache_read": 200, "cache_creation": 100},
        }
    )
    assert split == {
        "input": 1000,
        "cache_read": 200,
        "cache_write_5m": 100,
        "cache_write_1h": 0,
        "output": 7,
        "total": 1307,
    }


def test_unknown_model_logs_blank_cost_and_warns_once(usage_log, caplog, monkeypatch) -> None:
    monkeypatch.setattr(pricing, "_warned", set())

    class Mystery(UsageChatModel):
        def _get_ls_params(self, stop: list[str] | None = None, **kwargs: Any) -> Any:
            return {"ls_provider": "acme", "ls_model_name": "mystery-1"}

    model = Mystery(
        responses=[
            AIMessage(content="a", usage_metadata=usage(10, 2)),
            AIMessage(content="b", usage_metadata=usage(10, 2)),
        ]
    )
    with caplog.at_level(logging.WARNING, logger="llm_usage.pricing"):
        model.invoke("hi", config=run_config("test"))
        model.invoke("hi", config=run_config("test"))
    logged = rows(usage_log)
    assert [(r["provider"], r["model"], r["cost_usd"]) for r in logged] == [
        ("acme", "mystery-1", ""),
        ("acme", "mystery-1", ""),
    ]
    assert logged[0]["total_tokens"] == "12"
    assert sum("acme:mystery-1" in r.message for r in caplog.records) == 1
    table = summary.summarize(logged)
    assert table[0]["unpriced_calls"] == 2


def test_model_error_is_logged_as_error_row(usage_log) -> None:
    model = UsageChatModel(fail=True)
    with pytest.raises(RuntimeError):
        model.invoke("hi", config=run_config("test"))
    (row,) = rows(usage_log)
    assert row["status"] == "error"
    assert "provider down" in row["error"]
    assert row["total_tokens"] == ""


def test_bind_context_survives_steps_run_in_fresh_contexts(usage_log) -> None:
    """Starlette advances sync generators in worker threads, each in a copied context."""
    model = UsageChatModel()

    def stream():
        yield "a"
        model.invoke("hi", config=run_config("step2"))
        yield "b"
        model.invoke("hi", config=run_config("step3"))

    events = bind_context(stream(), user_id="alice", search_id="s9")
    with ThreadPoolExecutor(1) as pool:
        out = []
        while True:
            item = pool.submit(contextvars.copy_context().run, next, events, None).result()
            if item is None:
                break
            out.append(item)
    assert out == ["a", "b"]
    assert [(r["user_id"], r["search_id"], r["purpose"]) for r in rows(usage_log)] == [
        ("alice", "s9", "step2"),
        ("alice", "s9", "step3"),
    ]


def test_context_reaches_calls_in_other_threads_via_copied_context(usage_log) -> None:
    model = UsageChatModel()
    with usage_context(user_id="bob", purpose="from_context"):
        ctx = contextvars.copy_context()
    thread = threading.Thread(target=ctx.run, args=(model.invoke, "hi"))
    # No run_config here: the model's own callbacks (as get_llm sets) still log.
    model.callbacks = [usage_handler]
    thread.start()
    thread.join()
    (row,) = rows(usage_log)
    assert (row["user_id"], row["purpose"]) == ("bob", "from_context")


def test_search_endpoint_tags_rows_with_user_and_saved_search_id(usage_log, monkeypatch) -> None:
    model = UsageChatModel(responses=[reply("x", inp=5, out=1)])

    def fake_run_search(request):
        model.invoke("hi", config=run_config("research"))
        yield ResultEvent(data=RESULTS)

    monkeypatch.setattr(pipeline, "run_search", fake_run_search)
    body = REQUEST.model_dump()
    with TestClient(server.app).stream("POST", "/api/search", json=body) as response:
        events = [json.loads(x[6:]) for x in response.iter_lines() if x.startswith("data: ")]
    saved_id = events[-1]["search"]["id"]
    (row,) = rows(usage_log)
    assert (row["user_id"], row["search_id"], row["request_id"]) == (
        "TEST_USER",
        saved_id,
        saved_id,
    )


def test_logging_failures_never_break_a_search(usage_log, monkeypatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(pricing, "cost_usd", boom)  # fails inside the callback
    monkeypatch.setattr(recorder, "log_path", boom)  # and the writer can't find its file
    FakeSources(monkeypatch)
    events = list(pipeline.run_search(REQUEST, llm=_pipeline_model()))
    assert isinstance(events[-1], ResultEvent)
    assert not any(isinstance(e, ErrorEvent) for e in events)


def test_writer_failure_is_swallowed(tmp_path, monkeypatch) -> None:
    import config

    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    monkeypatch.setattr(config, "LLM_USAGE_LOG", blocker / "llm_usage.csv")
    model = UsageChatModel()
    model.invoke("hi", config=run_config("test"))  # must not raise


def test_get_llm_attaches_usage_handler(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    llm.get_llm.cache_clear()
    try:
        model = llm.get_llm("anthropic:claude-haiku-5-5")
        assert usage_handler in model.callbacks
    finally:
        llm.get_llm.cache_clear()


def test_summary_groups_by_user_and_day(usage_log, capsys) -> None:
    usage_log.parent.mkdir(parents=True)
    usage_log.write_text(
        ",".join(recorder.COLUMNS)
        + "\n"
        + "2026-11-11T10:00:00+00:00,alice,r,s,research,anthropic,m,ok,10,0,0,0,5,15,0.5,1,\n"
        + "2026-11-12T10:00:00+00:00,alice,r,s,research,anthropic,m,ok,10,0,0,0,5,15,0.25,1,\n"
        + "2026-11-12T11:00:00+00:00,bob,r,s,compile_results,anthropic,m,ok,1,1,1,1,1,5,,1,\n",
        encoding="utf-8",
    )
    logged = rows(usage_log)
    overall = summary.summarize(logged)
    assert overall[0]["calls"] == 3
    assert overall[0]["total_tokens"] == 35
    assert overall[0]["cost_usd"] == pytest.approx(0.75)
    by_user = {r["user"]: r for r in summary.summarize(logged, ["user"])}
    assert by_user["alice"]["cost_usd"] == pytest.approx(0.75)
    assert by_user["bob"]["unpriced_calls"] == 1
    by_day = [(r["user"], r["day"], r["calls"]) for r in summary.summarize(logged, ["user", "day"])]
    assert by_day == [
        ("alice", "2026-11-11", 1),
        ("alice", "2026-11-12", 1),
        ("bob", "2026-11-12", 1),
    ]

    summary.main(["--by", "user", "--since", "2026-11-12"])
    out = capsys.readouterr().out
    assert "alice" in out and "bob" in out and "0.25" in out
