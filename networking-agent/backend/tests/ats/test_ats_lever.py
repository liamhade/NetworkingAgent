"""The Lever provider (`ats.lever`): URL parsing and the Postings API, mocked."""

import json
from pathlib import Path
from typing import Any

import pytest
import requests

from ats import PROVIDERS, BoardRef, get_provider, parse_url
from ats import base as ats_base
from ats.lever import LEVER, Lever, company_name

FIXTURES = Path(__file__).parent / "fixtures"
POSTINGS = json.loads((FIXTURES / "lever_postings.json").read_text(encoding="utf-8"))
API = "https://api.lever.co/v0/postings"
EU_API = "https://api.eu.lever.co/v0/postings"
UUID = "2a55d6c9-c564-443a-be3e-a3851db5a93b"


class FakeApi:
    """Serves `responses[url]` (an Exception is raised); records requested URLs + params."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.responses: dict[str, Any] = {}
        self.requested: list[tuple[str, dict[str, str] | None]] = []
        monkeypatch.setattr(ats_base, "get_json", self.get_json)
        monkeypatch.setattr("ats.lever.get_json", self.get_json)

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


@pytest.fixture
def lever() -> Lever:
    """A fresh provider, so EU boards remembered by one test don't leak into another."""
    return Lever()


def http_error(status: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} Client Error", response=response)


# --- URL parsing ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "slug", "job_id"),
    [
        ("https://jobs.lever.co/spotify", "spotify", None),
        ("https://jobs.lever.co/spotify/", "spotify", None),
        (f"https://jobs.lever.co/spotify/{UUID}", "spotify", UUID),
        (f"https://jobs.lever.co/spotify/{UUID}/apply", "spotify", UUID),
        (f"https://jobs.lever.co/spotify/{UUID}?lever-source=LinkedIn", "spotify", UUID),
        ("https://jobs.lever.co/spotify?team=Engineering&location=London", "spotify", None),
        (f"http://JOBS.LEVER.CO/Acme-Labs/{UUID}", "Acme-Labs", UUID),
        (f"https://jobs.eu.lever.co/euroco/{UUID}/apply", "euroco", UUID),
        ("https://jobs.eu.lever.co/euroco", "euroco", None),
        ("https://jobs.lever.co/spotify/not-a-uuid", "spotify", None),
        (f"  https://jobs.lever.co/spotify/{UUID}  ", "spotify", UUID),
    ],
)
def test_parse_url(url: str, slug: str, job_id: str | None) -> None:
    assert LEVER.parse_url(url) == BoardRef(provider="lever", slug=slug, job_id=job_id)


@pytest.mark.parametrize(
    "url",
    [
        "https://jobs.lever.co/",
        "https://jobs.lever.co",
        "https://www.lever.co/careers",
        "https://lever.co/spotify",
        f"https://api.lever.co/v0/postings/spotify/{UUID}",
        "https://job-boards.greenhouse.io/discord/jobs/1",
        "https://www.google.com/goto?url=abc",
        "https://jobs.lever.co.evil.example/spotify",
        "",
    ],
)
def test_parse_url_rejects_other_urls(url: str) -> None:
    assert LEVER.parse_url(url) is None


def test_api_base_follows_the_board_host() -> None:
    assert LEVER.api_base(f"https://jobs.lever.co/a/{UUID}") == API
    assert LEVER.api_base(f"https://jobs.eu.lever.co/a/{UUID}") == EU_API


def test_registry() -> None:
    assert list(PROVIDERS) == ["greenhouse", "lever", "ashby"]
    assert get_provider("lever") is LEVER
    assert parse_url(f"https://jobs.lever.co/x/{UUID}/apply") == BoardRef(
        provider="lever", slug="x", job_id=UUID
    )
    assert parse_url("https://job-boards.greenhouse.io/x/jobs/1") == BoardRef(
        provider="greenhouse", slug="x", job_id="1"
    )


@pytest.mark.parametrize(
    ("slug", "name"),
    [("spotify", "Spotify"), ("acme-labs", "Acme Labs"), ("palantirTech", "PalantirTech")],
)
def test_company_name(slug: str, name: str) -> None:
    assert company_name(slug) == name


# --- the Postings API ----------------------------------------------------------------


def test_list_jobs_normalizes_the_api_response(api: FakeApi, lever: Lever) -> None:
    api.responses[f"{API}/spotify"] = POSTINGS
    jobs = lever.list_jobs("spotify")
    assert api.requested == [(f"{API}/spotify", {"mode": "json"})]
    assert len(jobs) == 8
    assert jobs[0].model_dump() == {
        "provider": "lever",
        "board": "spotify",
        "id": UUID,
        "title": "Account Executive - Commercial, Spotify Technology",
        "url": f"https://jobs.lever.co/spotify/{UUID}",
        "company": "Spotify",
        "location": "New York, NY",
        "departments": ["Operations and Business Support", "Platform"],
        "posted": "2026-10-23",
    }
    by_title = {j.title: j for j in jobs}
    # Every location is kept, so a London search matches a Stockholm-first posting.
    assert by_title["Backend Engineer - Data Platform"].location == "Stockholm / London"
    # Remote postings say so, so a "remote" search matches them.
    assert by_title["Full Stack Engineer - Music"].location == "New York, NY (Remote)"
    assert by_title["Tax Analyst"].departments == ["Finance", "Accounting"]
    assert lever.board_url("spotify") == "https://jobs.lever.co/spotify"


def test_list_jobs_skips_broken_entries_and_fills_gaps(api: FakeApi, lever: Lever) -> None:
    api.responses[f"{API}/acme"] = [
        {"id": "a1", "text": "  Data Analyst ", "categories": {"location": "Boston, MA"}},
        {"id": "a2", "text": ""},  # no title
        {"text": "No id"},
        "not a dict",
        {
            "id": "a3",
            "text": "Analytics Engineer",
            "categories": None,
            "workplaceType": "remote",
            "createdAt": "yesterday",
        },
        {
            "id": "a4",
            "text": "Data Lead",
            "categories": {"team": "Data", "department": "Data", "allLocations": ["", "NYC"]},
            "createdAt": 1793000000000,
        },
    ]
    jobs = lever.list_jobs("acme")
    assert [(j.id, j.title, j.company, j.location, j.posted) for j in jobs] == [
        ("a1", "Data Analyst", "Acme", "Boston, MA", None),
        ("a3", "Analytics Engineer", "Acme", "Remote", None),
        ("a4", "Data Lead", "Acme", "NYC", "2026-10-26"),
    ]
    assert jobs[0].url == "https://jobs.lever.co/acme/a1"  # built when hostedUrl is missing
    assert jobs[0].departments == []
    assert jobs[2].departments == ["Data"]  # department == team: listed once


def test_empty_board(api: FakeApi, lever: Lever) -> None:
    api.responses[f"{API}/acme"] = []
    assert lever.list_jobs("acme") == []


def test_unexpected_shape_is_an_empty_board(api: FakeApi, lever: Lever) -> None:
    api.responses[f"{API}/acme"] = {"ok": True}
    assert lever.list_jobs("acme") == []


def test_eu_board_is_read_from_the_eu_api(api: FakeApi, lever: Lever) -> None:
    api.responses[f"{API}/euroco"] = http_error(404)
    api.responses[f"{EU_API}/euroco"] = [
        {
            "id": "e1",
            "text": "Data Analyst",
            "hostedUrl": "https://jobs.eu.lever.co/euroco/e1",
            "categories": {"location": "Berlin"},
        }
    ]
    jobs = lever.list_jobs("euroco")
    assert [url for url, _ in api.requested] == [f"{API}/euroco", f"{EU_API}/euroco"]
    assert jobs[0].url == "https://jobs.eu.lever.co/euroco/e1"
    assert lever.board_url("EuroCo") == "https://jobs.eu.lever.co/EuroCo"


def test_unknown_board_raises(api: FakeApi, lever: Lever) -> None:
    api.responses[f"{API}/nope"] = http_error(404)
    api.responses[f"{EU_API}/nope"] = http_error(404)
    with pytest.raises(requests.HTTPError):
        lever.list_jobs("nope")
    assert lever.board_url("nope") == "https://jobs.lever.co/nope"


def test_other_http_errors_do_not_fall_back_to_the_eu_api(api: FakeApi, lever: Lever) -> None:
    api.responses[f"{API}/acme"] = http_error(429)
    with pytest.raises(requests.HTTPError, match="429"):
        lever.list_jobs("acme")
    assert [url for url, _ in api.requested] == [f"{API}/acme"]
