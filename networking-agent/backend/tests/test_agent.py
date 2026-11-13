import json

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

import agent
from schemas import ErrorEvent, ResultEvent, SearchRequest, SearchResults, StatusEvent

REQUEST = SearchRequest(
    background="I am a data analyst with 3 years of SQL and Python.",
    location="New York, NY",
    looking_for="Senior data analyst roles in fintech",
)

RESULTS = SearchResults.model_validate(
    {
        "summary": "Fintech analytics roles in NYC.",
        "companies": [
            {
                "name": "Ramp",
                "url": "https://www.builtinnyc.com/company/ramp",
                "description": "Corporate cards.",
                "alignment": "You know fintech.",
                "jobs": [
                    {
                        "title": "Senior Data Analyst",
                        "url": "https://www.builtinnyc.com/job/1",
                        "location": "New York, NY",
                        "salary": "",
                        "alignment": "Matches your SQL skills.",
                    }
                ],
                "people": [],
            }
        ],
    }
)


@tool
def search_builtin_jobs(search: str) -> str:
    """Fake BuiltIn job search."""
    return json.dumps([{"title": "Senior Data Analyst", "url": "https://www.builtinnyc.com/job/1"}])


def _call(i: int, search: str = "x") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "search_builtin_jobs", "args": {"search": search}, "id": f"c{i}"}],
    )


def test_run_search_streams_status_then_result(scripted_model) -> None:
    model = scripted_model(
        responses=[_call(1, "data analyst"), AIMessage(content="Found one strong job at Ramp.")],
        structured=RESULTS,
    )
    events = list(agent.run_search(REQUEST, llm=model, tools=[search_builtin_jobs]))

    statuses = [e.message for e in events if isinstance(e, StatusEvent)]
    assert "Searching BuiltInNYC jobs for “data analyst”" in statuses
    assert "search_builtin_jobs: 1 result" in statuses
    assert isinstance(events[-1], ResultEvent)
    assert events[-1].data == RESULTS

    compile_input = model.structured_calls[0]["input"][1].content
    assert "https://www.builtinnyc.com/job/1" in compile_input
    assert "Found one strong job at Ramp." in compile_input
    assert model.structured_calls[0]["kwargs"] == {"method": "json_schema"}


def test_run_search_compiles_after_step_limit(scripted_model) -> None:
    model = scripted_model(responses=[_call(i) for i in range(10)], structured=RESULTS)
    events = list(
        agent.run_search(REQUEST, llm=model, tools=[search_builtin_jobs], recursion_limit=4)
    )
    assert any("Step limit" in e.message for e in events if isinstance(e, StatusEvent))
    assert isinstance(events[-1], ResultEvent)


def test_run_search_reports_compile_failure(scripted_model) -> None:
    model = scripted_model(responses=[AIMessage(content="Nothing to do.")], structured=None)
    events = list(agent.run_search(REQUEST, llm=model, tools=[search_builtin_jobs]))
    assert isinstance(events[-1], ErrorEvent)


def test_describe_tool_call() -> None:
    assert (
        agent.describe_tool_call("linkedin_people", {"company": "Ramp", "keywords": "recruiter"})
        == "Looking for recruiter at Ramp"
    )
    assert agent.describe_tool_call("google_search", {"query": "q"}) == "Searching Google for “q”"
    assert (
        agent.describe_tool_call("search_conservation_jobs", {"categories": ["wildlife"]})
        == "Searching Conservation Job Board for “wildlife”"
    )
