from pathlib import Path

import pytest

from google_serp import parse_results_page
from google_serp.parser import is_google_redirect, parse_meta_refresh

FIXTURE = Path(__file__).parent / "fixtures" / "results_page.html"


@pytest.fixture(scope="module")
def response():
    return parse_results_page(FIXTURE.read_text(encoding="utf-8"), "python requests library")


def test_finds_organic_results_only(response):
    titles = [r.title for r in response.results]
    assert titles == [
        "Requests: HTTP for Humans™ — Requests documentation",
        "installation - Python requests library",
        "requests · PyPI",
        "I don't really understand requests",
    ]
    assert [r.position for r in response.results] == [1, 2, 3, 4]


def test_goto_links_are_absolute_and_kept_in_google_url(response):
    first = response.results[0]
    assert first.url == "https://www.google.com/goto?url=CAESabc1&gsessionid=x"
    assert first.google_url == first.url


def test_old_style_url_redirect_is_unwrapped(response):
    pypi = response.results[2]
    assert pypi.url == "https://pypi.org/project/requests/"
    assert pypi.google_url == ""


def test_display_url_ignores_metadata_cites(response):
    assert response.results[0].display_url == "https://requests.readthedocs.io"
    assert response.results[1].display_url == ""  # cite was "1 answer · 12 years ago"
    assert response.results[3].display_url == ""


def test_site_name_and_snippet(response):
    first, second = response.results[0], response.results[1]
    assert first.site_name == "Read the Docs"
    assert first.snippet.startswith("Requests is an elegant")
    assert second.site_name == "Stack Overflow"
    assert second.snippet.startswith("I am not all that familiar")
    assert response.results[3].site_name == "Reddit · r/learnpython"


def test_metadata(response):
    meta = response.metadata
    assert meta.query == "python requests library"
    assert meta.results_count == "About 10,500 results"
    assert meta.search_time == 0.19


def test_metadata_old_seconds_format():
    html = '<div id="result-stats">About 1,230,000 results (0.45 seconds)</div>'
    meta = parse_results_page(html, "q").metadata
    assert meta.results_count == "About 1,230,000 results"
    assert meta.search_time == 0.45


def test_empty_page():
    response = parse_results_page("<html><body></body></html>", "q")
    assert response.results == []
    assert response.metadata.results_count is None


def test_to_dict_is_json_ready(response):
    import json

    data = json.loads(json.dumps(response.to_dict()))
    assert data["metadata"]["query"] == "python requests library"
    assert data["results"][0]["site_name"] == "Read the Docs"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.google.com/goto?url=abc", True),
        ("https://www.google.com/url?q=https://x.org", True),
        ("https://www.google.com/search?q=x", False),
        ("https://example.com/goto?url=abc", False),
    ],
)
def test_is_google_redirect(url, expected):
    assert is_google_redirect(url) is expected


def test_parse_meta_refresh():
    html = '<meta content="3;url=/goto?url=CAES&amp;x=1" http-equiv="refresh">'
    assert parse_meta_refresh(html) == (3, "/goto?url=CAES&x=1")
    assert parse_meta_refresh("<html></html>") is None
