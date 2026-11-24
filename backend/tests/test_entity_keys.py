import json

import pytest

from entities import keys
from schemas import CompanyResult, JobResult, PersonResult, SearchResults


def _job(url: str = "", title: str = "Data Analyst") -> JobResult:
    return JobResult(title=title, url=url, location="", salary="", alignment="a")


def _person(url: str = "", name: str = "Jane Doe") -> PersonResult:
    return PersonResult(name=name, title="", profile_url=url, alignment="a")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://www.Example.com/jobs/123/?utm_source=x&gclid=1&b=2&a=1#apply",
            "example.com/jobs/123?a=1&b=2",
        ),
        ("http://example.com:80/jobs/123", "example.com/jobs/123"),
        ("https://example.com:8443//jobs//123", "example.com:8443/jobs/123"),
        (
            "https://boards.greenhouse.io/acme/jobs/42?gh_src=abc&gh_jid=42",
            "boards.greenhouse.io/acme/jobs/42?gh_jid=42",
        ),
        (
            "https://www.linkedin.com/jobs/view/data-analyst-at-acme-3812345678/?refId=x&trk=y",
            "linkedin.com/jobs/view/3812345678",
        ),
        ("https://uk.linkedin.com/jobs/view/3812345678", "linkedin.com/jobs/view/3812345678"),
        (
            "https://www.linkedin.com/jobs/search/?currentJobId=3812345678&keywords=data",
            "linkedin.com/jobs/view/3812345678",
        ),
        (
            "https://www.linkedin.com/in/Jane-Doe-42/?originalSubdomain=uk",
            "linkedin.com/in/jane-doe-42",
        ),
        (
            "https://www.indeed.com/viewjob?jk=ABC123&from=serp&vjs=3",
            "indeed.com/viewjob?jk=abc123",
        ),
        ("https://www.indeed.com/jobs?q=data&vjk=abc123", "indeed.com/viewjob?jk=abc123"),
    ],
)
def test_normalize_url(url: str, expected: str) -> None:
    assert keys.normalize_url(url) == expected


@pytest.mark.parametrize(
    "url", ["", "u", "not a url", "mailto:a@b.com", "ftp://x.com/a", "http://", "http://[::1"]
)
def test_normalize_url_rejects_non_http(url: str) -> None:
    assert keys.normalize_url(url) is None


def test_job_key_ignores_tracking_and_scheme_differences() -> None:
    first = keys.job_key(_job("https://www.acme.com/careers/123?utm_campaign=a"), "Acme")
    second = keys.job_key(_job("http://acme.com/careers/123/#top"), "ACME Inc.")
    assert first == second == "job:url:acme.com/careers/123"


def test_job_key_falls_back_to_company_and_title() -> None:
    first = keys.job_key(_job("", "Data  Analyst"), "Acme, Inc.")
    second = keys.job_key(_job("n/a", "data analyst"), "acme")
    assert first == second == "job:name:acme|data analyst"
    assert keys.job_key(_job("", "PM"), "Acme") != first


def test_person_key_uses_linkedin_slug() -> None:
    first = keys.person_key(_person("https://www.linkedin.com/in/jane-doe-42?trk=people"), "Acme")
    second = keys.person_key(_person("https://de.linkedin.com/in/Jane-Doe-42/", "J. Doe"), "Other")
    assert first == second == "person:linkedin:jane-doe-42"


def test_person_key_other_url_and_name_fallback() -> None:
    assert keys.person_key(_person("https://janedoe.dev/about/"), "Acme") == (
        "person:url:janedoe.dev/about"
    )
    assert keys.person_key(_person("", "José  Núñez"), "Acme LLC") == (
        "person:name:jose nunez|acme"
    )


def test_company_key_strips_legal_suffixes() -> None:
    assert keys.company_key("Acme, Inc.") == keys.company_key("ACME") == "company:name:acme"
    assert keys.company_key("Co") == "company:name:co"


def test_annotate_fills_keys_without_mutating() -> None:
    results = SearchResults(
        summary="s",
        companies=[
            CompanyResult(
                name="Acme",
                url="",
                description="d",
                alignment="a",
                jobs=[_job("https://acme.com/j/1")],
                people=[_person("https://linkedin.com/in/jane")],
            )
        ],
    )
    annotated = keys.annotate(results)
    assert annotated.companies[0].key == "company:name:acme"
    assert annotated.companies[0].jobs[0].key == "job:url:acme.com/j/1"
    assert annotated.companies[0].people[0].key == "person:linkedin:jane"
    assert results.companies[0].jobs[0].key == ""
    assert results.companies[0].key == ""


def test_llm_schema_does_not_expose_key() -> None:
    schema = json.dumps(SearchResults.model_json_schema())
    assert '"key"' not in schema
    assert '"profile_url"' in schema
