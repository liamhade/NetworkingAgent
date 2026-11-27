"""Posting parsers (BuiltIn, Workable) and Greenhouse's per-job fetch, on synthetic pages."""

import json
from typing import Any

import pytest
import requests

from postings import reader_for
from postings.builtin import parse_builtin
from postings.greenhouse import fetch_greenhouse
from postings.workable import parse_workable

URL = "https://example.test/job/1"


def jsonld_page(**overrides: Any) -> str:
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Data Analyst",
        "datePosted": "2026-11-01T09:00:00Z",
        "hiringOrganization": {"@type": "Organization", "name": "Acme Co"},
        "jobLocation": {
            "@type": "Place",
            "address": {"addressLocality": "New York", "addressRegion": "NY"},
        },
        "baseSalary": {
            "currency": "USD",
            "value": {"minValue": 80000, "maxValue": 95000, "unitText": "YEAR"},
        },
        "description": "&lt;p&gt;Analyze data.&lt;/p&gt;&lt;h2&gt;Requirements&lt;/h2&gt;"
        "&lt;ul&gt;&lt;li&gt;3+ years of SQL&lt;/li&gt;&lt;/ul&gt;",
    } | overrides
    return (
        "<html><head><script type='application/ld+json'>"
        f"{json.dumps(posting)}</script></head><body><p>noise</p></body></html>"
    )


def test_builtin_reads_the_json_ld_posting() -> None:
    parsed = parse_builtin(jsonld_page(), "https://builtinnyc.com/job/data-analyst/1")
    assert parsed is not None
    assert parsed.title == "Data Analyst"
    assert parsed.company == "Acme Co"
    assert parsed.location == "New York, NY"
    assert parsed.salary == "USD 80000-95000 per year"
    assert parsed.posted_at == "2026-11-01"
    assert "3+ years of SQL" in parsed.description
    assert "<p>" not in parsed.description
    assert parsed.years_required == "3+ years"


def test_builtin_falls_back_to_the_description_block() -> None:
    page = (
        "<body><nav>menu</nav><div id='job-post-body'><p>Build <b>dashboards</b>.</p></div></body>"
    )
    parsed = parse_builtin(page, URL)
    assert parsed is not None
    assert "dashboards" in parsed.description
    assert "menu" not in parsed.description


def test_builtin_page_without_a_posting_is_none() -> None:
    assert parse_builtin("<body><p>Just a blog.</p></body>", URL) is None


def test_workable_reads_the_json_ld_posting() -> None:
    parsed = parse_workable(
        jsonld_page(jobLocationType="TELECOMMUTE"), "https://apply.workable.com/acme/j/ABC123/"
    )
    assert parsed is not None
    assert parsed.company == "Acme Co"
    assert parsed.location == "New York, NY / Remote"
    assert "3+ years of SQL" in parsed.description


def test_workable_falls_back_to_its_data_ui_sections() -> None:
    page = (
        "<body><section data-ui='job-description'><p>Support customers.</p></section>"
        "<section data-ui='job-requirements'><p>2-4 years in support.</p></section>"
        "<section data-ui='other'>ignore me</section></body>"
    )
    parsed = parse_workable(page, URL)
    assert parsed is not None
    assert "Support customers." in parsed.description
    assert "2-4 years in support." in parsed.description
    assert "ignore me" not in parsed.description
    assert parsed.years_required == "2-4 years"


def test_workable_page_without_a_posting_is_none() -> None:
    assert parse_workable("<body>Loading...</body>", URL) is None


GREENHOUSE_URL = "https://job-boards.greenhouse.io/acme/jobs/4242"
GREENHOUSE_JOB = {
    "id": 4242,
    "title": "Analyst",
    "company_name": "Acme Co",
    "location": {"name": "Remote - US"},
    "first_published": "2026-10-20T10:00:00-04:00",
    "content": "&lt;p&gt;Own reporting.&lt;/p&gt;&lt;p&gt;5+ years experience required.&lt;/p&gt;",
}


def test_greenhouse_fetches_one_job_not_the_whole_board(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[str] = []

    def get_json(url: str, params: dict[str, str] | None = None) -> Any:
        requested.append(url)
        return GREENHOUSE_JOB

    monkeypatch.setattr("postings.greenhouse.get_json", get_json)
    parsed = fetch_greenhouse(GREENHOUSE_URL)
    assert requested == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs/4242"]
    assert parsed is not None
    assert parsed.company == "Acme Co"
    assert parsed.location == "Remote - US"
    assert parsed.posted_at == "2026-10-20"
    assert "Own reporting." in parsed.description
    assert "<p>" not in parsed.description
    assert parsed.years_required == "5+ years"


def test_greenhouse_board_url_is_not_a_posting() -> None:
    assert fetch_greenhouse("https://job-boards.greenhouse.io/acme") is None


def test_greenhouse_http_errors_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    def get_json(url: str, params: dict[str, str] | None = None) -> Any:
        raise requests.HTTPError("404")

    monkeypatch.setattr("postings.greenhouse.get_json", get_json)
    with pytest.raises(requests.HTTPError):
        fetch_greenhouse(GREENHOUSE_URL)


@pytest.mark.parametrize(
    ("url", "source", "text_source"),
    [
        (GREENHOUSE_URL, "greenhouse_api", "api"),
        ("https://www.builtinnyc.com/job/data-analyst/123", "builtin_parser", "parser"),
        ("https://apply.workable.com/acme/j/ABC123/", "workable_parser", "parser"),
    ],
)
def test_reader_for_known_sites(url: str, source: str, text_source: str) -> None:
    found = reader_for(url)
    assert found is not None
    assert found[:2] == (source, text_source)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/careers/1",
        "https://job-boards.greenhouse.io/acme",
        "https://apply.workable.com/acme/",
    ],
)
def test_reader_for_unknown_pages_is_none(url: str) -> None:
    assert reader_for(url) is None
