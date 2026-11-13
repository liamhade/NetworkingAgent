"""The read_page LangChain tool and its agent integration (no network)."""

import json

from langchain_core.messages import ToolMessage
from rp_fakes import FakeWeb, fixture_bytes

import agent
import tools


def test_read_page_is_registered() -> None:
    assert tools.read_page in tools.ALL_TOOLS
    schema = tools.read_page.args
    assert set(schema) == {"url", "method", "max_chars"}
    assert "full" in schema["method"]["enum"]
    assert "read_page" in agent.RESEARCH_PROMPT


def test_tool_returns_page_json(web: FakeWeb) -> None:
    web.page("https://acme.com/blog/x", fixture_bytes("article.html"))
    out = json.loads(tools.read_page.invoke({"url": "https://acme.com/blog/x"}))
    assert set(out) == {"url", "final_url", "method", "title", "markdown", "truncated"}
    assert out["method"] == "static"
    assert "(https://acme.com/docs/airflow)" in out["markdown"]


def test_tool_default_budget_and_max_chars(web: FakeWeb) -> None:
    web.page("https://acme.com/long", "<html><body><main>" + "<p>word " * 5000 + "</main>")
    out = json.loads(tools.read_page.invoke({"url": "https://acme.com/long"}))
    assert out["truncated"] and len(out["markdown"]) <= tools.READ_PAGE_MAX_CHARS
    out = json.loads(tools.read_page.invoke({"url": "https://acme.com/long", "max_chars": 2000}))
    assert len(out["markdown"]) <= 2000


def test_tool_returns_linkedin_refusal_as_error(web: FakeWeb) -> None:
    out = json.loads(tools.read_page.invoke({"url": "https://www.linkedin.com/in/janedoe"}))
    assert "PageBlocked" in out["error"]
    assert "linkedin_people" in out["error"]


def test_tool_returns_fetch_errors(web: FakeWeb) -> None:
    out = json.loads(tools.read_page.invoke({"url": "https://acme.com/missing"}))
    assert "404" in out["error"]


def test_agent_status_lines() -> None:
    assert (
        agent.describe_tool_call("read_page", {"url": "https://www.acme.com/careers"})
        == "Reading acme.com/careers"
    )
    message = ToolMessage(
        content=json.dumps({"title": "Careers", "markdown": "x" * 1234, "final_url": "u"}),
        name="read_page",
        tool_call_id="1",
    )
    assert agent.describe_tool_result(message) == "Read “Careers” (1,234 characters)"
