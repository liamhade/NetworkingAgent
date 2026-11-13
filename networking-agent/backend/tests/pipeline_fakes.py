"""Fake job sources, LinkedIn search and LLM answers for pipeline tests (no network)."""

import re
from typing import Any

import pytest

import tools
from pipeline.state import (
    BuiltinJobQuery,
    CompanyRanking,
    JobScore,
    PeopleNotes,
    RankedCompany,
    SearchPlan,
)
from read_page import PageResult
from schemas import CompanyResult, JobResult, PersonResult, SearchRequest, SearchResults

REQUEST = SearchRequest(
    background="I am a data analyst with 3 years of SQL and Python.",
    location="New York, NY",
    looking_for="Senior data analyst roles in fintech",
)

COMPANIES = ["Ramp", "Notion", "Datadog", "Etsy", "Plaid"]


def job_url(i: int) -> str:
    return f"https://www.builtinnyc.com/job/{i}"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "anyone"


def profile(company: str, keywords: str, i: int = 0, at_company: bool = True) -> dict[str, Any]:
    name = f"{company} {slug(keywords).title()} {i}"
    return {
        "name": name,
        "headline": f"Works at {company}",
        "title": keywords.title() or "Staff",
        "company": company if at_company else "Elsewhere",
        "at_company": at_company,
        "location": "New York",
        "url": f"https://www.linkedin.com/in/{slug(company)}-{slug(keywords)}-{i}",
        "snippet": "",
    }


def plan(**changes: Any) -> SearchPlan:
    base = SearchPlan(
        role_titles=["Data Analyst", "Analytics Engineer"],
        seniority="mid level",
        industries=["fintech"],
        location="New York, NY",
        people_location="New York",
        builtin_jobs=[
            BuiltinJobQuery(
                search="data analyst", category=None, experience_levels=[], remote_preferences=[]
            )
        ],
        builtin_companies=[],
        conservation_jobs=[],
        ats_jobs=[],
        google_queries=[],
    )
    return base.model_copy(update=changes)


def ranking(*companies: tuple[str, int, list[tuple[str, int]]]) -> CompanyRanking:
    """`("Ramp", 90, [("j1", 80)])`, ... -> CompanyRanking (keywords: "data manager")."""
    return CompanyRanking(
        companies=[
            RankedCompany(
                name=name,
                score=score,
                reason=f"{name} fits.",
                jobs=[JobScore(id=i, score=s) for i, s in jobs],
                people_keywords=["data manager"],
            )
            for name, score, jobs in companies
        ]
    )


DEFAULT_RANKING = ranking(*[(c, 90 - 10 * i, [(f"j{i + 1}", 80)]) for i, c in enumerate(COMPANIES)])


def compiled(found: dict[str, list[dict]] | None = None) -> SearchResults:
    """What a well-behaved compile step writes for the default fakes: every company, its
    job, and the people `found` there (by company name)."""
    found = found or {}
    return SearchResults(
        summary="Fintech data roles in NYC.",
        companies=[
            CompanyResult(
                name=c,
                url=f"https://www.builtinnyc.com/company/{slug(c)}",
                description=f"{c} is a company.",
                alignment="You fit.",
                jobs=[
                    JobResult(
                        title=f"Data Analyst at {c}",
                        url=job_url(i + 1),
                        location="New York, NY",
                        salary="",
                        alignment="Matches your SQL.",
                    )
                ],
                people=[
                    PersonResult(
                        name=p["name"],
                        title=p["title"],
                        profile_url=p["url"],
                        alignment="You both do data.",
                        connect_message=f"Hi {p['name'].split()[0]}, would love to connect.",
                    )
                    for p in found.get(c, [])
                ],
            )
            for i, c in enumerate(COMPANIES)
        ],
    )


def notes_for(people: list[dict]) -> PeopleNotes:
    return PeopleNotes(
        people=[
            PersonResult(
                name=p["name"],
                title=p["title"],
                profile_url=p["url"],
                alignment="You share a data background.",
                connect_message="Hi, would love to connect about your team.",
            )
            for p in people
        ]
    )


class FakeSources:
    """Patches the `tools` source functions. Records every call.

    `jobs`: BuiltIn jobs returned for every query (default: one job per company).
    `people`: `{(company, keywords): list[profile] | Exception}`; anything else returns
    `default_people` profiles (all current employees).
    `ats_boards`: boards (or an Exception) for ATS board searches; each provider's search
    returns the boards whose `provider` is its own.
    `ats_board_jobs`: `{slug: list[job] | Exception}` for `ats_jobs`; missing slugs give [].
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch, default_people: int = 3) -> None:
        self.jobs: list[dict] | Exception = [
            {
                "title": f"Data Analyst at {c}",
                "url": job_url(i + 1),
                "company": c,
                "company_url": f"https://www.builtinnyc.com/company/{slug(c)}",
                "location": "New York, NY",
                "salary": "100K-120K",
                "summary": "SQL and Python.",
            }
            for i, c in enumerate(COMPANIES)
        ]
        self.google: list[dict] | Exception = []
        self.people: dict[tuple[str, str], list[dict] | Exception] = {}
        self.default_people = default_people
        self.calls: list[tuple[str, Any]] = []
        self.people_calls: list[tuple[str, str, str]] = []
        self.ats_boards: list[dict] | Exception = []
        self.ats_board_jobs: dict[str, list[dict] | Exception] = {}
        for name in ("builtin_jobs", "builtin_companies", "conservation_jobs", "google_search"):
            monkeypatch.setattr(tools, name, self._source(name))
        monkeypatch.setattr(tools, "linkedin_people", self.linkedin_people)
        monkeypatch.setattr(tools, "read_page", self.read_page)
        monkeypatch.setattr(tools, "ats_boards", self.fake_ats_boards)
        monkeypatch.setattr(tools, "ats_jobs", self.fake_ats_jobs)

    def _source(self, name: str):
        def run(arg: Any, n: int = 15) -> list[dict]:
            self.calls.append((name, arg))
            result = {"builtin_jobs": self.jobs, "google_search": self.google}.get(name, [])
            if isinstance(result, Exception):
                raise result
            return result

        return run

    def found(self, company: str, keywords: str) -> list[dict]:
        result = self.people.get((company, keywords))
        if result is None:
            return [profile(company, keywords, i) for i in range(self.default_people)]
        if isinstance(result, Exception):
            raise result
        return result

    def linkedin_people(self, company: str, keywords: str, location: str = "", n: int = 5):
        self.people_calls.append((company, keywords, location))
        return self.found(company, keywords)

    def read_page(self, url: str, max_chars: int = 12_000) -> PageResult:
        self.calls.append(("read_page", url))
        return PageResult(url=url, final_url=url, method="static", markdown=f"Posting {url}")

    def fake_ats_boards(self, provider: str, keywords: str, location: str = "") -> list[dict]:
        self.calls.append(("ats_boards", (provider, keywords, location)))
        if isinstance(self.ats_boards, Exception):
            raise self.ats_boards
        return [b for b in self.ats_boards if b["provider"] == provider]

    def fake_ats_jobs(
        self,
        provider: str,
        board: str,
        keywords: str,
        location: str = "",
        job_ids: list[str] | None = None,
        n: int = 4,
    ) -> list[dict]:
        self.calls.append(("ats_jobs", (provider, board, keywords, location, job_ids, n)))
        result = self.ats_board_jobs.get(board, [])
        if isinstance(result, Exception):
            raise result
        return result[:n]


def ats_board(slug: str, *job_ids: str, provider: str = "greenhouse") -> dict[str, Any]:
    return {"provider": provider, "slug": slug, "job_ids": list(job_ids)}


def ats_job(company: str, i: int, title: str = "Data Analyst") -> dict[str, Any]:
    """A job dict as `tools.ats_jobs` returns it."""
    board = slug(company)
    return {
        "title": title,
        "url": f"https://job-boards.greenhouse.io/{board}/jobs/{i}",
        "company": company,
        "company_url": f"https://job-boards.greenhouse.io/{board}",
        "location": "New York, NY",
        "summary": "Greenhouse · posted 2026-11-01",
    }
