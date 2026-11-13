"""The Greenhouse provider (`ats.greenhouse`): URL parsing and the board API, mocked."""

import json
from pathlib import Path
from typing import Any

import pytest
import requests

from ats import BoardRef, get_provider, parse_url
from ats import base as ats_base
from ats.greenhouse import GREENHOUSE

FIXTURES = Path(__file__).parent / "fixtures"
BOARD_JOBS = json.loads((FIXTURES / "greenhouse_board_jobs.json").read_text(encoding="utf-8"))
API = "https://boards-api.greenhouse.io/v1/boards"


class FakeApi:
    """Serves `responses[url]` (an Exception is raised); records requested URLs."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.responses: dict[str, Any] = {}
        self.requested: list[str] = []
        monkeypatch.setattr(ats_base, "get_json", self.get_json)
        monkeypatch.setattr("ats.greenhouse.get_json", self.get_json)

    def get_json(self, url: str, params: dict[str, str] | None = None) -> Any:
        self.requested.append(url)
        if url not in self.responses:
            raise AssertionError(f"unexpected request: {url}")
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> FakeApi:
    return FakeApi(monkeypatch)


def not_found() -> requests.HTTPError:
    response = requests.Response()
    response.status_code = 404
    return requests.HTTPError("404 Client Error", response=response)


# --- URL parsing ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "slug", "job_id"),
    [
        ("https://job-boards.greenhouse.io/discord", "discord", None),
        ("https://job-boards.greenhouse.io/discord/jobs/8917177002", "discord", "8917177002"),
        ("https://boards.greenhouse.io/datadog/jobs/8257324?gh_src=abc", "datadog", "8257324"),
        ("https://boards.greenhouse.io/datadog/", "datadog", None),
        ("http://BOARDS.greenhouse.io/Acme/jobs/1", "Acme", "1"),
        ("https://job-boards.eu.greenhouse.io/euroltd/jobs/4400123", "euroltd", "4400123"),
        ("https://boards.eu.greenhouse.io/euroltd", "euroltd", None),
        ("https://boards.greenhouse.io/embed/job_app?for=widgetco&token=555", "widgetco", "555"),
        ("https://boards.greenhouse.io/embed/job_board?for=widgetco", "widgetco", None),
        ("https://job-boards.greenhouse.io/acme/jobs/not-a-number", "acme", None),
        ("  https://job-boards.greenhouse.io/acme  ", "acme", None),
    ],
)
def test_parse_url(url: str, slug: str, job_id: str | None) -> None:
    assert GREENHOUSE.parse_url(url) == BoardRef(provider="greenhouse", slug=slug, job_id=job_id)


@pytest.mark.parametrize(
    "url",
    [
        "https://job-boards.greenhouse.io/",
        "https://boards.greenhouse.io/embed/job_app?token=555",
        "https://boards.greenhouse.io/embed/job_app?for=../x&token=555",
        "https://www.greenhouse.io/careers",
        "https://boards-api.greenhouse.io/v1/boards/discord/jobs",
        "https://careers.example.com/jobs?gh_jid=123",
        "https://jobs.lever.co/acme/1b2c",
        "https://www.google.com/goto?url=abc",
        "",
    ],
)
def test_parse_url_rejects_other_urls(url: str) -> None:
    assert GREENHOUSE.parse_url(url) is None


def test_registry() -> None:
    assert get_provider("greenhouse") is GREENHOUSE
    assert parse_url("https://job-boards.greenhouse.io/x/jobs/1") == BoardRef(
        provider="greenhouse", slug="x", job_id="1"
    )
    assert parse_url("https://example.com/jobs/1") is None
    with pytest.raises(KeyError, match="Unknown ATS provider"):
        get_provider("taleo")


# --- the board API -------------------------------------------------------------------


def test_list_jobs_normalizes_the_api_response(api: FakeApi) -> None:
    api.responses[f"{API}/discord/jobs"] = BOARD_JOBS
    jobs = GREENHOUSE.list_jobs("discord")
    assert api.requested == [f"{API}/discord/jobs"]  # no ?content=true, no board-info call
    assert len(jobs) == 8
    first = jobs[0]
    assert first.model_dump() == {
        "provider": "greenhouse",
        "board": "discord",
        "id": "8917177002",
        "title": "Associate Commercial Counsel",
        "url": "https://job-boards.greenhouse.io/discord/jobs/8917177002",
        "company": "Discord",
        "location": "San Francisco Bay Area or Remote (U.S.)",
        "departments": [],
        "posted": "2026-11-03",
    }


def test_list_jobs_skips_broken_entries_and_fills_gaps(api: FakeApi) -> None:
    api.responses[f"{API}/acme/jobs"] = {
        "jobs": [
            {"id": 1, "title": "  Data Analyst ", "location": {"name": "New York, NY"}},
            {"id": 2, "title": ""},  # no title
            {"title": "No id"},
            "not a dict",
            {
                "id": 3,
                "title": "Analytics Engineer",
                "location": None,
                "updated_at": "2026-10-01T10:00:00-04:00",
                "departments": [{"name": "Data"}, {"id": 9}],
            },
        ]
    }
    api.responses[f"{API}/acme"] = {"name": "Acme Corp", "content": "<p>About</p>"}
    jobs = GREENHOUSE.list_jobs("acme")
    assert [(j.id, j.title, j.company, j.location) for j in jobs] == [
        ("1", "Data Analyst", "Acme Corp", "New York, NY"),
        ("3", "Analytics Engineer", "Acme Corp", ""),
    ]
    assert jobs[0].url == "https://job-boards.greenhouse.io/acme/jobs/1"  # built when missing
    assert jobs[1].departments == ["Data"]
    assert jobs[1].posted == "2026-10-01"


def test_board_name_falls_back_to_the_slug(api: FakeApi) -> None:
    api.responses[f"{API}/acme/jobs"] = {"jobs": [{"id": 1, "title": "Analyst"}]}
    api.responses[f"{API}/acme"] = RuntimeError("down")
    assert GREENHOUSE.list_jobs("acme")[0].company == "acme"


def test_empty_board(api: FakeApi) -> None:
    api.responses[f"{API}/acme/jobs"] = {"jobs": [], "meta": {"total": 0}}
    assert GREENHOUSE.list_jobs("acme") == []


def test_unknown_board_raises(api: FakeApi) -> None:
    api.responses[f"{API}/nope/jobs"] = not_found()
    with pytest.raises(requests.HTTPError):
        GREENHOUSE.list_jobs("nope")
