"""Typed state of the search graph: the LLM schemas and the gathered data.

LLM schemas (`SearchPlan`, `JobRanking`, `PeopleNotes`) keep every field required and
put limits in descriptions, not JSON-schema constraints, so they work with
`with_structured_output(..., method="json_schema")`. Code enforces the limits.
"""

import operator
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

from builtin_nyc.models import ExperienceLevel, JobCategory, RemotePreference
from conservation_jobboard.models import Category, Location
from conservation_jobboard.models import ExperienceLevel as ConservationExperience
from schemas import PersonResult, SearchRequest, SearchResults, TraceStep
from usajobs.models import Agency

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


class UsajobsQuery(BaseModel):
    keywords: str = Field(
        description='Role words, e.g. "wildlife biologist" or "park ranger", or "".'
    )
    location: str = Field(
        description='City and state, e.g. "Denver, Colorado", "remote", or "" for anywhere.'
    )
    agencies: list[Agency] = Field(
        description='Federal agencies: "nps" (National Park Service), "usfws" (Fish and '
        'Wildlife Service), "usfs" (Forest Service), "epa"; or [] for any agency.'
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
    usajobs: list[UsajobsQuery] = Field(
        description="0-2 USAJOBS federal job searches; [] unless the prompt offers USAJOBS."
    )
    ats_jobs: list[AtsJobQuery] = Field(
        description=(
            "0-2 searches of companies' own career boards (Greenhouse, Lever, Ashby, Workable)."
        )
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
    level: str = ""
    """Seniority label from the source (BuiltInNYC's "entry-level", ...), if it has one."""
    years_required: str = ""
    """Experience the posting asks for ("3+ years"; see `experience`), or "" if unknown."""
    description: str = ""
    """Full posting text when the board's search API already returns it (Lever, Ashby, the
    USAJOBS qualification summary); "" otherwise. `complete_jobs` fills the rest."""
    posted_at: str = ""
    """Publication date (YYYY-MM-DD) when the board gives it."""


TextSource = Literal["api", "parser", "page", "none"]


class JobPosting(Job):
    """A `Job` completed with the posting's text, by `steps.complete.complete_jobs`.

    Extends `Job` rather than duplicating it: every field the plan lists is already on `Job`
    (or added to it above), so `Job` stays the card from the board search and `JobPosting`
    adds what completion produces. `description` is kept for the record and never sent to
    the LLM whole; `requirements` is its excerpt for the ranking card."""

    requirements: str = ""
    """`posting_excerpt(description)`; the card's summary when no text could be read."""
    text_source: TextSource = "none"
    """Where `description` came from: the board `api`, a site `parser`, the generic `page`
    reader, or `none` (read failed or skipped: only the listing's card text is known)."""


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
    shared_background: str = Field(
        default="", description='What they share with the user, e.g. "Same school: Cornell".'
    )


# --------------------------------------------------------------------- ranking (LLM)


class JobRank(BaseModel):
    id: str = Field(description='Job id from the cards, e.g. "j3".')
    score: int = Field(description="Fit with the user's profile, 0-100.")
    reason: str = Field(description="One short sentence (at most 15 words) on the score.")
    alignment: str = Field(
        description="For your top jobs only: 1-3 sentences on why it fits, addressed to the "
        'user: "You ...". "" for every other job.'
    )
    years_required: str = Field(
        description='Experience the posting asks for, e.g. "3+ years", or "" if it does not say.'
    )
    company: str = Field(
        description="Employer name, copied from the card; when the card has no company, the "
        'employer named in its title, site or URL, else "".'
    )


class CompanyKeywords(BaseModel):
    company: str = Field(description="Company name exactly as on the cards.")
    people_keywords: list[str] = Field(
        description='1-2 keyword sets describing people to contact, e.g. "data science '
        'manager", "recruiter".'
    )


class JobRanking(BaseModel):
    jobs: list[JobRank] = Field(description="The best jobs, best first.")
    companies: list[CompanyKeywords] = Field(description="One entry per company in `jobs`.")


class RankedJob(BaseModel):
    """A job the ranker kept: the completed posting plus its verdict. `rank` is 1-based."""

    job: JobPosting
    rank: int
    score: int
    reason: str = ""
    alignment: str = ""
    years_required: str = ""


class ChosenCompany(BaseModel):
    """A company with at least one ranked job: what find_people and compile work on.

    Companies are ordered by their best job; `score` is that job's score and `jobs` are in
    rank order."""

    name: str
    url: str = ""
    about: str = ""
    score: int
    reason: str = ""
    jobs: list[RankedJob] = []
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
    postings: list[JobPosting]
    """The jobs worth ranking (`filter`), completed with their posting text."""
    ranked: list[RankedJob]
    """The ranker's top jobs, best first."""
    chosen: list[ChosenCompany]
    """Companies of the ranked jobs, best job first; only the first
    `config.PEOPLE_AUTO_COMPANIES` get a people search."""
    people: dict[str, list[Person]]
    """Chosen company name -> people found; a key exists only if it was searched."""
    results: SearchResults
    error: str
    """Set when nothing usable was found; the graph then ends."""
    trace: Annotated[list[TraceStep], operator.add]
