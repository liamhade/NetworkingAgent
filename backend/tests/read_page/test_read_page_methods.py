"""Each read_page method on fixture HTML / mocked API JSON (no network)."""

import pytest
from rp_fakes import FakeWeb, fixture_bytes

from read_page import MethodUnavailable, convert, methods


def test_static_absolute_links_title_and_charset(web: FakeWeb) -> None:
    # The fixture has no charset anywhere; passing bytes must still decode "we’re".
    web.page("https://acme.com/blog/x", fixture_bytes("article.html"))
    result = methods.read_static("https://acme.com/blog/x")
    assert result.method == "static"
    assert result.title == "How We Build Data Pipelines"
    assert "we’re building" in result.markdown
    assert "[Airflow](https://acme.com/docs/airflow)" in result.markdown
    assert "Accept all cookies" not in result.markdown
    assert "Pricing" not in result.markdown


def test_static_uses_final_url_for_links(web: FakeWeb) -> None:
    web.page("https://short.link/a", fixture_bytes("article.html"), "https://acme.com/blog/x")
    result = methods.read_static("https://short.link/a")
    assert result.url == "https://short.link/a"
    assert result.final_url == "https://acme.com/blog/x"
    assert "(https://acme.com/docs/airflow)" in result.markdown


def test_full_strips_chrome_and_keeps_cards(web: FakeWeb) -> None:
    web.page("https://acme.com/about/leadership", fixture_bytes("leadership.html"))
    result = methods.read_full("https://acme.com/about/leadership")
    assert result.method == "full"
    assert result.title == "Leadership | Acme"
    for name in ("Olivia Pomeroy", "Alexis Lechner", "Priya Raman"):
        assert name in result.markdown
    assert "[Bio](https://acme.com/team/olivia)" in result.markdown
    assert "All rights reserved" not in result.markdown
    assert "[Home]" not in result.markdown


def test_full_removes_cookie_banner() -> None:
    md = convert.cleaned_full_markdown(fixture_bytes("article.html"), "https://acme.com/")
    assert "Accept all cookies" not in md
    assert "Terms of service" not in md
    assert "[open roles](https://acme.com/careers)" in md


def test_jsonld_job_posting_in_graph(web: FakeWeb) -> None:
    url = "https://jobs.ashbyhq.com/notion/x"
    web.page(url, fixture_bytes("js_shell_jsonld.html"))
    result = methods.read_jsonld(url)
    assert result.method == "jsonld"
    assert result.title == "Product Engineer"
    md = result.markdown
    assert md.startswith("# Product Engineer")
    assert "**Company:** Notion" in md
    assert "**Location:** New York, NY, US" in md
    assert "USD 150000-200000 per year" in md
    assert "[great tools](https://jobs.ashbyhq.com/notion/apply)" in md
    assert "TypeScript" in md


def test_jsonld_list_and_type_list() -> None:
    html = (
        '<script type="application/ld+json">[{"@type":"WebPage"},'
        '{"@type":["JobPosting"],"title":"Analyst","hiringOrganization":"Acme",'
        '"jobLocationType":"TELECOMMUTE","description":"<p>Do SQL</p>"}]</script>'
    )
    result = methods.jsonld_from_html("u", "https://x.com/", html)
    assert "**Company:** Acme" in result.markdown
    assert "**Location:** Remote" in result.markdown
    assert "Do SQL" in result.markdown


def test_jsonld_missing_raises_unavailable() -> None:
    with pytest.raises(MethodUnavailable):
        methods.jsonld_from_html("u", "https://x.com/", fixture_bytes("article.html"))
    bad = '<script type="application/ld+json">{not json</script>'
    with pytest.raises(MethodUnavailable):
        methods.jsonld_from_html("u", "https://x.com/", bad)


GREENHOUSE_JSON = {
    "title": "Data Analyst",
    "company_name": "Discord",
    "location": {"name": "San Francisco, CA"},
    "departments": [{"name": "Analytics"}],
    "offices": [{"name": "SF"}],
    "absolute_url": "https://job-boards.greenhouse.io/discord/jobs/123",
    "content": "&lt;p&gt;Analyze &lt;a href=&quot;/discord&quot;&gt;data&lt;/a&gt;.&lt;/p&gt;",
    "pay_input_ranges": [
        {"min_cents": 15000000, "max_cents": 20000000, "currency_type": "USD", "title": "Base"}
    ],
}


@pytest.mark.parametrize(
    "url",
    [
        "https://job-boards.greenhouse.io/discord/jobs/123",
        "https://boards.greenhouse.io/discord/jobs/123?gh_src=abc",
        "https://boards.greenhouse.io/embed/job_app?for=discord&token=123",
    ],
)
def test_greenhouse_api(web: FakeWeb, url: str) -> None:
    web.json["https://boards-api.greenhouse.io/v1/boards/discord/jobs/123"] = GREENHOUSE_JSON
    result = methods.read_greenhouse(url)
    assert result.method == "greenhouse_api"
    assert result.final_url == "https://job-boards.greenhouse.io/discord/jobs/123"
    md = result.markdown
    assert md.startswith("# Data Analyst")
    assert "**Location:** San Francisco, CA" in md
    assert "**Pay:** USD 150,000-200,000 (Base)" in md
    assert "[data](https://job-boards.greenhouse.io/discord)" in md
    assert "&lt;" not in md


def test_greenhouse_not_found_is_unavailable(web: FakeWeb) -> None:
    with pytest.raises(MethodUnavailable):
        methods.read_greenhouse("https://job-boards.greenhouse.io/discord/jobs/999")
    with pytest.raises(MethodUnavailable):
        methods.read_greenhouse("https://careers.example.com/jobs?gh_jid=1")


LEVER_JSON = {
    "text": "Data Scientist",
    "categories": {"location": "New York", "team": "Data", "commitment": "Full-time"},
    "description": "<div>Join the <b>data</b> team.</div>",
    "lists": [{"text": "What you'll do", "content": "<li>Build models</li><li>Ship</li>"}],
    "additional": "<div>We offer benefits.</div>",
    "hostedUrl": "https://jobs.lever.co/spotify/2a55d6c9-0000-4000-8000-000000000000",
    "applyUrl": "https://jobs.lever.co/spotify/2a55d6c9-0000-4000-8000-000000000000/apply",
}


def test_lever_api(web: FakeWeb) -> None:
    job = "2a55d6c9-0000-4000-8000-000000000000"
    web.json[f"https://api.lever.co/v0/postings/spotify/{job}"] = LEVER_JSON
    result = methods.read_lever(f"https://jobs.lever.co/spotify/{job}?lever-source=x")
    md = result.markdown
    assert result.method == "lever_api"
    assert result.title == "Data Scientist"
    assert "**Team:** Data" in md
    assert "## What you'll do" in md
    assert "Build models" in md
    assert "We offer benefits." in md
    assert f"**Apply:** https://jobs.lever.co/spotify/{job}/apply" in md


def test_lever_eu_host(web: FakeWeb) -> None:
    job = "2a55d6c9-0000-4000-8000-000000000000"
    web.json[f"https://api.eu.lever.co/v0/postings/acme/{job}"] = {"text": "Eng"}
    assert methods.read_lever(f"https://jobs.eu.lever.co/acme/{job}").title == "Eng"


def test_lever_urls_are_parsed_by_the_ats_layer() -> None:
    job = "2a55d6c9-0000-4000-8000-000000000000"
    assert (
        methods.lever_api_url(f"https://jobs.lever.co/spotify/{job}/apply")
        == f"https://api.lever.co/v0/postings/spotify/{job}"
    )
    for url in ("https://jobs.lever.co/spotify", "https://example.com/spotify/" + job):
        with pytest.raises(MethodUnavailable):
            methods.lever_api_url(url)


ASHBY_ID = "1fc309c8-0000-4000-8000-000000000000"
ASHBY_JSON = {
    "jobs": [
        {"id": "other", "title": "Other"},
        {
            "id": ASHBY_ID,
            "title": "Product Engineer",
            "location": "New York",
            "isRemote": False,
            "department": "Engineering",
            "employmentType": "FullTime",
            "descriptionHtml": "<p>Build <a href='/notion'>tools</a>.</p>",
            "jobUrl": f"https://jobs.ashbyhq.com/notion/{ASHBY_ID}",
            "applyUrl": f"https://jobs.ashbyhq.com/notion/{ASHBY_ID}/application",
            "compensation": {"compensationTierSummary": "$150K – $200K"},
        },
    ]
}


def test_ashby_api_caches_board(web: FakeWeb) -> None:
    web.json["https://api.ashbyhq.com/posting-api/job-board/notion"] = ASHBY_JSON
    url = f"https://jobs.ashbyhq.com/notion/{ASHBY_ID}"
    result = methods.read_ashby(url)
    assert result.method == "ashby_api"
    assert "**Compensation:** $150K – $200K" in result.markdown
    assert "[tools](https://jobs.ashbyhq.com/notion)" in result.markdown
    methods.read_ashby(url + "/application")
    assert web.calls.count(("json", "https://api.ashbyhq.com/posting-api/job-board/notion")) == 1


def test_ashby_unknown_job_is_unavailable(web: FakeWeb) -> None:
    web.json["https://api.ashbyhq.com/posting-api/job-board/notion"] = {"jobs": []}
    with pytest.raises(MethodUnavailable):
        methods.read_ashby(f"https://jobs.ashbyhq.com/notion/{ASHBY_ID}")


def test_browser_method_uses_rendered_dom(web: FakeWeb) -> None:
    url = "https://spa.example.com/job"
    web.rendered[url] = fixture_bytes("rendered.html").decode()
    result = methods.read_browser(url)
    assert result.method == "browser"
    assert "[Apply for this job](https://spa.example.com/notion/apply)" in result.markdown
    assert web.calls == [("browser", url)]


def test_looks_empty() -> None:
    assert convert.looks_empty("")
    assert convert.looks_empty("You need to enable JavaScript to run this app." * 3)
    assert not convert.looks_empty("word " * 100)


def test_prefers_full_only_when_headings_were_dropped() -> None:
    html = fixture_bytes("leadership.html")
    full = convert.cleaned_full_markdown(html, "https://acme.com/")
    assert not convert.prefers_full(full, full, html)
    assert convert.prefers_full("Meet the people who lead Acme.", full, html)


def test_prefers_full_when_names_survive_only_inside_bios() -> None:
    # Datadog case: trafilatura keeps "Olivia Pomeroy" in a bio sentence but drops the heading.
    html = fixture_bytes("leadership.html")
    full = convert.cleaned_full_markdown(html, "https://acme.com/")
    names = ["Olivia Pomeroy", "Alexis Lechner", "Dana Whitfield", "Sam Okafor", "Priya Raman"]
    bios = "\n\n".join(f"{n} joined Acme after a decade building data products." for n in names)
    assert convert.prefers_full(bios, full, html)
    as_headings = "\n\n".join(f"### {n}\n\nJoined Acme." for n in names)
    assert not convert.prefers_full(as_headings, full, html)


def test_prefers_full_ignores_articles() -> None:
    html = fixture_bytes("article.html")
    traf = convert.trafilatura_markdown(html, "https://acme.com/")
    assert not convert.prefers_full(
        traf, convert.cleaned_full_markdown(html, "https://acme.com/"), html
    )


def test_browser_worker_close_is_idempotent() -> None:
    from read_page.browser import BrowserWorker

    worker = BrowserWorker()  # never launches Chromium: nothing was rendered
    worker.close()
    worker.close()


def test_full_drops_repeated_long_paragraphs() -> None:
    bio = "<p>" + "Built data systems for teachers before founding the company. " * 3 + "</p>"
    html = f"<main><h3>A</h3>{bio}<p>CEO</p><h3>B</h3><p>CEO</p><div hidden>{bio}</div></main>"
    md = convert.cleaned_full_markdown(html, "https://acme.com/")
    assert md.count("Built data systems") == 3  # one paragraph (3 sentences), not two
    assert md.count("CEO") == 2  # short lines are never de-duplicated
