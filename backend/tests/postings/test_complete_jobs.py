"""`complete_jobs`: Job -> JobPosting, text_source values, the read cap and the fallbacks."""

import re
import time
from typing import Any

import pytest
import requests

import config
import tools
from pipeline import steps
from pipeline.state import Job, JobPosting
from postings import ParsedPosting
from read_page import fetch as fetch_mod
from read_page import methods
from read_page.models import PageResult

BUILTIN_URL = "https://www.builtinnyc.com/job/data-analyst/{n}"
GREENHOUSE_URL = "https://job-boards.greenhouse.io/acme/jobs/{n}"
PAGE_URL = "https://careers.example.test/jobs/{n}"

BUILTIN_HTML = (
    "<script type='application/ld+json'>"
    '{"@type": "JobPosting", "title": "Data Analyst", '
    '"hiringOrganization": {"name": "Acme Co"}, '
    '"description": "&lt;p&gt;Analyze data.&lt;/p&gt;&lt;p&gt;2+ years of SQL.&lt;/p&gt;"}'
    "</script>"
)


def job(url: str, n: int = 1, **fields: Any) -> Job:
    return Job(
        id=f"j{n}",
        source="test",
        title=f"Role {n}",
        url=url.format(n=n),
        summary="card text",
        **fields,
    )


def fake_page(url: str, max_chars: int = 12_000) -> PageResult:
    return PageResult(
        url=url, final_url=url, method="static", markdown="Plain page.\n\n4+ years of Go."
    )


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("unexpected network read")

    monkeypatch.setattr(tools, "read_page", refuse)
    monkeypatch.setattr(fetch_mod, "fetch", refuse)
    monkeypatch.setattr("postings.greenhouse.get_json", refuse)


def test_api_text_is_used_without_a_read() -> None:
    api_job = job(
        PAGE_URL, description="USAJOBS text.\n\nRequirements\n3+ years.", posted_at="2026-11-02"
    )
    [posting], trace = steps.complete_jobs([api_job], max_reads=5)
    assert isinstance(posting, JobPosting)
    assert posting.text_source == "api"
    assert posting.description.startswith("USAJOBS text.")
    assert posting.posted_at == "2026-11-02"
    assert posting.years_required == "3+ years"
    assert [t.source for t in trace] == ["complete"]


def test_greenhouse_uses_the_per_job_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[str] = []

    def get_json(url: str, params: dict[str, str] | None = None) -> Any:
        requested.append(url)
        return {"title": "Analyst", "content": "&lt;p&gt;5+ years of SQL.&lt;/p&gt;"}

    monkeypatch.setattr("postings.greenhouse.get_json", get_json)
    [posting], trace = steps.complete_jobs([job(GREENHOUSE_URL, 7)], max_reads=5)
    assert requested == ["https://boards-api.greenhouse.io/v1/boards/acme/jobs/7"]
    assert (posting.text_source, posting.years_required) == ("api", "5+ years")
    assert trace[0].source == "greenhouse_api"
    assert trace[0].count == len(posting.description)


def test_lever_and_ashby_use_their_posting_api(monkeypatch: pytest.MonkeyPatch) -> None:
    read: list[str] = []

    def lever(url: str) -> PageResult:
        read.append(url)
        return fake_page(url)

    monkeypatch.setitem(methods.READERS, "lever_api", lever)
    monkeypatch.setitem(methods.READERS, "ashby_api", lever)
    uuid = "186b763a-2a61-4563-8813-ff6b40c9c8a7"
    jobs = [
        job(f"https://jobs.lever.co/acme/{uuid}"),
        job(f"https://jobs.ashbyhq.com/acme/{uuid}", 2),
    ]
    postings, trace = steps.complete_jobs(jobs, max_reads=5)
    assert [p.text_source for p in postings] == ["api", "api"]
    assert [t.source for t in trace[:2]] == ["lever_api", "ashby_api"]
    assert len(read) == 2


def test_builtin_page_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        fetch_mod,
        "fetch",
        lambda url: fetch_mod.Fetched(url, url, 200, BUILTIN_HTML.encode()),
    )
    [posting], trace = steps.complete_jobs([job(BUILTIN_URL)], max_reads=5)
    assert posting.text_source == "parser"
    assert posting.company == "Acme Co"
    assert "2+ years of SQL" in posting.requirements
    assert posting.years_required == "2+ years"
    assert trace[0].source == "builtin_parser"


def test_other_pages_use_the_generic_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "read_page", fake_page)
    [posting], trace = steps.complete_jobs([job(PAGE_URL)], max_reads=5)
    assert posting.text_source == "page"
    assert posting.years_required == "4+ years"
    assert trace[0].source == "read_page"
    assert trace[0].note.startswith("text_source=page")


def test_http_429_keeps_the_job_with_its_card_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def too_many(url: str) -> Any:
        response = requests.Response()
        response.status_code = 429
        raise requests.HTTPError("429 Client Error: Too Many Requests", response=response)

    monkeypatch.setattr(fetch_mod, "fetch", too_many)
    jobs = [job(BUILTIN_URL, n, years_required="1-2 years") for n in range(1, 4)]
    postings, trace = steps.complete_jobs(jobs, max_reads=5)
    assert [p.id for p in postings] == ["j1", "j2", "j3"]
    assert {p.text_source for p in postings} == {"none"}
    assert all(p.description == "" and p.requirements == "card text" for p in postings)
    assert all(p.years_required == "1-2 years" for p in postings)
    reads = [t for t in trace if t.source == "builtin_parser"]
    assert len(reads) == 3
    assert all("429" in t.error for t in reads)
    assert trace[-1].args["none"] == 3


def test_a_429_is_retried_once_after_a_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "READ_RETRY_BACKOFF_S", 0.01)
    calls: dict[str, int] = {}

    def flaky(url: str) -> Any:
        calls[url] = calls.get(url, 0) + 1
        if calls[url] == 1:
            response = requests.Response()
            response.status_code = 429
            raise requests.HTTPError("429", response=response)
        return fetch_mod.Fetched(url=url, final_url=url, status=200, content=BUILTIN_HTML.encode())

    monkeypatch.setattr(fetch_mod, "fetch", flaky)
    [posting], trace = steps.complete_jobs([job(BUILTIN_URL, 1)], max_reads=5)
    assert posting.text_source == "parser"
    assert list(calls.values()) == [2]
    assert not trace[0].error


def test_reads_beyond_three_per_host_run_together(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "READ_HOST_CONCURRENCY", 5)
    monkeypatch.setattr(config, "READ_BUDGET_S", 3.0)

    def slow(url: str) -> Any:
        time.sleep(0.3)
        return fetch_mod.Fetched(url=url, final_url=url, status=200, content=BUILTIN_HTML.encode())

    monkeypatch.setattr(fetch_mod, "fetch", slow)
    start = time.monotonic()
    postings, _ = steps.complete_jobs([job(BUILTIN_URL, n) for n in range(1, 11)], max_reads=10)
    assert {p.text_source for p in postings} == {"parser"}
    assert time.monotonic() - start < 1.5  # two waves of 5; 3 per host would take 4 waves


def test_empty_page_counts_as_a_failed_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tools,
        "read_page",
        lambda url, max_chars=0: fake_page(url).model_copy(update={"markdown": " "}),
    )
    [posting], trace = steps.complete_jobs([job(PAGE_URL)], max_reads=5)
    assert posting.text_source == "none"
    assert trace[0].error


def test_a_slow_read_times_out_and_the_job_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "READ_BUDGET_S", 1.0)

    def slow(url: str, max_chars: int = 0) -> PageResult:
        if url.endswith("/1"):
            time.sleep(2)
        return fake_page(url)

    monkeypatch.setattr(tools, "read_page", slow)
    postings, trace = steps.complete_jobs([job(PAGE_URL, 1), job(PAGE_URL, 2)], max_reads=5)
    assert [p.text_source for p in postings] == ["none", "page"]
    assert any(t.error.startswith("Timeout") for t in trace)


def test_a_timed_out_read_names_the_reader_that_was_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "READ_BUDGET_S", 0.5)

    def slow(url: str) -> fetch_mod.Fetched:
        time.sleep(1.5)
        return fetch_mod.Fetched(url, url, 200, BUILTIN_HTML.encode())

    monkeypatch.setattr(fetch_mod, "fetch", slow)
    [posting], trace = steps.complete_jobs([job(BUILTIN_URL)], max_reads=5)
    assert posting.text_source == "none"
    timeout = next(t for t in trace if t.error.startswith("Timeout"))
    assert timeout.source == "builtin_parser"


def test_only_max_reads_jobs_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    read: list[str] = []

    def fake(url: str, max_chars: int = 0) -> PageResult:
        read.append(url)
        return fake_page(url)

    monkeypatch.setattr(tools, "read_page", fake)
    api_job = job(PAGE_URL, 0, description="Already have the text.")
    jobs = [api_job, *(job(PAGE_URL, n) for n in range(1, 5))]
    postings, trace = steps.complete_jobs(jobs, max_reads=2)
    assert sorted(read) == [PAGE_URL.format(n=1), PAGE_URL.format(n=2)]
    assert [p.text_source for p in postings] == ["api", "page", "page", "none", "none"]
    assert len([t for t in trace if t.source == "read_page"]) == 2


def test_zero_reads_still_returns_every_job() -> None:
    postings, _ = steps.complete_jobs([job(PAGE_URL, n) for n in range(3)], max_reads=0)
    assert [p.text_source for p in postings] == ["none"] * 3


def test_parsed_fields_fill_only_blanks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "postings.registry._RULES",
        [
            (
                re.compile("example"),
                "fake_parser",
                "parser",
                lambda url: ParsedPosting(description="Text.", location="Paris", salary="$1"),
            )
        ],
    )
    [posting], _ = steps.complete_jobs([job(PAGE_URL, location="Boston")], max_reads=1)
    assert (posting.location, posting.salary) == ("Boston", "$1")
