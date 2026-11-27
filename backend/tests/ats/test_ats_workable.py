"""The Workable provider (`ats.workable`): URL parsing and the widget API, mocked."""

import json
from pathlib import Path
from typing import Any

import pytest
import requests

from ats import PROVIDERS, BoardRef, get_provider, parse_url
from ats import base as ats_base
from ats.workable import WORKABLE, Workable

FIXTURES = Path(__file__).parent / "fixtures"
BOARD = json.loads((FIXTURES / "workable_widget.json").read_text(encoding="utf-8"))
API = "https://apply.workable.com/api/v1/widget/accounts"
HF = "https://apply.workable.com/huggingface"


class FakeApi:
    """Serves `responses[url]` (an Exception is raised); records requested URLs + params."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.responses: dict[str, Any] = {}
        self.requested: list[tuple[str, dict[str, str] | None]] = []
        monkeypatch.setattr(ats_base, "get_json", self.get_json)
        monkeypatch.setattr("ats.workable.get_json", self.get_json)

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
        (HF, "huggingface", None),
        (f"{HF}/", "huggingface", None),
        (f"{HF}/?lng=en", "huggingface", None),
        (f"{HF}/j/81B46579FE/", "huggingface", "81B46579FE"),
        (f"{HF}/j/81B46579FE", "huggingface", "81B46579FE"),
        (f"{HF}/j/81B46579FE/apply", "huggingface", "81B46579FE"),
        (f"{HF}/j/81B46579FE/apply/?x=1#a", "huggingface", "81B46579FE"),
        (f"{HF}/j/81b46579fe/?utm_source=x", "huggingface", "81B46579FE"),
        ("http://APPLY.WORKABLE.COM/Acme-Corp/j/0A1B2C3D4E", "Acme-Corp", "0A1B2C3D4E"),
        ("https://apply.workable.com/acme/j", "acme", None),
        ("  https://apply.workable.com/acme/j/ABC123/  ", "acme", "ABC123"),
        # Legacy subdomain forms.
        ("https://acme.workable.com", "acme", None),
        ("https://acme.workable.com/", "acme", None),
        ("https://acme.workable.com/jobs/123456", "acme", "123456"),
        ("https://acme.workable.com/jobs/1A2B3C?x=1", "acme", "1A2B3C"),
        ("https://acme.workable.com/jobs", "acme", None),
    ],
)
def test_parse_url(url: str, slug: str, job_id: str | None) -> None:
    assert WORKABLE.parse_url(url) == BoardRef(provider="workable", slug=slug, job_id=job_id)


@pytest.mark.parametrize(
    "url",
    [
        "https://apply.workable.com/",
        "https://apply.workable.com",
        "https://apply.workable.com/j/81B46579FE",  # the API's own link: no account
        "https://apply.workable.com/api/v1/widget/accounts/acme",
        "https://apply.workable.com/api/v3/accounts/acme/jobs",
        "https://www.workable.com/",
        "https://www.workable.com/jobs/data-analyst",
        "https://workable.com/acme",
        "https://resources.workable.com/job-descriptions/data-analyst",
        "https://help.workable.com/hc/en-us",
        "https://apply.workable.com.evil.example/acme",
        "https://notworkable.com/acme",
        "https://jobs.lever.co/spotify",
        "https://job-boards.greenhouse.io/discord/jobs/1",
        "https://www.google.com/goto?url=abc",
        "",
    ],
)
def test_parse_url_rejects_other_urls(url: str) -> None:
    assert WORKABLE.parse_url(url) is None


def test_board_url() -> None:
    assert WORKABLE.board_url("huggingface") == "https://apply.workable.com/huggingface/"


def test_registry_order_and_lookup() -> None:
    assert list(PROVIDERS) == ["greenhouse", "lever", "ashby", "workable"]
    assert get_provider("workable") is WORKABLE
    assert parse_url("https://apply.workable.com/x/j/ABC/apply") == BoardRef(
        provider="workable", slug="x", job_id="ABC"
    )


# --- the widget API ------------------------------------------------------------------


def test_list_jobs_normalizes_the_api_response(api: FakeApi) -> None:
    api.responses[f"{API}/huggingface"] = BOARD
    jobs = Workable().list_jobs("huggingface")
    assert api.requested == [(f"{API}/huggingface", None)]  # one request, no pagination
    assert len(jobs) == 6
    assert jobs[0].model_dump() == {
        "provider": "workable",
        "board": "huggingface",
        "id": "81B46579FE",
        "title": "Open-Source Machine Learning Engineer - EMEA Remote",
        "url": "https://apply.workable.com/j/81B46579FE",
        "company": "Hugging Face",  # the API's name, not the slug
        "location": "Paris, Île-de-France, France (Remote)",
        "departments": ["Open Source", "Engineering"],
        "posted": "2026-05-29",
        "years_required": "",
    }
    # A region equal to the city is not repeated.
    assert jobs[1].location == "New York, United States (Remote)"
    # Hidden locations without a city still name the country.
    assert jobs[3].location == "France (Remote)"


def test_missing_fields_are_filled_or_skipped(api: FakeApi) -> None:
    api.responses[f"{API}/acme"] = {
        "name": None,
        "jobs": [
            {"shortcode": "a1b2", "title": "  Data Analyst ", "city": "Boston", "state": "MA"},
            {"shortcode": "A2", "title": ""},  # no title
            {"title": "No shortcode"},
            "not a dict",
            {
                "shortcode": "A4",
                "title": "Analytics Engineer",
                "telecommuting": True,
                "department": "Data",
                "function": "Data",
                "published_on": "yesterday",
                "created_at": "2026-10-26",
                "url": "https://apply.workable.com/j/A4",
            },
            {
                "shortcode": "A5",
                "title": "Data Lead",
                "telecommuting": True,
                "locations": [
                    {"city": "NYC", "region": "NY", "country": "United States"},
                    {"city": "", "country": "Canada", "hidden": True},
                    "bad",
                ],
            },
        ],
    }
    jobs = Workable().list_jobs("acme")
    assert [(j.id, j.title, j.company, j.location, j.posted) for j in jobs] == [
        ("A1B2", "Data Analyst", "acme", "Boston, MA", None),
        ("A4", "Analytics Engineer", "acme", "Remote", "2026-10-26"),
        ("A5", "Data Lead", "acme", "NYC, NY, United States / Canada (Remote)", None),
    ]
    assert jobs[0].url == "https://apply.workable.com/acme/j/a1b2/"  # built when url is missing
    assert jobs[0].departments == []
    assert jobs[1].departments == ["Data"]  # department == function: listed once


@pytest.mark.parametrize("payload", [{"name": "Acme", "jobs": []}, {"jobs": None}, {}, [], "oops"])
def test_empty_or_unexpected_board_is_empty(api: FakeApi, payload: Any) -> None:
    api.responses[f"{API}/acme"] = payload
    assert Workable().list_jobs("acme") == []


def test_unknown_board_raises(api: FakeApi) -> None:
    api.responses[f"{API}/nope"] = http_error(404)
    with pytest.raises(requests.HTTPError, match="404"):
        Workable().list_jobs("nope")
