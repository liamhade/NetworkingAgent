"""Offline tests for the USAJOBS API client (request building, parsing, errors).

`fixtures/search.json` is built from the documented response shape, not recorded live.
"""

import json
from pathlib import Path
from typing import Any

import pytest
import requests

from usajobs import Agency, JobFilter, UsajobsError, api

FIXTURES = Path(__file__).parent / "fixtures"
KEY = "secret-key-123"
EMAIL = "me@example.com"


def payload() -> dict:
    return json.loads((FIXTURES / "search.json").read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status: int = 200, body: Any = None, bad_json: bool = False) -> None:
        self.status_code = status
        self._body = payload() if body is None else body
        self._bad_json = bad_json

    def json(self) -> Any:
        if self._bad_json:
            raise ValueError("not json")
        return self._body


class FakeSession:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def use(monkeypatch: pytest.MonkeyPatch, response: FakeResponse | Exception) -> FakeSession:
    session = FakeSession(response)
    monkeypatch.setattr(api, "_session", session)
    return session


def test_request_params_and_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    session = use(monkeypatch, FakeResponse())
    job_filter = JobFilter(
        keyword=" wildlife biologist ",
        location="Denver, Colorado",
        radius_miles=50,
        agencies=[Agency.NPS, Agency.USFWS, Agency.NPS],
        days_posted=90,
    )
    api.search_jobs(job_filter, 10, KEY, EMAIL)
    (call,) = session.calls
    assert call["url"] == "https://data.usajobs.gov/api/search"
    assert call["headers"] == {
        "Host": "data.usajobs.gov",
        "User-Agent": EMAIL,
        "Authorization-Key": KEY,
    }
    assert call["params"] == {
        "ResultsPerPage": "10",
        "WhoMayApply": "public",
        "Keyword": "wildlife biologist",
        "LocationName": "Denver, Colorado",
        "Radius": "50",
        "Organization": "IN10;IN15",
        "DatePosted": "60",
    }
    assert KEY not in call["url"]
    assert KEY not in json.dumps(call["params"])


def test_params_minimal_remote_and_page_size_cap() -> None:
    assert api.search_params(JobFilter(), 5000) == {
        "ResultsPerPage": "500",
        "WhoMayApply": "public",
    }
    params = api.search_params(JobFilter(remote=True, radius_miles=10, agencies=[Agency.EPA]), 0)
    assert params["RemoteIndicator"] == "True"
    assert params["Organization"] == "EP00"
    assert params["ResultsPerPage"] == "1"
    assert "Radius" not in params  # a radius needs a location


def test_agency_codes() -> None:
    assert {a.value: a.code for a in Agency} == {
        "nps": "IN10",
        "usfws": "IN15",
        "usfs": "AG11",
        "epa": "EP00",
    }


def test_parses_and_normalizes(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeResponse())
    jobs = api.search_jobs(JobFilter(), 10, KEY, EMAIL)
    # The item without a PositionURI is dropped.
    assert [j.title for j in jobs] == [
        "Wildlife Biologist",
        "Fish and Wildlife Biologist (Pathway Intern)",
        "Forestry Technician",
    ]
    first = jobs[0]
    assert first.url == "https://www.usajobs.gov/job/800000001"
    assert first.apply_url == "https://www.usajobs.gov/job/800000001?PostingChannelID=RESTAPI"
    assert first.agency == "National Park Service"
    assert first.department == "Department of the Interior"
    assert first.location == "Yellowstone National Park, Wyoming"
    assert first.salary == "$64,957 - $84,447 per year"
    assert first.job_type == "Permanent · Full-time"
    assert (first.posted, first.closes) == ("2026-11-03", "2026-11-24")
    assert first.summary and first.summary.startswith("You must have one year")
    assert jobs[1].salary == "$23.50 per hour"  # equal min and max collapse


def test_missing_fields_become_none(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeResponse())
    sparse = api.search_jobs(JobFilter(), 10, KEY, EMAIL)[2]
    assert sparse.agency is None  # blank OrganizationName
    assert sparse.department == "Department of Agriculture"
    assert (sparse.apply_url, sparse.location, sparse.salary, sparse.job_type) == (
        None,
        None,
        None,
        None,
    )
    assert (sparse.posted, sparse.closes, sparse.summary) == (None, None, None)


def test_n_limits_results(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeResponse())
    assert len(api.search_jobs(JobFilter(), 2, KEY, EMAIL)) == 2


@pytest.mark.parametrize(
    "body", [{}, {"SearchResult": None}, {"SearchResult": {"SearchResultItems": None}}]
)
def test_empty_or_odd_bodies_give_no_jobs(monkeypatch: pytest.MonkeyPatch, body: dict) -> None:
    use(monkeypatch, FakeResponse(body=body))
    assert api.search_jobs(JobFilter(), 5, KEY, EMAIL) == []


def test_non_object_body_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, FakeResponse(body=["nope"]))
    with pytest.raises(UsajobsError, match="unexpected"):
        api.search_jobs(JobFilter(), 5, KEY, EMAIL)


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (401, "rejected the API key or email"),
        (403, "rejected the API key or email"),
        (429, "rate limit"),
        (500, "HTTP 500"),
        (503, "HTTP 503"),
    ],
)
def test_http_errors(monkeypatch: pytest.MonkeyPatch, status: int, message: str) -> None:
    use(monkeypatch, FakeResponse(status=status))
    with pytest.raises(UsajobsError, match=message) as info:
        api.search_jobs(JobFilter(), 5, KEY, EMAIL)
    assert KEY not in str(info.value)
    assert EMAIL not in str(info.value)


def test_network_and_json_errors_hide_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    use(monkeypatch, requests.ConnectionError(f"failed with key {KEY}"))
    with pytest.raises(UsajobsError, match="ConnectionError") as info:
        api.search_jobs(JobFilter(), 5, KEY, EMAIL)
    assert KEY not in str(info.value)
    assert info.value.__cause__ is None
    use(monkeypatch, FakeResponse(bad_json=True))
    with pytest.raises(UsajobsError, match="not JSON"):
        api.search_jobs(JobFilter(), 5, KEY, EMAIL)
