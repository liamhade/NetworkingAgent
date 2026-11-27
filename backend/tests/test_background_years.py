"""`user_years`: experience from a free-text background, with an injected clock."""

from datetime import date

import pytest

from pipeline import steps
from schemas import SearchRequest

TODAY = date(2026, 11, 27)


def years(background: str) -> int | None:
    request = SearchRequest(background=background, location="NYC", looking_for="x")
    return steps.user_years(request, today=TODAY)


def test_a_stated_amount_still_counts() -> None:
    assert years("I am a data analyst with 3 years of SQL.") == 3
    assert years("5+ yrs of Java and 2 years of Go.") == 5


def test_one_recent_job_and_a_graduation_is_about_one_year() -> None:
    assert years("Software Engineer, Nov 2025 – present.\nGraduated June 2025 from Cornell.") == 1


def test_work_ranges_are_summed_without_double_counting_overlaps() -> None:
    background = (
        "Analyst at Acme, Jan 2021 - Dec 2022\n"
        "Consultant at Beta, June 2022 - June 2024\n"
        "Engineer at Gamma, 2025 - present\n"
    )
    # Jan 2021 -> Jun 2024 (41 months) + Jul 2025 -> Nov 2026 (16 months) = 57 months.
    assert years(background) == 4


def test_student_roles_and_degrees_do_not_count() -> None:
    background = (
        "B.S. Computer Science, Cornell University, Aug 2021 - May 2025\n"
        "Software Engineering Intern at Acme, Jun 2024 - Aug 2024\n"
        "Teaching Assistant, Sep 2022 - May 2024\n"
    )
    assert years(background) == 0  # student signals, no work range


def test_a_title_on_the_line_before_the_dates_is_read() -> None:
    assert years("Data Science Intern\nJune 2025 - Aug 2025\nGraduated May 2025") == 0
    assert years("Backend Engineer\nMar 2023 - Mar 2026") == 3


def test_a_future_or_open_end_is_capped_at_today() -> None:
    assert years("Engineer, Nov 2025 - present") == 1
    assert years("Engineer, Nov 2024 - Dec 2030") == 2


def test_new_graduate_or_student_wording_is_no_experience() -> None:
    assert years("Recent graduate in biology.") == 0
    assert years("Senior at NYU studying statistics, class of 2027.") == 0


def test_no_signal_is_unknown() -> None:
    assert years("Biology and lab work.") is None


def test_filter_uses_the_dated_background_to_drop_far_too_senior_jobs() -> None:
    from pipeline.state import Job

    job = Job(id="j1", source="x", title="Staff", url="https://e.com/1", years_required="8+ years")
    assert steps.filter.too_senior(job, years("Engineer, Nov 2025 - present")) is True
    assert steps.filter.too_senior(job, years("Biology and lab work.")) is False


@pytest.mark.parametrize("text", [" ", "Worked 2019", "from 2024 to"])
def test_odd_text_does_not_crash(text: str) -> None:
    assert years(text) is None
