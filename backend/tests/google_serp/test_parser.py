from pathlib import Path

import pytest

from google_serp.parser import is_google_redirect, parse_meta_refresh, parse_results

FIXTURE = Path(__file__).parent / "fixtures" / "results_page.html"


@pytest.fixture(scope="module")
def results():
    return parse_results(FIXTURE.read_text(encoding="utf-8"))


def test_finds_organic_results_only(results):
    titles = [r.title for r in results]
    assert titles == [
        "Requests: HTTP for Humans™ — Requests documentation",
        "installation - Python requests library",
        "requests · PyPI",
        "I don't really understand requests",
    ]


def test_goto_links_are_absolute_and_kept_in_google_url(results):
    first = results[0]
    assert first.url == "https://www.google.com/goto?url=CAESabc1&gsessionid=x"
    assert first.google_url == first.url


def test_old_style_url_redirect_is_unwrapped(results):
    pypi = results[2]
    assert pypi.url == "https://pypi.org/project/requests/"
    assert pypi.google_url == ""


def test_display_url_ignores_metadata_cites(results):
    assert results[0].display_url == "https://requests.readthedocs.io"
    assert results[1].display_url == ""  # cite was "1 answer · 12 years ago"
    assert results[3].display_url == ""


def test_site_name_and_snippet(results):
    first, second = results[0], results[1]
    assert first.site_name == "Read the Docs"
    assert first.snippet.startswith("Requests is an elegant")
    assert second.site_name == "Stack Overflow"
    assert second.snippet.startswith("I am not all that familiar")
    assert results[3].site_name == "Reddit · r/learnpython"


def test_empty_page():
    assert parse_results("<html><body></body></html>") == []


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
