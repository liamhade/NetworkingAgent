"""Shared models of the ATS layer: what every provider parses and returns."""

from pydantic import BaseModel, Field


class BoardRef(BaseModel):
    """What a URL says about an ATS board: its provider, slug and (maybe) one posting."""

    provider: str = Field(description='Provider name, e.g. "greenhouse".')
    slug: str = Field(description='The company\'s board token, e.g. "discord".')
    job_id: str | None = Field(default=None, description="Posting id, if the URL is a posting.")


class Board(BaseModel):
    """A board found through Google, with the postings Google pointed at (if any)."""

    provider: str
    slug: str
    job_ids: list[str] = []


class AtsJob(BaseModel):
    """A posting from a provider's public board API, normalized across providers."""

    provider: str
    board: str = Field(description="The board slug the posting came from.")
    id: str
    title: str
    url: str = Field(description="Employer-direct posting URL (the ATS's own link to it).")
    company: str = ""
    location: str = ""
    departments: list[str] = []
    posted: str | None = Field(default=None, description="ISO date first published, if known.")
    years_required: str = Field(
        default="", description='Experience the description asks for, e.g. "3+ years".'
    )
