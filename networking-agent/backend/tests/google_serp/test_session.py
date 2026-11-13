"""GoogleSerpSession logic with a fake Playwright page (no browser, no network)."""

from pathlib import Path

from google_serp import SearchResult
from google_serp.session import GoogleSerpSession, default_profile_dir

FIXTURE = Path(__file__).parent / "fixtures" / "results_page.html"


class FakeResponse:
    def __init__(self, status, headers=None, text=""):
        self.status = status
        self.headers = headers or {}
        self._text = text

    def text(self):
        return self._text


class FakeRequest:
    """`page.request`: /goto -> 302 with the real URL as Location."""

    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def get(self, url, max_redirects=None):
        self.calls.append((url, max_redirects))
        if url in self.responses:
            return self.responses[url]
        return FakeResponse(302, {"location": f"https://dest.example/{len(self.calls)}?a=1&b=2"})


class FakePage:
    def __init__(self, html=""):
        self.html = html
        self.url = "https://www.google.com/search?q=x"
        self.request = FakeRequest()
        self.goto_calls = []
        self.selector_waits = []
        self.timeouts = []

    def goto(self, url, wait_until=None, timeout=None):
        self.goto_calls.append((url, wait_until))

    def wait_for_selector(self, selector, timeout=None):
        self.selector_waits.append(selector)

    def wait_for_timeout(self, ms):
        self.timeouts.append(ms)

    def content(self):
        return self.html


def _session(page: FakePage) -> GoogleSerpSession:
    session = GoogleSerpSession()
    session._context = object()  # marks it as started, so start() is a no-op
    session._page = page
    return session


def _redirect(i: int) -> SearchResult:
    goto = f"https://www.google.com/goto?url=TOKEN{i}"
    return SearchResult(title=f"r{i}", url=goto, google_url=goto)


def test_search_waits_for_results_not_full_load_and_leaves_links_unresolved():
    page = FakePage(FIXTURE.read_text(encoding="utf-8"))
    response = _session(page).search("python requests")
    assert page.goto_calls == [
        ("https://www.google.com/search?q=python+requests&hl=en", "domcontentloaded")
    ]
    assert page.selector_waits == ["#search, #rso"]
    assert response.query == "python requests"
    assert [r for r in response.results if r.google_url]
    assert all(r.url == r.google_url for r in response.results if r.google_url)
    assert page.request.calls == []


def test_resolve_results_follows_each_redirect_link_once():
    page = FakePage(FIXTURE.read_text(encoding="utf-8"))
    session = _session(page)
    response = session.search("python requests")
    session.resolve_results(response.results)
    redirects = [r for r in response.results if r.google_url]
    assert all(r.url.startswith("https://dest.example/") for r in redirects)
    assert len(page.request.calls) == len(redirects)
    assert all(max_redirects == 0 for _, max_redirects in page.request.calls)


def test_resolve_results_keeps_location_exactly_and_skips_resolved():
    page = FakePage()
    results = [
        _redirect(1),
        SearchResult(title="plain", url="https://plain.example/"),
        SearchResult(
            title="done",
            url="https://already.example/",
            google_url="https://www.google.com/goto?url=DONE",
        ),
    ]
    _session(page).resolve_results(results)
    # The Location header is used verbatim: same full URL as before the change.
    assert results[0].url == "https://dest.example/1?a=1&b=2"
    assert results[0].google_url == "https://www.google.com/goto?url=TOKEN1"
    assert results[1].url == "https://plain.example/"
    assert results[2].url == "https://already.example/"
    assert [url for url, _ in page.request.calls] == ["https://www.google.com/goto?url=TOKEN1"]


def test_resolve_honours_meta_refresh_throttle():
    page = FakePage()
    goto = "https://www.google.com/goto?url=SLOW"
    page.request.responses[goto] = FakeResponse(
        200, text='<meta http-equiv="refresh" content="3; url=/goto?url=SLOW2">'
    )
    result = SearchResult(title="slow", url=goto, google_url=goto)
    _session(page).resolve_results([result])
    assert page.timeouts == [3000]
    assert page.request.calls[1][0] == "https://www.google.com/goto?url=SLOW2"
    assert result.url.startswith("https://dest.example/")


def test_resolve_failure_keeps_goto_link():
    page = FakePage()

    def boom(url, max_redirects=None):
        raise RuntimeError("network down")

    page.request.get = boom
    result = _redirect(1)
    _session(page).resolve_results([result])
    assert result.url == result.google_url


def test_profile_dir_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_SERP_PROFILE_DIR", str(tmp_path))
    assert default_profile_dir() == tmp_path
    monkeypatch.delenv("GOOGLE_SERP_PROFILE_DIR")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert default_profile_dir() == tmp_path / "google-serp" / "chrome-profile"
