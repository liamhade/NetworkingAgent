"""Provider-agnostic ATS helpers (`ats.search`): queries, boards from Google, matching."""

import json
from pathlib import Path

import pytest

from ats import AtsJob, Board, boards_from_results, filter_jobs, needs_resolving, site_query
from ats.greenhouse import GREENHOUSE
from ats.search import breadcrumb_url, matches_keywords, matches_location
from google_serp import SearchResult

FIXTURES = Path(__file__).parent / "fixtures"


def google_results() -> list[SearchResult]:
    raw = json.loads((FIXTURES / "google_results.json").read_text(encoding="utf-8"))
    return [SearchResult(**r) for r in raw]


def job(i: int, title: str, location: str = "New York, NY", **extra) -> AtsJob:
    return AtsJob(
        provider="greenhouse",
        board="acme",
        id=str(i),
        title=title,
        url=f"https://job-boards.greenhouse.io/acme/jobs/{i}",
        company="Acme",
        location=location,
        **extra,
    )


# --- the query -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("keywords", "location", "query"),
    [
        (
            "data analyst",
            "New York, NY",
            'site:job-boards.greenhouse.io OR site:boards.greenhouse.io "data analyst" "New York"',
        ),
        (
            '"data analyst"',
            "Remote",
            'site:job-boards.greenhouse.io OR site:boards.greenhouse.io "data analyst" remote',
        ),
        (
            "analyst",
            "Boston",
            'site:job-boards.greenhouse.io OR site:boards.greenhouse.io "analyst" Boston',
        ),
        ("", "", "site:job-boards.greenhouse.io OR site:boards.greenhouse.io"),
    ],
)
def test_site_query(keywords: str, location: str, query: str) -> None:
    assert site_query(GREENHOUSE, keywords, location) == query


# --- boards from Google results ------------------------------------------------------


@pytest.mark.parametrize(
    ("crumb", "url"),
    [
        (
            "https://job-boards.greenhouse.io › discord › jobs › 1",
            "https://job-boards.greenhouse.io/discord/jobs/1",
        ),
        ("https://boards.greenhouse.io › acme", "https://boards.greenhouse.io/acme"),
        ("https://job-boards.greenhouse.io › acme › ...", "https://job-boards.greenhouse.io/acme"),
        ("https://job-boards.greenhouse.io › …", "https://job-boards.greenhouse.io"),
        ("8 comments · 3 years ago", ""),
        ("", ""),
    ],
)
def test_breadcrumb_url(crumb: str, url: str) -> None:
    assert breadcrumb_url(crumb) == url


def test_boards_are_read_from_breadcrumbs_without_resolving() -> None:
    results = google_results()
    boards = boards_from_results(results, GREENHOUSE)
    assert boards == [
        # Two Discord results (one with a capitalised slug) merge into one board.
        Board(provider="greenhouse", slug="discord", job_ids=["8865033002", "8691572002"]),
        Board(provider="greenhouse", slug="acmecorp", job_ids=[]),
        Board(provider="greenhouse", slug="euroltd", job_ids=["4400123"]),
    ]
    # Only the embed and the truncated breadcrumb hide their board; Indeed is off-provider.
    assert [r.url for r in results if needs_resolving(r, GREENHOUSE)] == [
        "https://www.google.com/goto?url=AAA4",
        "https://www.google.com/goto?url=AAA7",
    ]


def test_resolved_urls_win_over_breadcrumbs() -> None:
    result = SearchResult(
        title="Analytics Lead",
        url="https://boards.greenhouse.io/embed/job_app?for=widgetco&token=555",
        display_url="https://boards.greenhouse.io › embed › job_app",
    )
    assert boards_from_results([result], GREENHOUSE) == [
        Board(provider="greenhouse", slug="widgetco", job_ids=["555"])
    ]
    assert not needs_resolving(result, GREENHOUSE)


def test_a_result_resolved_off_provider_is_not_resolved_again() -> None:
    result = SearchResult(title="x", url="https://careers.example.com/jobs?gh_jid=1")
    assert boards_from_results([result], GREENHOUSE) == []
    assert not needs_resolving(result, GREENHOUSE)


# --- matching ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "keywords", "match"),
    [
        ("Senior Data Analyst, Risk", "data analyst", True),
        ("Data Analytics Manager", "data analyst", True),  # crude stem: analy-
        ("Analyst, Data Platform", "data analyst", True),  # any order
        ("Analytics Engineer", "data analyst", False),
        ("Software Engineer, Payments", "software engineer", True),
        ("Engineering Manager", "engineer", True),
        ("Strategic Finance Analyst", "finance analyst jobs", True),  # stopwords ignored
        ("Product Designer", "", True),
    ],
)
def test_matches_keywords(title: str, keywords: str, match: bool) -> None:
    assert matches_keywords(job(1, title), keywords) is match


def test_departments_count_as_keywords() -> None:
    assert matches_keywords(job(1, "Analyst II", departments=["Data Science"]), "data analyst")


@pytest.mark.parametrize(
    ("job_location", "location", "match"),
    [
        ("New York, NY", "New York, NY", True),
        ("NYC - Hybrid", "New York", True),
        ("New York City or Remote", "New York", True),
        ("San Francisco Bay Area or Remote (U.S.)", "San Francisco, CA", True),
        ("San Francisco Bay Area", "New York", False),
        ("Remote (U.S.)", "remote", True),
        ("San Francisco Bay Area", "Remote", False),
        ("York, UK", "New York", False),
        ("Newark, NJ", "New York", False),
        ("", "New York", False),
        ("Anywhere", "", True),
    ],
)
def test_matches_location(job_location: str, location: str, match: bool) -> None:
    assert matches_location(job(1, "Analyst", job_location), location) is match


def test_filter_jobs_puts_googles_postings_first_and_caps() -> None:
    jobs = [
        job(1, "Data Analyst"),
        job(2, "Product Designer"),
        job(3, "Senior Data Analyst"),
        job(4, "Data Analyst", "London"),
        job(5, "Data Analyst II"),
        job(6, "Lead Data Analyst"),
        job(7, "Head of Design", "London"),  # Google pointed at it: kept despite filters
    ]
    picked = filter_jobs(jobs, "data analyst", "New York", job_ids=["7", "999", "7"], n=3)
    assert [j.id for j in picked] == ["7", "1", "3"]
    assert [j.id for j in filter_jobs(jobs, "data analyst", "New York", n=10)] == [
        "1",
        "3",
        "5",
        "6",
    ]
    assert filter_jobs(jobs, "astronaut", "New York") == []
