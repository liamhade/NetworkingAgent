"""The Ashby provider (`ats.ashby`): URL parsing and the job-board API, mocked."""

import json
from pathlib import Path
from typing import Any

import pytest
import requests

from ats import PROVIDERS, BoardRef, get_provider, parse_url
from ats import base as ats_base
from ats.ashby import ASHBY, Ashby

FIXTURES = Path(__file__).parent / "fixtures"
BOARD = json.loads((FIXTURES / "ashby_job_board.json").read_text(encoding="utf-8"))
API = "https://api.ashbyhq.com/posting-api/job-board"
UUID = "34413f8d-26bf-4bbc-8ade-eb309a0e2245"


class FakeApi:
    """Serves `responses[url]` (an Exception is raised); records requested URLs + params."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.responses: dict[str, Any] = {}
        self.requested: list[tuple[str, dict[str, str] | None]] = []
        monkeypatch.setattr(ats_base, "get_json", self.get_json)
        monkeypatch.setattr("ats.ashby.get_json", self.get_json)

    def get_json(self, url: str, params: dict[str, str] | None = None) -> Any:
        self.requested.append((url, params))
        if url not in self.responses:
            raise AssertionError(f"unexpected request: {url}")
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> FakeApi:
    return FakeApi(monkeypatch)


def http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} Client Error", response=response)


# --- URL parsing ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "slug", "job_id"),
    [
        ("https://jobs.ashbyhq.com/ramp", "ramp", None),
        ("https://jobs.ashbyhq.com/ramp/", "ramp", None),
        (f"https://jobs.ashbyhq.com/ramp/{UUID}", "ramp", UUID),
        (f"https://jobs.ashbyhq.com/ramp/{UUID}/application", "ramp", UUID),
        (f"https://jobs.ashbyhq.com/ramp/{UUID}?utm_source=abc", "ramp", UUID),
        (f"https://jobs.ashbyhq.com/ramp/{UUID}/application?src=x#top", "ramp", UUID),
        ("https://jobs.ashbyhq.com/ramp?departmentId=1234", "ramp", None),
        (f"http://JOBS.ASHBYHQ.COM/Acme-Labs/{UUID}", "Acme-Labs", UUID),
        ("https://jobs.ashbyhq.com/ramp/not-a-uuid", "ramp", None),
        ("https://jobs.ashbyhq.com/ramp/embed", "ramp", None),
        (f"  https://jobs.ashbyhq.com/ramp/{UUID}  ", "ramp", UUID),
    ],
)
def test_parse_url(url: str, slug: str, job_id: str | None) -> None:
    assert ASHBY.parse_url(url) == BoardRef(provider="ashby", slug=slug, job_id=job_id)


@pytest.mark.parametrize(
    "url",
    [
        "https://jobs.ashbyhq.com/",
        "https://jobs.ashbyhq.com",
        "https://www.ashbyhq.com/careers",
        "https://ashbyhq.com/ramp",
        f"https://api.ashbyhq.com/posting-api/job-board/ramp/{UUID}",
        "https://jobs.ashbyhq.com.evil.example/ramp",
        "https://jobs.lever.co/spotify",
        "https://job-boards.greenhouse.io/discord/jobs/1",
        "https://www.google.com/goto?url=abc",
        "",
    ],
)
def test_parse_url_rejects_other_urls(url: str) -> None:
    assert ASHBY.parse_url(url) is None


def test_board_url() -> None:
    assert ASHBY.board_url("ramp") == "https://jobs.ashbyhq.com/ramp"


def test_registry_order_and_lookup() -> None:
    assert list(PROVIDERS) == ["greenhouse", "lever", "ashby", "workable"]
    assert get_provider("ashby") is ASHBY
    assert parse_url(f"https://jobs.ashbyhq.com/x/{UUID}/application") == BoardRef(
        provider="ashby", slug="x", job_id=UUID
    )
    assert parse_url(f"https://jobs.lever.co/x/{UUID}") == BoardRef(
        provider="lever", slug="x", job_id=UUID
    )


# --- the job-board API ---------------------------------------------------------------


def test_list_jobs_normalizes_the_api_response(api: FakeApi) -> None:
    api.responses[f"{API}/ramp"] = BOARD
    jobs = Ashby().list_jobs("ramp")
    # No compensation: AtsJob has no pay field and it only makes the payload bigger.
    assert api.requested == [(f"{API}/ramp", None)]
    assert len(jobs) == 5
    assert jobs[0].model_dump() == {
        "provider": "ashby",
        "board": "ramp",
        "id": UUID,
        "title": "Software Engineer, Security, Cloud",  # the API's leading space is dropped
        "url": f"https://jobs.ashbyhq.com/ramp/{UUID}",
        "company": "Ramp",
        "location": "New York, NY (HQ) / Remote (Canada) / Remote (US) / Miami, FL",
        "departments": ["Engineering", "Backend"],
        "posted": "2026-04-07",
        "years_required": "",
    }
    by_title = {j.title: j for j in jobs}
    # isRemote is true for most hybrid postings; only workplaceType "Remote" adds the tag.
    assert by_title["Account Executive | Strategic"].location == "San Francisco, CA"
    assert by_title["Product Manager | Growth"].location == "New York, NY (HQ) / San Francisco, CA"
    assert by_title["Partner Consultant, Accounting"].location.startswith("Remote (US)")


def test_missing_fields_are_filled_or_skipped(api: FakeApi) -> None:
    api.responses[f"{API}/acme"] = {
        "jobs": [
            {"id": "a1", "title": "  Data Analyst ", "location": "Boston, MA"},
            {"id": "a2", "title": ""},  # no title
            {"title": "No id"},
            "not a dict",
            {"id": "a3", "title": "Hidden", "isListed": False},
            {
                "id": "a4",
                "title": "Analytics Engineer",
                "workplaceType": "Remote",
                "department": "Data",
                "team": "Data",
                "publishedAt": "yesterday",
                "jobUrl": "https://jobs.ashbyhq.com/acme/a4",
            },
            {
                "id": "a5",
                "title": "Data Lead",
                "location": "NYC",
                "secondaryLocations": [{"location": ""}, {"location": "Remote"}, "Austin, TX", 3],
                "workplaceType": "Remote",
                "publishedAt": "2026-10-26T01:02:03Z",
            },
        ]
    }
    jobs = Ashby().list_jobs("acme")
    assert [(j.id, j.title, j.company, j.location, j.posted) for j in jobs] == [
        ("a1", "Data Analyst", "Acme", "Boston, MA", None),
        ("a4", "Analytics Engineer", "Acme", "Remote", None),
        ("a5", "Data Lead", "Acme", "NYC / Remote / Austin, TX", "2026-10-26"),
    ]
    assert jobs[0].url == "https://jobs.ashbyhq.com/acme/a1"  # built when jobUrl is missing
    assert jobs[0].departments == []
    assert jobs[1].departments == ["Data"]  # department == team: listed once


@pytest.mark.parametrize("payload", [{"jobs": []}, {"jobs": None}, {}, [], "oops"])
def test_empty_or_unexpected_board_is_empty(api: FakeApi, payload: Any) -> None:
    api.responses[f"{API}/acme"] = payload
    assert Ashby().list_jobs("acme") == []


def test_unknown_board_raises(api: FakeApi) -> None:
    api.responses[f"{API}/nope"] = http_error(404)
    with pytest.raises(requests.HTTPError, match="404"):
        Ashby().list_jobs("nope")
