"""LinkedIn people search: query building, profile filtering, parsing, and the tool (no network).

The result shapes are copied from live Google results pages (Nov 2026).
"""

import pytest

import linkedin
import tools
from google_serp import SearchResponse, SearchResult

GOTO = "https://www.google.com/goto?url=abc"


def _r(title: str, site: str, display: str = "", snippet: str = "", url: str = GOTO):
    return SearchResult(
        title=title,
        url=url,
        display_url=display,
        snippet=snippet,
        site_name=site,
        google_url=GOTO if url == GOTO else "",
    )


PROFILE = _r(
    "Shreya Rao - Data at Ramp",
    "LinkedIn · Shreya Rao",
    snippet="New York, New York, United States · Data Scientist · Ramp Data at Ramp · I illustrate"
    " and explain Machine Learning algorithms",
)
FORMER = _r(
    "Dianna Chen - Strategy & Ops @ Profound | Ex-Ramp",
    "LinkedIn · Dianna Chen",
    snippet="New York, New York, United States · GTM Strategy & Operations · Profound Ramp .",
)
EXPERIENCE_ONLY = _r(
    "Sophie O. - Datadog",
    "LinkedIn · Sophie O.",
    snippet="New York, New York, United States · Datadog Experience: Datadog · Education: Bucknell"
    " University · Location: New York",
)
COUNTRY_SUBDOMAIN = _r(
    "hamesh raj - Data Analyst at Notion", "LinkedIn", display="https://in.linkedin.com › ..."
)
POST = _r("Ian Macomber's Post", "LinkedIn · Ian Macomber")
ARTICLE = _r("Inside Ramp's Modern Data &… | Ricky K.", "LinkedIn · Ricky K.")
LINKEDIN_JOB = _r(
    "Customer Experience Associate (Evening Shift) at Ramp",
    "LinkedIn",
    display="https://www.linkedin.com › jobs › view › customer-expe...",
)
LINKEDIN_JOB_ELIDED = _r(
    "Tech Lead, Ramp Travel at Ramp — New York, NY",
    "LinkedIn",
    display="https://www.linkedin.com › ... › Lead Therapist jobs",
)
JOB_LIST = _r(
    "Ramp Jobs in New York (7000+ Open Roles)",
    "LinkedIn",
    display="https://www.linkedin.com › jobs › ramp-jobs-new-york-ny",
)
JOB_BOARD = _r(
    "60 Data Jobs Hiring at Ramp 1-Click Apply Now",
    "ZipRecruiter",
    display="https://www.ziprecruiter.com › ramp › Jobs › Data",
)


# ------------------------------------------------------------------- query building


def test_build_query_puts_site_operator_first_and_quotes_company() -> None:
    assert (
        linkedin.build_query("Ramp", "data analyst", "New York")
        == 'site:linkedin.com/in "Ramp" data analyst New York'
    )


def test_build_query_without_location_and_with_stray_quotes() -> None:
    assert (
        linkedin.build_query(' "Ramp" ', " recruiter ") == 'site:linkedin.com/in "Ramp" recruiter'
    )


def test_retry_query_moves_operator_to_the_end() -> None:
    assert (
        linkedin.retry_query("Datadog", "recruiter", "New York")
        == '"Datadog" recruiter New York site:linkedin.com/in'
    )


# ------------------------------------------------------------------------- filtering


@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/in/shreya-rao",
        "https://in.linkedin.com/in/hamesh-raj-123",
        "http://linkedin.com/in/x?trk=y",
    ],
)
def test_is_profile_url(url: str) -> None:
    assert linkedin.is_profile_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/jobs/view/123",
        "https://www.linkedin.com/posts/ian_abc",
        "https://www.linkedin.com/company/ramp",
        "https://www.linkedin.com/in/",
        "https://notlinkedin.com/in/x",
        "https://www.glassdoor.com/in/x",
    ],
)
def test_is_not_profile_url(url: str) -> None:
    assert not linkedin.is_profile_url(url)


EN_DASH = _r("Denis Chernilevskiy – Senior IT Manager", "LinkedIn · Denis Chernilevskiy")
NAME_ONLY = _r("Pat Lee", "LinkedIn · Pat Lee")


@pytest.mark.parametrize(
    "result", [PROFILE, FORMER, EXPERIENCE_ONLY, COUNTRY_SUBDOMAIN, EN_DASH, NAME_ONLY]
)
def test_unresolved_profiles_are_recognised(result: SearchResult) -> None:
    assert linkedin.looks_like_profile(result)


@pytest.mark.parametrize(
    "result", [POST, ARTICLE, LINKEDIN_JOB, LINKEDIN_JOB_ELIDED, JOB_LIST, JOB_BOARD]
)
def test_non_profiles_are_rejected(result: SearchResult) -> None:
    assert not linkedin.looks_like_profile(result)


def test_resolved_links_are_checked_strictly() -> None:
    profile = _r(PROFILE.title, PROFILE.site_name, url="https://www.linkedin.com/in/shreya")
    job = _r(PROFILE.title, PROFILE.site_name, url="https://www.linkedin.com/jobs/view/1")
    assert linkedin.looks_like_profile(profile)
    assert not linkedin.looks_like_profile(job)


def test_operator_ignored_when_most_results_are_off_linkedin() -> None:
    assert linkedin.operator_ignored([JOB_LIST, JOB_BOARD, JOB_BOARD, JOB_BOARD])
    assert not linkedin.operator_ignored([PROFILE, FORMER, POST, JOB_BOARD])
    assert not linkedin.operator_ignored([])


# --------------------------------------------------------------------------- parsing


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Jane Doe - Engineer - Acme | LinkedIn", ("Jane Doe", "Engineer - Acme")),
        ("John Smith · LinkedIn", ("John Smith", "")),
        ("Ana Li - Recruiter", ("Ana Li", "Recruiter")),
        ("Beata Sterner – Talangjägarna AB", ("Beata Sterner", "Talangjägarna AB")),
        ("Jean-Luc Picard - Captain", ("Jean-Luc Picard", "Captain")),
    ],
)
def test_parse_linkedin_title(title: str, expected: tuple[str, str]) -> None:
    assert linkedin.parse_linkedin_title(title) == expected


def test_parse_profile_from_snippet() -> None:
    assert linkedin.parse_profile(PROFILE, "Ramp") == {
        "name": "Shreya Rao",
        "headline": "Data at Ramp",
        "title": "Data Scientist",
        "company": "Ramp",
        "at_company": True,
        "location": "New York, New York, United States",
        "url": GOTO,
    }


def test_parse_profile_former_employee() -> None:
    person = linkedin.parse_profile(FORMER, "Ramp")
    assert person["company"] == "Profound"
    assert person["at_company"] is False


def test_parse_profile_experience_field_and_no_title() -> None:
    person = linkedin.parse_profile(EXPERIENCE_ONLY, "Datadog")
    assert (person["title"], person["company"], person["at_company"]) == ("", "Datadog", True)


def test_parse_profile_headline_only() -> None:
    result = _r(
        "Alex R. - Technical Recruiter | Datadog | We're Hiring! # ...",
        "LinkedIn · Alex R.",
        snippet="Technical Recruiter | Datadog | We're Hiring! #DatadogLife · Education: X",
    )
    person = linkedin.parse_profile(result, "Datadog")
    assert person["name"] == "Alex R."
    assert person["headline"].endswith("…")
    assert person["at_company"] is True


def test_surname_matching_company_is_not_an_employee() -> None:
    result = _r(
        "Demyre Ramp - Data Analyst | M.S. in Business Analytics",
        "LinkedIn · Demyre Ramp",
        snippet="Akron, Ohio, United States · Data Analytics Intern · Acme Corp Data Analyst",
    )
    assert linkedin.parse_profile(result, "Ramp")["at_company"] is False


def test_similar_company_name_is_not_a_match() -> None:
    result = _r(
        "Pat Lee - Analyst",
        "LinkedIn · Pat Lee",
        snippet="Boston, Massachusetts, United States · Analyst · Rampart Security Analyst",
    )
    assert linkedin.parse_profile(result, "Ramp")["at_company"] is False


@pytest.mark.parametrize(
    ("company", "expected"),
    [
        (
            "U.S. Department of Agriculture (USDA)",
            ["us department of agriculture usda", "us department of agriculture", "usda"],
        ),
        ("Artefact (artefact.com)", ["artefact artefact com", "artefact"]),
        ("Acme (formerly Widget Co)", ["acme formerly widget co", "acme"]),
        ("Ramp", ["ramp"]),
    ],
)
def test_company_aliases(company: str, expected: list[str]) -> None:
    assert linkedin.company_aliases(company) == expected


@pytest.mark.parametrize(
    "headline",
    [
        "Management Analyst @ USDA-Food Safety Inspection",
        "Research Technician at US Department of Agriculture",
        "Research Technician at U.S. Department of Agriculture",
    ],
)
def test_agency_acronyms_and_us_spelling_match(headline: str) -> None:
    result = _r(f"Sam Doe - {headline}", "LinkedIn · Sam Doe", snippet=headline)
    person = linkedin.parse_profile(result, "U.S. Department of Agriculture (USDA)")
    assert person["at_company"] is True


def test_alias_in_snippet_company_slot() -> None:
    result = _r(
        "Sam Doe - Biologist",
        "LinkedIn · Sam Doe",
        snippet="Fort Collins, Colorado, United States · Biologist · USDA-APHIS Wildlife work",
    )
    person = linkedin.parse_profile(result, "U.S. Department of Agriculture (USDA)")
    assert (person["company"], person["at_company"]) == (
        "U.S. Department of Agriculture (USDA)",
        True,
    )


def test_former_employee_by_acronym() -> None:
    result = _r("Sam Doe - Analyst, ex-USDA", "LinkedIn · Sam Doe", snippet="Analyst, ex-USDA")
    assert (
        linkedin.parse_profile(result, "U.S. Department of Agriculture (USDA)")["at_company"]
        is False
    )


# ------------------------------------------------------------------- tools.linkedin_people


def _resolved(result: SearchResult, url: str) -> SearchResult:
    return SearchResult(**{**result.__dict__, "url": url})


class FakeGoogle:
    """Stands in for tools.run_google_search; serves one page per call."""

    def __init__(self, *pages: list[SearchResult], resolve: dict[str, str] | None = None):
        self.pages = list(pages)
        self.resolve = resolve or {}
        self.queries: list[str] = []
        self.cacheable: list[bool] = []

    def __call__(self, query, pick=None, cacheable=None):
        self.queries.append(query)
        page = SearchResponse(results=self.pages.pop(0))
        self.cacheable.append(cacheable(page) if cacheable else True)
        chosen = pick(list(page.results)) if pick else list(page.results)
        return SearchResponse(
            results=[_resolved(r, self.resolve.get(r.title, r.url)) for r in chosen]
        )


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "LINKEDIN_RETRY_DELAY_S", 0)


def test_tool_returns_only_profiles_current_employees_first(monkeypatch) -> None:
    google = FakeGoogle(
        [FORMER, JOB_BOARD, PROFILE, POST, LINKEDIN_JOB, EXPERIENCE_ONLY],
        resolve={
            FORMER.title: "https://www.linkedin.com/in/dianna",
            PROFILE.title: "https://www.linkedin.com/in/shreya",
        },
    )
    monkeypatch.setattr(tools, "run_google_search", google)
    out = tools.linkedin_people("Ramp", "data analyst", "New York", n=2)
    assert google.queries == ['site:linkedin.com/in "Ramp" data analyst New York']
    assert google.cacheable == [True]
    assert [(p["name"], p["at_company"], p["url"]) for p in out] == [
        ("Shreya Rao", True, "https://www.linkedin.com/in/shreya"),
        ("Dianna Chen", False, "https://www.linkedin.com/in/dianna"),
    ]
    assert out[0]["snippet"].startswith("New York")


def test_tool_drops_results_that_resolve_off_profile(monkeypatch) -> None:
    google = FakeGoogle([PROFILE], resolve={PROFILE.title: "https://www.linkedin.com/posts/x"})
    monkeypatch.setattr(tools, "run_google_search", google)
    assert tools.linkedin_people("Ramp", "x") == []


def test_tool_retries_when_google_ignores_site_operator(monkeypatch) -> None:
    google = FakeGoogle([JOB_LIST, JOB_BOARD, JOB_BOARD], [PROFILE])
    monkeypatch.setattr(tools, "run_google_search", google)
    out = tools.linkedin_people("Ramp", "data analyst")
    assert google.queries == [
        'site:linkedin.com/in "Ramp" data analyst',
        '"Ramp" data analyst site:linkedin.com/in',
    ]
    assert google.cacheable == [False, True]  # the ignored page isn't cached
    assert [p["name"] for p in out] == ["Shreya Rao"]


def test_tool_reports_when_google_keeps_ignoring_operator(monkeypatch) -> None:
    google = FakeGoogle([JOB_LIST, JOB_BOARD, JOB_BOARD], [JOB_BOARD, JOB_BOARD])
    monkeypatch.setattr(tools, "run_google_search", google)
    with pytest.raises(tools.OperatorIgnoredError, match="job listings instead of LinkedIn"):
        tools.linkedin_people("Ramp", "x")
    assert len(google.queries) == 2


def test_tool_returns_errors(monkeypatch) -> None:
    def boom(query, pick=None, cacheable=None):
        raise RuntimeError("Chrome not found")

    monkeypatch.setattr(tools, "run_google_search", boom)
    with pytest.raises(RuntimeError, match="Chrome not found"):
        tools.linkedin_people("Ramp", "x")


def test_build_query_with_school_quotes_it_after_the_company() -> None:
    assert (
        linkedin.build_query("Ramp", "data analyst", "New York", "Cornell University")
        == 'site:linkedin.com/in "Ramp" "Cornell University" data analyst New York'
    )
    assert (
        linkedin.retry_query("Ramp", "", "", ' "Cornell" ')
        == '"Ramp" "Cornell" site:linkedin.com/in'
    )


def test_build_query_without_school_is_unchanged() -> None:
    assert linkedin.build_query("Ramp", "recruiter", "", "  ") == (
        'site:linkedin.com/in "Ramp" recruiter'
    )


def test_mentions_school_needs_the_whole_name_in_headline_or_snippet() -> None:
    person = {"headline": "Analyst at Ramp", "snippet": "Cornell University · Economics"}
    assert linkedin.mentions_school(person, "Cornell University")
    assert linkedin.mentions_school(person, "cornell university")
    assert not linkedin.mentions_school(person, "Columbia University")
    assert not linkedin.mentions_school({"headline": "x", "snippet": ""}, "Cornell")
    assert not linkedin.mentions_school(person, "")
