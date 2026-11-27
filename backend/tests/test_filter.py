"""The `filter` step: dedupe, location, experience and the cap, before any posting is read."""

import pytest
from pipeline_fakes import REQUEST, FakeSources, plan

import config
from pipeline import steps
from pipeline.state import Job, JobPosting
from read_page import PageResult


def job(i: int, title: str = "Data Analyst", **fields) -> Job:
    base = {
        "id": f"j{i}",
        "source": "builtin_jobs",
        "title": title,
        "url": f"https://example.com/job/{i}",
        "company": f"Co{i}",
        "location": "New York, NY",
    }
    return Job(**(base | fields))


def run_filter(jobs: list[Job], request=REQUEST, limit: int = 30):
    return steps.filter_jobs(jobs, request, ["Data Analyst"], "New York, NY", limit)


def ids(jobs: list[Job]) -> list[str]:
    return [j.id for j in jobs]


def test_same_url_and_same_company_title_and_place_are_duplicates() -> None:
    jobs = [
        job(1, company="Ramp"),
        job(2, company="Ramp", url="https://example.com/job/1/"),  # same URL
        job(3, company="Ramp Inc.", url="https://other.example/3"),  # same company + title
        job(4, company="Ramp", location="Brooklyn, NY", url="https://other.example/4"),
        job(5, company="Ramp", title="Data Analyst II", url="https://other.example/5"),
    ]
    kept, counts = run_filter([jobs[0], jobs[1], jobs[2], jobs[4]])
    assert ids(kept) == ["j1", "j5"]
    assert counts["duplicates"] == 2
    # A second location is a different job.
    assert ids(run_filter([jobs[0], jobs[3]])[0]) == ["j1", "j4"]


@pytest.mark.parametrize(
    ("location", "kept"),
    [
        ("Brooklyn, NY", True),
        ("Jersey City, NJ", True),  # NYC area
        ("Remote", True),
        ("Remote - US", True),
        ("", True),  # unknown
        ("United States", True),
        ("New York", True),
        ("San Francisco, CA", False),
        ("London, United Kingdom", False),
    ],
)
def test_jobs_far_from_the_user_are_dropped_but_remote_and_unknown_stay(
    location: str, kept: bool
) -> None:
    out, counts = run_filter([job(1, location=location)])
    assert bool(out) is kept
    assert counts["far_away"] == (0 if kept else 1)


def test_a_remote_user_keeps_every_location() -> None:
    out, _ = steps.filter_jobs(
        [job(1, location="Austin, TX")], REQUEST, ["Data Analyst"], "Remote", 30
    )
    assert ids(out) == ["j1"]


def test_user_years_come_from_the_background() -> None:
    assert steps.user_years(REQUEST) == 3
    nothing = REQUEST.model_copy(update={"background": "Biology and lab work."})
    assert steps.user_years(nothing) is None


def test_jobs_far_above_the_users_experience_are_dropped_when_it_is_known() -> None:
    jobs = [
        job(1, years_required="8+ years"),
        job(2, years_required="5+ years"),  # 2 above 3: kept
        job(3, years_required="7-10 years"),  # 4 above: dropped
        job(4),  # unknown: kept
    ]
    out, counts = run_filter(jobs)
    assert ids(out) == ["j2", "j4"]
    assert counts["too_senior"] == 2

    unknown_user = REQUEST.model_copy(update={"background": "Biology and lab work."})
    assert ids(run_filter(jobs, unknown_user)[0]) == ["j1", "j2", "j3", "j4"]


def test_the_cap_keeps_the_most_recent_best_matches_first() -> None:
    jobs = [
        job(1, title="Office Manager", posted_at="2026-11-20"),
        job(2, posted_at="2026-10-01"),
        job(3, posted_at="2026-11-10"),
        job(4, title="Senior Data Analyst", posted_at="2026-11-01"),
        job(5),  # no date: after the dated ones
    ]
    out, counts = run_filter(jobs, limit=3)
    # Title matches first, newest first among them (j3, j4, j2, j5), then the rest.
    assert ids(out) == ["j3", "j4", "j2"]
    assert counts["over_limit"] == 2


def test_filter_node_reads_only_the_survivors_and_records_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = FakeSources(monkeypatch)
    monkeypatch.setattr(config, "RANK_MAX_JOBS", 2)
    jobs = [job(1), job(2, years_required="9+ years"), job(3), job(4)]
    update = steps.filter_node({"request": REQUEST, "plan": plan(), "jobs": jobs, "trace": []})

    assert ids(update["postings"]) == ["j1", "j3"]
    assert all(isinstance(p, JobPosting) for p in update["postings"])
    # The reads run in parallel pool threads, so their order is not defined: compare sorted.
    assert sorted(u for k, u in sources.calls if k == "read_page") == [
        "https://example.com/job/1",
        "https://example.com/job/3",
    ]
    first = update["trace"][0]
    assert (first.step, first.count) == ("filter", 2)
    assert first.args["too_senior"] == 1 and first.args["over_limit"] == 1
    assert "error" not in update


def test_filter_node_drops_jobs_whose_posting_shows_far_more_experience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeSources(monkeypatch)

    def read(url: str, max_chars: int = 0) -> PageResult:
        text = "## Requirements\n- 10+ years of experience in analytics" if "/1" in url else "x"
        return PageResult(url=url, final_url=url, method="static", markdown=text)

    monkeypatch.setattr(steps.tools, "read_page", read)
    update = steps.filter_node(
        {"request": REQUEST, "plan": plan(), "jobs": [job(1), job(2)], "trace": []}
    )
    assert ids(update["postings"]) == ["j2"]
    assert update["trace"][-1].args == {"stage": "completed", "too_senior": 1}


def test_filter_node_errors_when_nothing_is_left(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSources(monkeypatch)
    jobs = [job(1, location="Tokyo, Japan")]
    update = steps.filter_node({"request": REQUEST, "plan": plan(), "jobs": jobs, "trace": []})
    assert "No job postings were left" in update["error"]
