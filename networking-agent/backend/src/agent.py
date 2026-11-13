"""Where the LangChain ReAct agent lives.

`run_search()` runs in two phases:

1. **Research**: a LangChain tool-calling agent searches BuiltInNYC and Google. Each
   tool call and tool result is reported as a `StatusEvent`.
2. **Compile**: one structured-output call turns the research transcript into
   `SearchResults`, which is reported as a `ResultEvent`. The same call writes each
   person's example LinkedIn note (`connect_message`).

The prompts live in `prompts.py`.
"""

import json
import logging
from collections.abc import Iterator
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.errors import GraphRecursionError

import config
from llm import get_llm
from llm_usage import run_config
from prompts import RESEARCH_PROMPT, compile_prompt
from schemas import (
    AgentEvent,
    ErrorEvent,
    ResultEvent,
    SearchRequest,
    SearchResults,
    StatusEvent,
)
from tools import ALL_TOOLS

log = logging.getLogger(__name__)


def format_profile(request: SearchRequest) -> str:
    return (
        f"<background>\n{request.background.strip()}\n</background>\n"
        f"<location>{request.location.strip() or 'not specified'}</location>\n"
        f"<looking_for>\n{request.looking_for.strip()}\n</looking_for>"
    )


def _short(value: Any, limit: int = 60) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe_tool_call(name: str, args: dict[str, Any]) -> str:
    """Human-readable progress line for a tool call."""
    if name == "search_builtin_jobs":
        what = args.get("search") or args.get("category") or "all roles"
        return f"Searching BuiltInNYC jobs for “{_short(what)}”"
    if name == "search_builtin_companies":
        industries = ", ".join(args.get("industries") or []) or "all industries"
        return f"Browsing BuiltInNYC companies in {_short(industries)}"
    if name == "google_search":
        return f"Searching Google for “{_short(args.get('query', ''))}”"
    if name == "linkedin_people":
        return f"Looking for {args.get('keywords', 'people')} at {args.get('company', '?')}"
    if name == "read_page":
        url = str(args.get("url", ""))
        return f"Reading {_short(url.split('://', 1)[-1].removeprefix('www.'))}"
    return f"Running {name}"


def describe_tool_result(message: ToolMessage) -> str:
    """Human-readable progress line for a tool result."""
    try:
        payload = json.loads(message.content) if isinstance(message.content, str) else None
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and "error" in payload:
        return f"{message.name} failed: {_short(payload['error'], 120)}"
    if isinstance(payload, dict) and "markdown" in payload:
        title = payload.get("title") or payload.get("final_url") or "page"
        return f"Read “{_short(title)}” ({len(payload['markdown']):,} characters)"
    if isinstance(payload, list):
        return f"{message.name}: {len(payload)} result{'s' if len(payload) != 1 else ''}"
    return f"{message.name} finished"


def _message_text(message: BaseMessage) -> str:
    return str(message.text)


def transcript(messages: list[BaseMessage]) -> str:
    """Plain-text rendering of the research conversation for the compile step."""
    parts: list[str] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            parts.append(f"## User profile\n{_message_text(message)}")
        elif isinstance(message, AIMessage):
            text = _message_text(message).strip()
            if text:
                parts.append(f"## Agent note\n{text}")
            for call in message.tool_calls:
                parts.append(f"## Tool call: {call['name']}\n{json.dumps(call['args'])}")
        elif isinstance(message, ToolMessage):
            parts.append(f"## Tool result: {message.name}\n{_message_text(message)}")
    return "\n\n".join(parts)


def build_agent(llm: BaseChatModel, tools: list[BaseTool]):
    return create_agent(model=llm, tools=tools, system_prompt=RESEARCH_PROMPT)


def compile_results(
    llm: BaseChatModel, request: SearchRequest, messages: list[BaseMessage]
) -> SearchResults:
    model = llm.with_structured_output(SearchResults, method="json_schema")
    result = model.invoke(
        [
            SystemMessage(compile_prompt()),
            HumanMessage(
                f"{format_profile(request)}\n\n<research>\n{transcript(messages)}\n</research>"
            ),
        ],
        config=run_config("compile_results"),
    )
    return result if isinstance(result, SearchResults) else SearchResults.model_validate(result)


def run_search(
    request: SearchRequest,
    llm: BaseChatModel | None = None,
    tools: list[BaseTool] | None = None,
    recursion_limit: int | None = None,
) -> Iterator[AgentEvent]:
    """Research and compile results for `request`, yielding progress events."""
    llm = llm or get_llm()
    agent = build_agent(llm, tools if tools is not None else ALL_TOOLS)
    first = HumanMessage(format_profile(request))
    messages: list[BaseMessage] = [first]

    yield StatusEvent(message="Reading your profile")
    try:
        for update in agent.stream(
            {"messages": [first]},
            config=run_config(
                "research", recursion_limit=recursion_limit or config.AGENT_RECURSION_LIMIT
            ),
            stream_mode="updates",
        ):
            for node_update in update.values():
                for message in (node_update or {}).get("messages", []):
                    messages.append(message)
                    if isinstance(message, AIMessage):
                        for call in message.tool_calls:
                            yield StatusEvent(
                                message=describe_tool_call(call["name"], call["args"])
                            )
                    elif isinstance(message, ToolMessage):
                        yield StatusEvent(message=describe_tool_result(message))
    except GraphRecursionError:
        log.info("Agent hit the step limit; compiling what it found")
        yield StatusEvent(message="Step limit reached; compiling what was found")
    except Exception as exc:  # noqa: BLE001
        log.exception("Agent research failed")
        if not any(isinstance(m, ToolMessage) for m in messages):
            yield ErrorEvent(message=f"Research failed: {exc}")
            return
        yield StatusEvent(message="Research stopped early; compiling what was found")

    yield StatusEvent(message="Compiling your results")
    try:
        yield ResultEvent(data=compile_results(llm, request, messages))
    except Exception as exc:  # noqa: BLE001
        log.exception("Compiling results failed")
        yield ErrorEvent(message=f"Could not compile results: {exc}")
