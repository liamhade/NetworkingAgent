"""google_serp.api: SERP API clients, offline (HTTP is faked)."""

import pytest

import google_serp
import tools
from google_serp import api

SERPER_PAGE = {
    "searchParameters": {"q": "playwright python", "type": "search"},
    "organic": [
        {
            "title": "Playwright for Python",
            "link": "https://playwright.dev/python/docs/intro",
            "snippet": "Playwright was created specifically to accommodate the needs...",
            "position": 1,
        },
        {
            "title": "Jane Doe - Recruiter - Navan | LinkedIn",
            "link": "https://www.linkedin.com/in/jane-doe",
            "snippet": "New York · Recruiter at Navan",
            "date": "Mar 3, 2025",
            "position": 2,
        },
        {"title": "No link", "position": 3},
    ],
}

SERPAPI_PAGE = {
    "organic_results": [
        {
            "position": 1,
            "title": "Playwright for Python",
            "link": "https://playwright.dev/python/docs/intro",
            "displayed_link": "https://playwright.dev › python › docs",
            "snippet": "Playwright was created...",
            "source": "Playwright",
            "date": "2 days ago",
        }
    ]
}


class FakeResponse:
    def __init__(self, status: int, payload=None, text: str = ""):
        self.status_code = status
        self._payload = payload
        self.text = text or str(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeHttp:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict] = []

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response

    def get(self, url, **kwargs):
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return self.response


def test_serper_parses_urls_titles_and_metadata():
    http = FakeHttp(FakeResponse(200, SERPER_PAGE))
    response = api.SerperClient("k", session=http).search("playwright python")

    assert http.calls[0]["headers"] == {"X-API-KEY": "k"}
    assert http.calls[0]["json"]["q"] == "playwright python"
    assert [r.url for r in response.results] == [
        "https://playwright.dev/python/docs/intro",
        "https://www.linkedin.com/in/jane-doe",
    ]
    first, second = response.results
    assert first.title == "Playwright for Python"
    assert first.display_url == "https://playwright.dev › python › docs › intro"
    assert first.site_name == "playwright.dev"
    assert first.google_url == ""  # nothing to resolve
    assert (second.position, second.date) == (2, "Mar 3, 2025")


def test_serpapi_parses_results():
    http = FakeHttp(FakeResponse(200, SERPAPI_PAGE))
    response = api.SerpApiClient("k", session=http).search("playwright python")

    assert http.calls[0]["params"]["engine"] == "google"
    (r,) = response.results
    assert (r.site_name, r.display_url, r.date) == (
        "Playwright",
        "https://playwright.dev › python › docs",
        "2 days ago",
    )


def test_serpapi_no_results_is_empty_not_an_error():
    payload = {"error": "Google hasn't returned any results for this query."}
    client = api.SerpApiClient("k", session=FakeHttp(FakeResponse(200, payload)))
    assert client.search("zzzz").results == []


@pytest.mark.parametrize(
    "response",
    [FakeResponse(403, {"message": "Unauthorized."}), FakeResponse(200, None, "<html>")],
)
def test_bad_responses_raise(response):
    with pytest.raises(api.SerpApiError):
        api.SerperClient("k", session=FakeHttp(response)).search("q")


def test_client_from_env(monkeypatch: pytest.MonkeyPatch):
    assert api.client_from_env() is None
    monkeypatch.setenv("SERPAPI_API_KEY", "b")
    assert isinstance(api.client_from_env(), api.SerpApiClient)
    monkeypatch.setenv("SERPER_API_KEY", "a")
    assert isinstance(api.client_from_env(), api.SerperClient)


def test_worker_uses_api_and_never_starts_chrome(monkeypatch: pytest.MonkeyPatch):
    def no_browser():
        raise AssertionError("Chrome must not start when an API client is configured")

    monkeypatch.setattr(google_serp, "GoogleSerpSession", no_browser)
    http = FakeHttp(FakeResponse(200, SERPER_PAGE))
    worker = tools._GoogleWorker(cache_ttl=60, client=api.SerperClient("k", session=http))
    try:
        first = worker.search("playwright python", resolve_urls=True)
        again = worker.search("playwright python", resolve_urls=True)
    finally:
        worker.close()
        worker.close()  # idempotent (tools.shutdown and atexit both call it)

    assert len(first.results) == 2
    assert [r.url for r in again.results] == [r.url for r in first.results]
    assert len(http.calls) == 1  # second search served from cache
