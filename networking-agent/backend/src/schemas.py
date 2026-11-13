"""Request, response and result models shared by the agent and the server."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """What the user typed on the hero page."""

    background: str = Field(min_length=1, max_length=20_000)
    location: str = Field(default="", max_length=200)
    looking_for: str = Field(min_length=1, max_length=5_000)


class ResumeProfile(BaseModel):
    """Fields extracted from an uploaded resume to pre-fill the hero form."""

    background: str = Field(
        description="2-5 sentence first-person summary of experience, skills and education."
    )
    location: str = Field(description="City/region the person lives in, or empty string.")
    looking_for: str = Field(
        description="Roles the person seems to be targeting, inferred from the resume, "
        "or empty string if unclear."
    )


class JobResult(BaseModel):
    title: str
    url: str = Field(description="Exact posting URL from a tool result.")
    location: str = Field(description="Location / work arrangement, or empty string.")
    salary: str = Field(description="Salary text if listed, else empty string.")
    alignment: str = Field(description="1-3 sentences on why this job fits the user.")


class PersonResult(BaseModel):
    name: str
    title: str = Field(description="Their role/headline, or empty string.")
    profile_url: str = Field(description="Exact profile URL from a tool result.")
    alignment: str = Field(
        description="1-3 sentences on why the user should connect with them and what "
        "they have in common."
    )


class CompanyResult(BaseModel):
    name: str
    url: str = Field(description="Company profile or website URL from a tool result.")
    description: str = Field(description="One-sentence description of the company.")
    alignment: str = Field(description="1-3 sentences on why this company fits the user.")
    jobs: list[JobResult]
    people: list[PersonResult]


class SearchResults(BaseModel):
    summary: str = Field(description="2-3 sentence overview of the search and the strategy.")
    companies: list[CompanyResult]


class SearchSummary(BaseModel):
    """One entry in the search-history side panel."""

    id: str
    title: str
    created_at: datetime


class SavedSearch(SearchSummary):
    """A persisted search: what was asked and what came back."""

    user_id: str
    request: SearchRequest
    results: SearchResults


class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    message: str


class ResultEvent(BaseModel):
    type: Literal["result"] = "result"
    data: SearchResults


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class SavedEvent(BaseModel):
    type: Literal["saved"] = "saved"
    search: SearchSummary


AgentEvent = StatusEvent | ResultEvent | ErrorEvent | SavedEvent
