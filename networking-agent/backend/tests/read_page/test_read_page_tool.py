"""`tools.read_page`, the read_page source used by the pipeline (no network)."""

import pytest
from rp_fakes import FakeWeb, fixture_bytes

import tools
from read_page import PageBlocked


def test_returns_page(web: FakeWeb) -> None:
    web.page("https://acme.com/blog/x", fixture_bytes("article.html"))
    page = tools.read_page("https://acme.com/blog/x")
    assert page.method == "static"
    assert "(https://acme.com/docs/airflow)" in page.markdown


def test_max_chars(web: FakeWeb) -> None:
    web.page("https://acme.com/long", "<html><body><main>" + "<p>word " * 5000 + "</main>")
    page = tools.read_page("https://acme.com/long", max_chars=2000)
    assert page.truncated and len(page.markdown) <= 2000


def test_linkedin_profiles_are_refused(web: FakeWeb) -> None:
    with pytest.raises(PageBlocked, match="linkedin_people"):
        tools.read_page("https://www.linkedin.com/in/janedoe")


def test_fetch_errors_are_raised(web: FakeWeb) -> None:
    with pytest.raises(Exception, match="404"):
        tools.read_page("https://acme.com/missing")
