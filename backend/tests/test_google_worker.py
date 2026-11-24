"""tools._GoogleWorker: selective link resolution and the results cache (no browser)."""

import pytest

import google_serp
import tools
from google_serp import SearchResponse, SearchResult


class FakeSession:
    """Stands in for GoogleSerpSession; counts page loads and resolved links."""

    def __init__(self, n_results: int = 10, fail_first: bool = False):
        self.n_results = n_results
        self.fail_first = fail_first
        self.searches: list[str] = []
        self.resolved: list[str] = []
        self.closed = False

    def start(self):
        return self

    def close(self):
        self.closed = True

    def search(self, query):
        self.searches.append(query)
        if self.fail_first:
            self.fail_first = False
            raise RuntimeError("browser crashed")
        results = []
        for i in range(1, self.n_results + 1):
            goto = f"https://www.google.com/goto?url={query}-{i}"
            # Even positions look like LinkedIn profiles, odd ones like job boards.
            site = f"LinkedIn · Person {i}" if i % 2 == 0 else "Indeed"
            title = f"Person {i} - Recruiter at Ramp" if i % 2 == 0 else f"r{i}"
            results.append(SearchResult(title=title, url=goto, google_url=goto, site_name=site))
        return SearchResponse(results=results, query=query)

    def resolve_results(self, results):
        for r in results:
            if r.google_url and r.url == r.google_url:
                self.resolved.append(r.google_url)
                i = r.google_url.rsplit("-", 1)[1]  # position on the page
                if r.site_name.startswith("LinkedIn"):
                    r.url = f"https://www.linkedin.com/in/person-{i}"
                else:
                    r.url = f"https://real.example/{i}"


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch):
    sessions: list[FakeSession] = []

    def factory():
        sessions.append(FakeSession())
        return sessions[-1]

    monkeypatch.setattr(google_serp, "GoogleSerpSession", factory)
    w = tools._GoogleWorker(cache_ttl=60)
    w.sessions = sessions
    yield w
    w.close()


def test_only_picked_results_are_resolved(worker):
    response = worker.search("q", pick=lambda rs: rs[:3])
    session = worker.sessions[0]
    assert session.searches == ["q"]
    assert len(session.resolved) == 3
    assert [r.url for r in response.results] == [
        "https://real.example/1",
        "https://www.linkedin.com/in/person-2",
        "https://real.example/3",
    ]


def test_no_pick_resolves_everything(worker):
    response = worker.search("q")
    assert len(response.results) == 10
    assert len(worker.sessions[0].resolved) == 10


def test_resolve_urls_false_keeps_goto_links(worker):
    response = worker.search("q", resolve_urls=False)
    assert worker.sessions[0].resolved == []
    assert all(r.url == r.google_url for r in response.results)


def test_repeated_query_uses_cache_and_only_resolves_new_results(worker):
    worker.search("q", pick=lambda rs: rs[:3])
    response = worker.search("q", pick=lambda rs: rs[:5])
    session = worker.sessions[0]
    assert session.searches == ["q"]  # one page load for both calls
    assert len(session.resolved) == 5  # 3 the first time, 2 more the second
    assert len(response.results) == 5


def test_cache_expires(worker, monkeypatch: pytest.MonkeyPatch):
    clock = [1000.0]
    monkeypatch.setattr(tools.time, "monotonic", lambda: clock[0])
    worker.search("q", pick=lambda rs: rs[:1])
    clock[0] += 61
    worker.search("q", pick=lambda rs: rs[:1])
    assert len(worker.sessions[0].searches) == 2


def test_cache_disabled_with_zero_ttl(monkeypatch: pytest.MonkeyPatch):
    session = FakeSession()
    monkeypatch.setattr(google_serp, "GoogleSerpSession", lambda: session)
    w = tools._GoogleWorker(cache_ttl=0)
    try:
        w.search("q", pick=lambda rs: rs[:1])
        w.search("q", pick=lambda rs: rs[:1])
    finally:
        w.close()
    assert len(session.searches) == 2


def test_empty_results_are_not_cached(monkeypatch: pytest.MonkeyPatch):
    session = FakeSession(n_results=0)
    monkeypatch.setattr(google_serp, "GoogleSerpSession", lambda: session)
    w = tools._GoogleWorker(cache_ttl=60)
    try:
        w.search("q")
        w.search("q")
    finally:
        w.close()
    assert len(session.searches) == 2


def test_browser_is_restarted_once_after_a_failure(monkeypatch: pytest.MonkeyPatch):
    sessions = [FakeSession(fail_first=True), FakeSession()]
    made = iter(sessions)
    monkeypatch.setattr(google_serp, "GoogleSerpSession", lambda: next(made))
    w = tools._GoogleWorker(cache_ttl=60)
    try:
        response = w.search("q", pick=lambda rs: rs[:2])
    finally:
        w.close()
    assert sessions[0].closed
    assert len(response.results) == 2
    assert len(sessions[1].resolved) == 2


def test_tools_resolve_only_what_they_return(monkeypatch: pytest.MonkeyPatch):
    session = FakeSession()
    monkeypatch.setattr(google_serp, "GoogleSerpSession", lambda: session)
    w = tools._GoogleWorker(cache_ttl=60)
    monkeypatch.setattr(tools, "_google_worker", lambda: w)
    monkeypatch.setattr(tools.config, "GOOGLE_RESOLVE_URLS", True)
    try:
        out = tools.google_search("jobs", n=2)
        assert len(out) == 2 and len(session.resolved) == 2

        session.resolved.clear()
        people = tools.linkedin_people("Ramp", "x", n=3)
        # Only the LinkedIn profiles (even positions) are resolved, and only 3 of them.
        assert [p["url"] for p in people] == [
            f"https://www.linkedin.com/in/person-{i}" for i in (2, 4, 6)
        ]
        assert len(session.resolved) == 3
    finally:
        w.close()


def test_rejected_pages_are_not_cached(worker):
    worker.search("q", cacheable=lambda page: False)
    worker.search("q", cacheable=lambda page: False)
    assert len(worker.sessions[0].searches) == 2
    worker.search("q", cacheable=lambda page: True)
    worker.search("q", cacheable=lambda page: True)
    assert len(worker.sessions[0].searches) == 3
