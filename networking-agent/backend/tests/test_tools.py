import pytest

import tools
from builtin_nyc.models import Company, CompanyFilter, ExperienceLevel, Job, JobCategory, JobFilter
from conservation_jobboard.models import Category, Location
from conservation_jobboard.models import Job as ConservationJob
from conservation_jobboard.models import JobFilter as ConservationJobFilter
from google_serp import SearchResponse, SearchResult


def _job(i: int) -> Job:
    return Job(
        id=i,
        title=f"Data Analyst {i}",
        url=f"https://www.builtinnyc.com/job/{i}",
        company_name="Acme",
        company_url="https://www.builtinnyc.com/company/acme",
        location="New York, NY",
        salary="100K-120K Annually",
        skills=["SQL", "Python"],
        description="x" * 1000,
    )


def test_search_builtin_jobs_builds_filter_and_clips(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_jobs(job_filter, n):
        seen["filter"], seen["n"] = job_filter, n
        return [_job(1), _job(2)]

    monkeypatch.setattr(tools.builtin_api, "get_jobs", fake_get_jobs)
    out = tools.builtin_jobs(
        JobFilter(
            search="analyst",
            category=JobCategory.DATA_ANALYTICS,
            experience_levels=[ExperienceLevel.JUNIOR],
        ),
        n=2,
    )
    assert seen["n"] == 2
    assert seen["filter"].search == "analyst"
    assert seen["filter"].category == JobCategory.DATA_ANALYTICS
    assert seen["filter"].experience_levels == [ExperienceLevel.JUNIOR]
    assert [j["url"] for j in out] == [
        "https://www.builtinnyc.com/job/1",
        "https://www.builtinnyc.com/job/2",
    ]
    assert len(out[0]["summary"]) <= tools.MAX_TEXT


def test_search_builtin_companies(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_companies(company_filter, n):
        assert company_filter.industries == ["fintech"]
        assert company_filter.hiring_only is True
        return [Company(id=1, name="Ramp", url="https://www.builtinnyc.com/company/ramp")]

    monkeypatch.setattr(tools.builtin_api, "get_companies", fake_get_companies)
    out = tools.builtin_companies(CompanyFilter(industries=["fintech"], hiring_only=True))
    assert out[0]["name"] == "Ramp"


def test_source_errors_are_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_):
        raise RuntimeError("404 Not Found")

    monkeypatch.setattr(tools.builtin_api, "get_companies", boom)
    with pytest.raises(RuntimeError, match="404"):
        tools.builtin_companies(CompanyFilter(industries=["nope"]))


def _serp(*results):
    return SearchResponse(results=[SearchResult(**r) for r in results])


def test_google_search(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tools,
        "run_google_search",
        lambda q, pick=None: _serp(
            {
                "title": "Jobs",
                "url": "https://boards.greenhouse.io/x",
                "site_name": "Greenhouse",
                "snippet": "Apply",
            }
        ),
    )
    out = tools.google_search("analyst jobs")
    assert out == [
        {
            "title": "Jobs",
            "url": "https://boards.greenhouse.io/x",
            "site": "Greenhouse",
            "snippet": "Apply",
        }
    ]


def test_google_errors_are_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(q, pick=None):
        raise RuntimeError("Chrome not found")

    monkeypatch.setattr(tools, "run_google_search", boom)
    with pytest.raises(RuntimeError, match="Chrome not found"):
        tools.google_search("x")


def test_search_conservation_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_jobs(job_filter, n):
        seen["filter"], seen["n"] = job_filter, n
        return [
            ConservationJob(
                id=1,
                title="Wildlife Technician",
                url="https://www.conservationjobboard.com/job-listing-wildlife-technician/123",
                organization="Audubon",
                location="Denver, CO",
                job_type="Temporary",
                salary="$20 - $22 per hour",
            )
        ]

    monkeypatch.setattr(tools.conservation_api, "get_jobs", fake_get_jobs)
    out = tools.conservation_jobs(
        ConservationJobFilter(
            keyword="wildlife",
            categories=[Category.WILDLIFE],
            locations=[Location.COLORADO, Location.REMOTE],
        )
    )
    assert seen["n"] == 15
    assert seen["filter"].categories == [Category.WILDLIFE]
    assert seen["filter"].locations == [Location.COLORADO, Location.REMOTE]
    assert out == [
        {
            "title": "Wildlife Technician",
            "url": "https://www.conservationjobboard.com/job-listing-wildlife-technician/123",
            "company": "Audubon",
            "location": "Denver, CO",
            "job_type": "Temporary",
            "salary": "$20 - $22 per hour",
            "experience": None,
            "deadline": None,
            "posted": None,
        }
    ]


def test_search_conservation_jobs_errors_are_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_):
        raise RuntimeError("403 Forbidden")

    monkeypatch.setattr(tools.conservation_api, "get_jobs", boom)
    with pytest.raises(RuntimeError, match="403"):
        tools.conservation_jobs(ConservationJobFilter(keyword="x"))
