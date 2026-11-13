"""Typed state of the search graph: the LLM schemas and the gathered data.

LLM schemas (`SearchPlan`, `CompanyRanking`, `PeopleNotes`) keep every field required and
put limits in descriptions, not JSON-schema constraints, so they work with
`with_structured_output(..., method="json_schema")`. Code enforces the limits.
"""

import operator
from typing import Annotated, TypedDict

from pydantic import BaseModel, Field

from builtin_nyc.models import ExperienceLevel, JobCategory, RemotePreference
from conservation_jobboard.models import Category, Location
from conservation_jobboard.models import ExperienceLevel as ConservationExperience
from schemas import PersonResult, SearchRequest, SearchResults, TraceStep

# ------------------------------------------------------------------------ plan (LLM)


class BuiltinJobQuery(BaseModel):
    search: str = Field(description='Short search phrase, 1-3 words, e.g. "data analyst".')
    category: JobCategory | None = Field(description="Top-level job category, or null.")
    experience_levels: list[ExperienceLevel] = Field(description="Seniority levels, or [].")
    remote_preferences: list[RemotePreference] = Field(
        description='"remote", "hybrid" and/or "office", or [] for any.'
    )


class BuiltinCompanyQuery(BaseModel):
    industries: list[str] = Field(
        description='BuiltIn industry aliases, lowercase and hyphenated: "fintech", '
        '"artificial-intelligence", "healthtech", "edtech", "greentech", "software", '
        '"cybersecurity", "consumer-web", "media", "nonprofit".'
    )
    tech_stack: list[str] = Field(description='Tech aliases, e.g. "python", or [].')


class ConservationJobQuery(BaseModel):
    keyword: str = Field(description='Optional 1-2 word keyword, e.g. "biologist", or "".')
    categories: list[Category] = Field(description="Job categories (any of), or [].")
    locations: list[Location] = Field(
        description='The user\'s US state(s) and/or "remote", or [] for anywhere.'
    )
    experience_levels: list[ConservationExperience] = Field(
        description='"entry" (0-1 yr), "mid" (2-4), "senior" (5+), or [].'
    )


class AtsJobQuery(BaseModel):
    keywords: str = Field(
        description='Role phrase, 1-3 words, matched against posting titles, e.g. "data '
        'analyst". No seniority words.'
    )
    location: str = Field(description='A city, e.g. "New York", "remote", or "" for anywhere.')


class SearchPlan(BaseModel):
    role_titles: list[str] = Field(description="2-3 target role titles.")
    seniority: str = Field(description='e.g. "entry level", "mid level", "senior".')
    industries: list[str] = Field(description="1-4 industries that fit.")
    location: str = Field(description='Where they want to work, e.g. "New York, NY", "Remote".')
    people_location: str = Field(
        description='City for finding people to network with, e.g. "New York", or "" if the '
        "user wants remote work or doesn't care where."
    )
    builtin_jobs: list[BuiltinJobQuery] = Field(description="0-3 BuiltInNYC job searches.")
    builtin_companies: list[BuiltinCompanyQuery] = Field(
        description="0-1 BuiltInNYC company searches."
    )
    conservation_jobs: list[ConservationJobQuery] = Field(
        description="0-3 Conservation Job Board searches."
    )
    ats_jobs: list[AtsJobQuery] = Field(
        description="0-2 searches of companies' own career boards (Greenhouse, Lever)."
    )
    google_queries: list[str] = Field(description="0-2 Google job-search queries.")


# --------------------------------------------------------------- gathered data (code)


class Job(BaseModel):
    """A job posting found by `find_jobs`; `id` ("j1", ...) is how the LLM refers to it."""

    id: str
    source: str
    title: str
    url: str
    company: str = ""
    company_url: str = ""
    location: str = ""
    salary: str = ""
    summary: str = ""


class ListedCompany(BaseModel):
    """A company from a BuiltInNYC company search."""

    name: str
    url: str
    about: str = ""


class Person(BaseModel):
    """A LinkedIn profile found by the people search."""

    name: str
    headline: str = ""
    title: str = ""
    company: str = ""
    at_company: bool = False
    location: str = ""
    url: str
    snippet: str = ""
    keywords: str = Field(default="", description="The people search that found them.")


# --------------------------------------------------------------------- ranking (LLM)


class JobScore(BaseModel):
    id: str = Field(description='Job id from the table, e.g. "j3".')
    score: int = Field(description="Fit with the user's profile, 0-100.")


class RankedCompany(BaseModel):
    name: str = Field(description="Company name exactly as in the data.")
    score: int = Field(description="Overall fit with the user's profile, 0-100.")
    reason: str = Field(description="One short sentence on the score.")
    jobs: list[JobScore] = Field(description="Its relevant postings, at most 4, best first.")
    people_keywords: list[str] = Field(
        description='1-2 keyword sets describing people to contact, e.g. "data science '
        'manager", "recruiter".'
    )


class CompanyRanking(BaseModel):
    companies: list[RankedCompany]


class ChosenCompany(BaseModel):
    """A validated, scored company: what the rest of the pipeline works on."""

    name: str
    url: str = ""
    about: str = ""
    score: int
    reason: str = ""
    jobs: list[Job] = []
    job_scores: dict[str, int] = {}
    people_keywords: list[str] = []


# ----------------------------------------------------------- on-demand people (LLM)


class PeopleNotes(BaseModel):
    people: list[PersonResult]


# ------------------------------------------------------------------------ the graph


class PipelineState(TypedDict, total=False):
    request: SearchRequest
    plan: SearchPlan
    jobs: list[Job]
    listed_companies: list[ListedCompany]
    chosen: list[ChosenCompany]
    """Ranked best first; only the top `config.PEOPLE_AUTO_COMPANIES` get a people search."""
    people: dict[str, list[Person]]
    """Chosen company name -> people found; a key exists only if it was searched."""
    postings: dict[str, str]
    """Job URL -> posting text from read_page."""
    results: SearchResults
    error: str
    """Set when nothing usable was found; the graph then ends."""
    trace: Annotated[list[TraceStep], operator.add]
