"""Offline tests for the Conservation Job Board API (URL building, parsing, pagination)."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from conservation_jobboard import api
from conservation_jobboard.models import Category, ExperienceLevel, JobFilter, JobType, Location

FIXTURES = Path(__file__).parent / "fixtures"


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _soup(name: str) -> BeautifulSoup:
    return BeautifulSoup(_html(name), "html.parser")


def test_search_path_without_filters() -> None:
    assert api.search_path(JobFilter()) == "/"
    assert api.search_path(JobFilter(), page=3) == "/3"


def test_search_path_with_filters() -> None:
    job_filter = JobFilter(
        keyword=" wildlife biologist ",
        categories=[Category.WILDLIFE, Category.ECOLOGY],
        locations=[Location.COLORADO, Location.CALIFORNIA, Location.REMOTE],
        job_types=[JobType.TEMPORARY],
        experience_levels=[ExperienceLevel.ENTRY],
    )
    assert api.search_path(job_filter) == (
        "/search/kw=wildlife%20biologist&cat=1-5&state=6-5&region=9&type=2&experience=1"
    )
    assert api.search_path(job_filter, page=2).endswith("&experience=1/2")


def test_search_path_escapes_keyword() -> None:
    assert api.search_path(JobFilter(keyword="a&b/c")) == "/search/kw=a%26b%2Fc"


def test_filters_accept_slugs() -> None:
    job_filter = JobFilter.model_validate({"locations": ["new-york", "remote"]})
    assert job_filter.locations == [Location.NEW_YORK, Location.REMOTE]
    assert [(loc.key, loc.site_id) for loc in job_filter.locations] == [
        ("state", 33),
        ("region", 9),
    ]


def test_parse_jobs_keeps_only_main_results() -> None:
    # The fixture also has featured (paid) and sponsor cards, which are skipped.
    jobs = api.parse_jobs(_soup("search_page1.html"))
    assert [j.id for j in jobs] == [281276, 281272, 281274, 281234]
    job = jobs[0]
    assert job.title == "Wildlife Biologist - Nuisance Wildlife"
    assert job.url == (
        "https://www.conservationjobboard.com/"
        "job-listing-wildlife-biologist---nuisance-wildlife-dallas-texas/7084278620"
    )
    assert job.organization == "Wildernex LLC Wildlife Control"
    assert job.location == "Dallas, TX"
    assert job.job_type == "Permanent"
    assert job.salary == "$45,000 - $100,000 per year"
    assert job.deadline == "Nov 30, 2026"
    assert job.experience == "0 - 1 year"
    assert job.posted == "Today"
    assert jobs[3].deadline is None  # Not every card has a deadline.


def test_parse_jobs_empty_page() -> None:
    assert api.parse_jobs(_soup("search_empty.html")) == []


def test_get_jobs_paginates_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Page 3 repeats page 1, so pagination stops there with no duplicates.
    pages = {1: "search_page1.html", 2: "search_page2.html", 3: "search_page1.html"}
    fetched: list[str] = []

    def fake_fetch(path: str) -> BeautifulSoup:
        fetched.append(path)
        page = int(path.rsplit("/", 1)[1]) if path.rsplit("/", 1)[1].isdigit() else 1
        return _soup(pages[page])

    monkeypatch.setattr(api, "_fetch", fake_fetch)
    monkeypatch.setattr(api, "REQUEST_DELAY_S", 0)
    jobs = api.get_jobs(JobFilter(keyword="wildlife biologist"), n=20)
    assert len(jobs) == 7 and len({j.id for j in jobs}) == 7
    assert fetched == [
        "/search/kw=wildlife%20biologist",
        "/search/kw=wildlife%20biologist/2",
        "/search/kw=wildlife%20biologist/3",
    ]


def test_get_jobs_stops_at_n(monkeypatch: pytest.MonkeyPatch) -> None:
    fetched: list[str] = []

    def fake_fetch(path: str) -> BeautifulSoup:
        fetched.append(path)
        return _soup("search_page1.html")

    monkeypatch.setattr(api, "_fetch", fake_fetch)
    jobs = api.get_jobs(JobFilter(), n=3)
    assert len(jobs) == 3 and fetched == ["/"]


def test_get_jobs_caps_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_fetch(path: str) -> BeautifulSoup:
        # Every page brings new ids, so only MAX_PAGES stops the loop.
        calls["n"] += 1
        html = _html("search_page1.html").replace('job_id="2812', f'job_id="{calls["n"]}2812')
        return BeautifulSoup(html, "html.parser")

    monkeypatch.setattr(api, "_fetch", fake_fetch)
    monkeypatch.setattr(api, "REQUEST_DELAY_S", 0)
    jobs = api.get_jobs(JobFilter(), n=1000)
    assert calls["n"] == api.MAX_PAGES
    assert len(jobs) == 4 * api.MAX_PAGES
