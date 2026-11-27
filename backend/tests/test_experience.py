"""`experience.years_required` and how it reaches the ranking step's job table."""

import pytest

import tools
from ats.ashby import Ashby
from ats.lever import Lever
from experience import years_required
from pipeline import steps


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5+ years of experience building backend systems", "5+ years"),
        ("3-5 years experience", "3-5 years"),
        ("3 to 5 years of relevant experience", "3-5 years"),
        ("7–10 yrs", "7-10 years"),
        ("Minimum of two years of professional experience", "2+ years"),
        ("You have 4 years of hands-on product management experience", "4+ years"),
        ("at least 1 year of specialized experience", "1+ year"),
        ("0 - 1 year", "0-1 years"),
        # The smallest minimum wins, so a job never looks more senior than its text says.
        ("2+ years Python; 5+ years overall", "2+ years"),
        # Not requirements.
        ("We have been building for 40 years", ""),
        ("Join us for a 2 year rotational program", ""),
        ("New grads welcome", ""),
        ("", ""),
    ],
)
def test_years_required(text: str, expected: str) -> None:
    assert years_required(text) == expected


def test_lever_reads_years_from_description_and_lists() -> None:
    raw = {
        "id": "a1",
        "text": "Data Analyst",
        "hostedUrl": "https://jobs.lever.co/acme/a1",
        "descriptionPlain": "Join our team.",
        "lists": [{"text": "Requirements", "content": "<li>3+ years of SQL experience</li>"}],
    }
    job = Lever()._job("acme", "Acme", raw)
    assert job is not None and job.years_required == "3+ years"


def test_ashby_reads_years_from_description() -> None:
    raw = {"id": "b2", "title": "Engineer", "descriptionPlain": "5+ years of Go experience."}
    job = Ashby()._job("acme", "Acme", raw)
    assert job is not None and job.years_required == "5+ years"


def test_years_and_level_reach_the_job_table() -> None:
    builtin = steps._job_from(
        "builtin_jobs",
        {
            "title": "Analyst",
            "url": "u1",
            "experience_level": "Senior",
            "years_required": "6+ years",
        },
    )
    google = steps._job_from(
        "google_search",
        {"title": "Junior Analyst", "url": "u2", "snippet": "1-2 years of experience required"},
    )
    builtin.id, google.id = "j1", "j2"
    table = steps._jobs_table([builtin, google])
    assert '"level": "Senior"' in table
    assert '"years_required": "6+ years"' in table
    assert '"years_required": "1-2 years"' in table


def test_conservation_experience_becomes_years(monkeypatch: pytest.MonkeyPatch) -> None:
    class Posting:
        title, url, organization, location = "Tech", "u", "Org", "CO"
        job_type, salary, deadline, posted = "Seasonal", None, None, None
        experience = "0 - 1 year"

    monkeypatch.setattr(tools.conservation_api, "get_jobs", lambda *_: [Posting()])
    (job,) = tools.conservation_jobs(None)  # type: ignore[arg-type]
    assert job["years_required"] == "0-1 years"
