"""read_page(): registry, auto fallbacks, caching, truncation and blocking (no network)."""

import pytest
from rp_fakes import FakeWeb, fixture_bytes
from test_read_page_methods import ASHBY_ID, ASHBY_JSON, GREENHOUSE_JSON

import read_page
from read_page import PageBlocked, PageResult, ReadPageError, core, methods, registry


@pytest.mark.parametrize(
    ("url", "method"),
    [
        ("https://www.linkedin.com/in/janedoe/", registry.BLOCKED),
        ("https://uk.linkedin.com/in/janedoe", registry.BLOCKED),
        ("https://job-boards.greenhouse.io/discord/jobs/8917177002", "greenhouse_api"),
        ("https://boards.greenhouse.io/datadog/jobs/8257324", "greenhouse_api"),
        ("https://jobs.lever.co/spotify/2a55d6c9-0000-4000-8000-000000000000", "lever_api"),
        (f"https://jobs.ashbyhq.com/notion/{ASHBY_ID}", "ashby_api"),
        ("https://www.builtinnyc.com/job/senior-product-engineer/11344396", "jsonld"),
        ("https://builtin.com/job/x/1", "jsonld"),
        ("https://www.linkedin.com/company/datadog/", None),
        ("https://careers.datadoghq.com/detail/1/?gh_jid=1", None),
        ("https://en.wikipedia.org/wiki/Datadog", None),
    ],
)
def test_registry_builtin_rules(url: str, method: str | None) -> None:
    assert registry.match(url) == method


def test_register_takes_precedence() -> None:
    registry.register(r"^https?://jobs\.lever\.co/", "full")
    registry.register(r"example\.com/team", "full")
    assert registry.match("https://jobs.lever.co/a/2a55d6c9-0000-4000-8000-000000000000") == "full"
    assert registry.match("https://example.com/team") == "full"
    registry.unregister_all()
    assert registry.match("https://example.com/team") is None


def test_registered_method_is_used_by_auto(web: FakeWeb) -> None:
    web.page("https://acme.com/about/leadership", fixture_bytes("leadership.html"))
    read_page.register(r"acme\.com/about/", "full")
    assert read_page.read_page("https://acme.com/about/leadership").method == "full"


def test_linkedin_profiles_are_refused_for_every_method(web: FakeWeb) -> None:
    for method in (None, "static", "browser"):
        with pytest.raises(PageBlocked, match="linkedin_people"):
            read_page.read_page("https://www.linkedin.com/in/williamhgates/", method=method)
    assert web.calls == []


def test_rejects_bad_url_and_unknown_method(web: FakeWeb) -> None:
    with pytest.raises(ReadPageError):
        read_page.read_page("ftp://example.com/x")
    with pytest.raises(ReadPageError, match="Unknown method"):
        read_page.read_page("https://example.com/", method="magic")
    assert web.calls == []


def test_auto_default_is_static(web: FakeWeb) -> None:
    web.page("https://acme.com/blog/x", fixture_bytes("article.html"))
    result = read_page.read_page("https://acme.com/blog/x")
    assert result.method == "static"
    assert result.truncated is False
    assert web.calls == [("fetch", "https://acme.com/blog/x")]


def test_auto_uses_specialized_method(web: FakeWeb) -> None:
    web.json["https://boards-api.greenhouse.io/v1/boards/discord/jobs/123"] = GREENHOUSE_JSON
    result = read_page.read_page("https://job-boards.greenhouse.io/discord/jobs/123")
    assert result.method == "greenhouse_api"
    assert [kind for kind, _ in web.calls] == ["json"]


def test_auto_falls_back_to_static_when_api_fails(web: FakeWeb) -> None:
    url = "https://job-boards.greenhouse.io/discord/jobs/123"
    web.json["https://boards-api.greenhouse.io/v1/boards/discord/jobs/123"] = RuntimeError("down")
    web.page(url, fixture_bytes("article.html"))
    result = read_page.read_page(url)
    assert result.method == "static"
    assert [kind for kind, _ in web.calls] == ["json", "fetch"]


def test_explicit_method_does_not_fall_back(web: FakeWeb) -> None:
    url = "https://job-boards.greenhouse.io/discord/jobs/123"
    web.page(url, fixture_bytes("article.html"))
    with pytest.raises(read_page.MethodUnavailable):
        read_page.read_page(url, method="greenhouse_api")


def test_js_shell_uses_jsonld_without_browser(web: FakeWeb) -> None:
    # Ashby board API has no such job -> generic path -> JS shell -> JSON-LD in the same HTML.
    url = f"https://jobs.ashbyhq.com/notion/{ASHBY_ID}"
    web.json["https://api.ashbyhq.com/posting-api/job-board/notion"] = {"jobs": []}
    web.page(url, fixture_bytes("js_shell_jsonld.html"))
    result = read_page.read_page(url)
    assert result.method == "jsonld"
    assert "**Company:** Notion" in result.markdown
    assert not any(kind == "browser" for kind, _ in web.calls)


def test_ashby_api_preferred_when_job_listed(web: FakeWeb) -> None:
    web.json["https://api.ashbyhq.com/posting-api/job-board/notion"] = ASHBY_JSON
    result = read_page.read_page(f"https://jobs.ashbyhq.com/notion/{ASHBY_ID}")
    assert result.method == "ashby_api"


def test_js_shell_without_jsonld_renders_in_browser(web: FakeWeb) -> None:
    url = "https://spa.example.com/job"
    web.page(url, fixture_bytes("js_shell.html"))
    web.rendered[url] = fixture_bytes("rendered.html").decode()
    result = read_page.read_page(url)
    assert result.method == "browser"
    assert "Notion is hiring" in result.markdown
    assert web.calls == [("fetch", url), ("browser", url)]


def test_empty_everywhere_raises(web: FakeWeb) -> None:
    url = "https://spa.example.com/empty"
    web.page(url, fixture_bytes("js_shell.html"))
    web.rendered[url] = "<html><body></body></html>"
    with pytest.raises(ReadPageError, match="No readable content"):
        read_page.read_page(url)


def test_card_page_switches_to_full(web: FakeWeb, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate trafilatura dropping the card headings (as on the Datadog leadership page).
    monkeypatch.setattr(
        methods,
        "trafilatura_markdown",
        lambda html, url: "Meet the people who lead Acme, a data company. " * 5,
    )
    web.page("https://acme.com/about/leadership", fixture_bytes("leadership.html"))
    result = read_page.read_page("https://acme.com/about/leadership")
    assert result.method == "full"
    assert "Olivia Pomeroy" in result.markdown
    assert len(web.calls) == 1  # cleaned-full reuses the fetched HTML


def test_cache_avoids_refetch_and_applies_max_chars_per_call(web: FakeWeb) -> None:
    web.page("https://acme.com/blog/x", fixture_bytes("article.html"))
    full = read_page.read_page("https://acme.com/blog/x")
    short = read_page.read_page("https://acme.com/blog/x", max_chars=100)
    assert len(web.calls) == 1
    assert short.truncated and len(short.markdown) <= 100
    assert not full.truncated
    read_page.clear_cache()
    read_page.read_page("https://acme.com/blog/x")
    assert len(web.calls) == 2


def test_truncate_prefers_paragraph_break() -> None:
    page = PageResult(
        url="u", final_url="u", method="static", markdown="a" * 90 + "\n\n" + "b" * 50
    )
    out = core.truncate(page, 100)
    assert out.truncated
    assert out.markdown == "a" * 90
    hard = core.truncate(page.model_copy(update={"markdown": "x" * 500}), 100)
    assert hard.markdown == "x" * 100
    assert core.truncate(page, 1000) is page
