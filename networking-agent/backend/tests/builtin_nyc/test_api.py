"""Offline tests for the BuiltInNYC API (URL building and HTML parsing)."""

from pathlib import Path

from bs4 import BeautifulSoup

from builtin_nyc import api
from builtin_nyc.models import (
    CompanyFilter,
    CompanySize,
    ExperienceLevel,
    JobCategory,
    JobFilter,
    RemotePreference,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _soup(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "html.parser")


def test_job_path_default() -> None:
    assert api._job_path_and_params(JobFilter()) == ("/jobs", {})


def test_job_path_with_filters() -> None:
    job_filter = JobFilter(
        search="python",
        category=JobCategory.ENGINEERING,
        subcategories=["software-engineering"],
        remote_preferences=[RemotePreference.HYBRID],
        experience_levels=[ExperienceLevel.SENIOR],
        industries=["fintech"],
        company_sizes=[CompanySize.S_51_200],
        posted_within_days=7,
        early_applicant=True,
    )
    path, params = api._job_path_and_params(job_filter)
    assert path == "/jobs/hybrid/engineering/software-engineering/senior/fintech/51-200"
    assert params == {"search": "python", "daysSinceUpdated": "7", "earlyApplicant": "true"}


def test_job_skills_ignored_without_search_or_category() -> None:
    assert api._job_path_and_params(JobFilter(skills=["Python"]))[1] == {}
    assert api._job_path_and_params(JobFilter(search="x", skills=["Python", "SQL"]))[1] == {
        "search": "x",
        "skills": "Python,SQL",
    }


def test_company_path() -> None:
    company_filter = CompanyFilter(
        hiring_only=True,
        industries=["fintech"],
        sizes=[CompanySize.S_1_10, CompanySize.S_11_50],
        tech_stack=["python"],
    )
    path, _ = api._company_path_and_params(company_filter)
    assert path == (
        "/companies/hiring/open-jobs/type/fintech-companies/size/1-10/11-50/tech/python-companies"
    )


def test_parse_jobs() -> None:
    jobs = api._parse_jobs(_soup("jobs.html"))
    assert len(jobs) == 2
    job = jobs[0]
    assert job.id > 0 and job.title and job.company_name
    assert job.url.startswith("https://www.builtinnyc.com/job/")
    assert job.location and job.work_arrangement and job.experience_level
    assert job.industries and job.description


def test_parse_companies() -> None:
    companies = api._parse_companies(_soup("companies.html"))
    assert len(companies) == 2
    company = companies[0]
    assert company.id > 0 and company.name
    assert company.url.startswith("https://www.builtinnyc.com/company/")
    assert company.industries and company.employee_count
