"""Filter and result models for the USAJOBS search API."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field


class Agency(StrEnum):
    """Federal conservation agencies, with the USAJOBS agency subelement code
    (the `Organization` query parameter)."""

    code: str

    def __new__(cls, value: str, code: str = "") -> Self:
        member = str.__new__(cls, value)
        member._value_ = value
        member.code = code
        return member

    NPS = "nps", "IN10"  # National Park Service
    USFWS = "usfws", "IN15"  # U.S. Fish and Wildlife Service
    USFS = "usfs", "AG11"  # Forest Service
    EPA = "epa", "EP00"  # Environmental Protection Agency


class JobFilter(BaseModel):
    """What to search for. Empty fields don't filter; `agencies=[]` means any agency."""

    keyword: str | None = Field(default=None, description="Words matched in the announcement.")
    location: str | None = Field(
        default=None, description='City and state, e.g. "Denver, Colorado" (LocationName).'
    )
    radius_miles: int | None = Field(default=None, description="With `location` only.")
    agencies: list[Agency] = []
    remote: bool | None = Field(default=None, description="True: only remote jobs.")
    days_posted: int | None = Field(default=None, description="Posted within N days (0-60).")


class Job(BaseModel):
    """A federal job announcement, normalized from `MatchedObjectDescriptor`."""

    title: str
    url: str
    apply_url: str | None = None
    agency: str | None = Field(default=None, description="OrganizationName, e.g. an agency.")
    department: str | None = None
    location: str | None = None
    salary: str | None = None
    job_type: str | None = None
    posted: str | None = Field(default=None, description="Publication date, YYYY-MM-DD.")
    closes: str | None = Field(default=None, description="Application close date, YYYY-MM-DD.")
    summary: str | None = Field(default=None, description="The qualification summary.")
