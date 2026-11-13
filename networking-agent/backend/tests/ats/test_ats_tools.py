"""`tools.ats_boards` / `tools.ats_jobs` with a mocked Google worker and board API."""

import json
from pathlib import Path
from typing import Any

import pytest

import config
import tools
from ats import base as ats_base
from google_serp import SearchResponse, SearchResult

FIXTURES = Path(__file__).parent / "fixtures"
API = "https://boards-api.greenhouse.io/v1/boards"
QUERY = 'site:job-boards.greenhouse.io OR site:boards.greenhouse.io "data analyst" "New York"'
RESOLVED = {
    "https://www.google.com/goto?url=AAA4": (
        "https://boards.greenhouse.io/embed/job_app?for=widgetco&token=555"
    ),
    "https://www.google.com/goto?url=AAA7": "https://job-boards.greenhouse.io/gamma",
}


class FakeGoogle:
    """Stands in for `tools.run_google_search`: calls `pick`, then "resolves" the picked
    results in place, like the shared worker does."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        raw = json.loads((FIXTURES / "google_results.json").read_text(encoding="utf-8"))
        self.results = [SearchResult(**r) for r in raw]
        self.error: Exception | None = None
        self.queries: list[str] = []
        self.resolved: list[str] = []
        self.cacheable: bool | None = None
        monkeypatch.setattr(tools, "run_google_search", self.search)

    def search(self, query: str, pick=None, cacheable=None) -> SearchResponse:
        self.queries.append(query)
        if self.error is not None:
            raise self.error
        page = SearchResponse(results=self.results, query=query)
        self.cacheable = cacheable(page) if cacheable else None
        picked = pick(list(self.results)) if pick else list(self.results)
        for r in picked:
            self.resolved.append(r.url)
            r.url = RESOLVED.get(r.url, "https://elsewhere.example/")
        return SearchResponse(results=picked, query=query)


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> FakeGoogle:
    return FakeGoogle(monkeypatch)


@pytest.fixture
def board_api(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    responses: dict[str, Any] = {}

    def get_json(url: str, params: dict[str, str] | None = None) -> Any:
        value = responses[url]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(ats_base, "get_json", get_json)
    monkeypatch.setattr("ats.greenhouse.get_json", get_json)
    return responses


def test_ats_boards_reads_breadcrumbs_and_resolves_only_hidden_boards(
    google: FakeGoogle, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "ATS_RESOLVE_LINKS", 3)
    boards = tools.ats_boards("greenhouse", "data analyst", "New York, NY")
    assert google.queries == [QUERY]
    assert google.resolved == list(RESOLVED)  # not the 4 boards readable from breadcrumbs
    assert google.cacheable is True
    assert boards == [
        {"provider": "greenhouse", "slug": "discord", "job_ids": ["8865033002", "8691572002"]},
        {"provider": "greenhouse", "slug": "acmecorp", "job_ids": []},
        {"provider": "greenhouse", "slug": "widgetco", "job_ids": ["555"]},
        {"provider": "greenhouse", "slug": "euroltd", "job_ids": ["4400123"]},
        {"provider": "greenhouse", "slug": "gamma", "job_ids": []},
    ]


def test_ats_boards_resolve_cap(google: FakeGoogle, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "ATS_RESOLVE_LINKS", 0)
    boards = tools.ats_boards("greenhouse", "data analyst", "New York, NY")
    assert google.resolved == []
    assert [b["slug"] for b in boards] == ["discord", "acmecorp", "euroltd"]


def test_ats_boards_page_without_boards_is_not_cached(google: FakeGoogle) -> None:
    google.results = [r for r in google.results if "indeed" in r.display_url]
    assert tools.ats_boards("greenhouse", "data analyst") == []
    assert google.cacheable is False
    assert google.resolved == []


def test_ats_boards_errors_are_raised(google: FakeGoogle) -> None:
    google.error = RuntimeError("Chrome not found")
    with pytest.raises(RuntimeError, match="Chrome not found"):
        tools.ats_boards("greenhouse", "data analyst")
    with pytest.raises(KeyError):
        tools.ats_boards("taleo", "data analyst")


def test_ats_jobs_returns_matching_postings(board_api: dict[str, Any]) -> None:
    board_api[f"{API}/discord/jobs"] = json.loads(
        (FIXTURES / "greenhouse_board_jobs.json").read_text(encoding="utf-8")
    )
    out = tools.ats_jobs(
        "greenhouse", "discord", "data engineer", "San Francisco", job_ids=["8865033002"], n=2
    )
    assert out == [
        {
            "title": "Strategic Finance Analyst",  # Google pointed at it
            "url": "https://job-boards.greenhouse.io/discord/jobs/8865033002",
            "company": "Discord",
            "company_url": "https://job-boards.greenhouse.io/discord",
            "location": "San Francisco Bay Area",
            "summary": "Greenhouse · posted 2026-11-10",
        },
        {
            "title": "Staff Data Engineer",
            "url": "https://job-boards.greenhouse.io/discord/jobs/8691572002",
            "company": "Discord",
            "company_url": "https://job-boards.greenhouse.io/discord",
            "location": "San Francisco Bay Area",
            "summary": "Greenhouse · posted 2026-08-10",
        },
    ]
    remote = tools.ats_jobs("greenhouse", "discord", "data engineer", "remote")
    assert [j["title"] for j in remote] == ["Senior Data Engineer, Ads"]


def test_ats_jobs_errors_are_raised(board_api: dict[str, Any]) -> None:
    board_api[f"{API}/nope/jobs"] = RuntimeError("404 Client Error")
    with pytest.raises(RuntimeError, match="404"):
        tools.ats_jobs("greenhouse", "nope", "data analyst")
