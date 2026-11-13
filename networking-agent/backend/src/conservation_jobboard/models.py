"""Filters and result models for the Conservation Job Board API.

Each filter enum's value is a readable slug; ``site_id`` is the numeric id the site uses in
its search URLs (``/search/cat=1&state=6``). The ids come from the filter widget on
https://www.conservationjobboard.com.
"""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field


class _SiteFilter(StrEnum):
    """A filter value that also knows the site's numeric id (and URL key, for locations)."""

    site_id: int
    key: str

    def __new__(cls, value: str, site_id: int, key: str = "") -> Self:
        member = str.__new__(cls, value)
        member._value_ = value
        member.site_id = site_id
        member.key = key
        return member


class Category(_SiteFilter):
    ADMIN_LEADERSHIP = "admin-leadership", 16
    BOTANY = "botany", 6
    ECOLOGY = "ecology", 5
    ENVIRONMENTAL_EDUCATION = "environmental-education", 14
    FISHERIES = "fisheries", 7
    FORESTRY = "forestry", 3
    GENERAL_STEWARDSHIP = "general-stewardship", 8
    HYDROLOGY = "hydrology", 13
    LAND_TRUST = "land-trust", 4
    MARINE_BIOLOGY = "marine-biology", 2
    OUTDOOR_RECREATION = "outdoor-recreation", 17
    POLICY_LAW = "policy-law", 15
    RESTORATION = "restoration", 9
    SUSTAINABILITY = "sustainability", 12
    WILDLIFE = "wildlife", 1


class JobType(_SiteFilter):
    PERMANENT = "permanent", 1
    TEMPORARY = "temporary", 2
    PAID_INTERNSHIP = "paid-internship", 3
    STUDENT = "student", 4
    AMERICORPS = "americorps", 5
    UNPAID = "unpaid", 6
    FACULTY_POSTDOC = "faculty-postdoc", 7


class ExperienceLevel(_SiteFilter):
    ENTRY = "entry", 1  # 0-1 years
    MID = "mid", 2  # 2-4 years
    SENIOR = "senior", 3  # 5+ years


class Location(_SiteFilter):
    """A US state (or DC / US territories) or a world region, including remote."""

    ALABAMA = "alabama", 1, "state"
    ALASKA = "alaska", 2, "state"
    ARIZONA = "arizona", 3, "state"
    ARKANSAS = "arkansas", 4, "state"
    CALIFORNIA = "california", 5, "state"
    COLORADO = "colorado", 6, "state"
    CONNECTICUT = "connecticut", 7, "state"
    DELAWARE = "delaware", 8, "state"
    DISTRICT_OF_COLUMBIA = "district-of-columbia", 9, "state"
    FLORIDA = "florida", 10, "state"
    GEORGIA = "georgia", 11, "state"
    HAWAII = "hawaii", 12, "state"
    IDAHO = "idaho", 13, "state"
    ILLINOIS = "illinois", 14, "state"
    INDIANA = "indiana", 15, "state"
    IOWA = "iowa", 16, "state"
    KANSAS = "kansas", 17, "state"
    KENTUCKY = "kentucky", 18, "state"
    LOUISIANA = "louisiana", 19, "state"
    MAINE = "maine", 20, "state"
    MARYLAND = "maryland", 21, "state"
    MASSACHUSETTS = "massachusetts", 22, "state"
    MICHIGAN = "michigan", 23, "state"
    MINNESOTA = "minnesota", 24, "state"
    MISSISSIPPI = "mississippi", 25, "state"
    MISSOURI = "missouri", 26, "state"
    MONTANA = "montana", 27, "state"
    NEBRASKA = "nebraska", 28, "state"
    NEVADA = "nevada", 29, "state"
    NEW_HAMPSHIRE = "new-hampshire", 30, "state"
    NEW_JERSEY = "new-jersey", 31, "state"
    NEW_MEXICO = "new-mexico", 32, "state"
    NEW_YORK = "new-york", 33, "state"
    NORTH_CAROLINA = "north-carolina", 34, "state"
    NORTH_DAKOTA = "north-dakota", 35, "state"
    OHIO = "ohio", 36, "state"
    OKLAHOMA = "oklahoma", 37, "state"
    OREGON = "oregon", 38, "state"
    PENNSYLVANIA = "pennsylvania", 39, "state"
    RHODE_ISLAND = "rhode-island", 41, "state"
    SOUTH_CAROLINA = "south-carolina", 42, "state"
    SOUTH_DAKOTA = "south-dakota", 43, "state"
    TENNESSEE = "tennessee", 44, "state"
    TEXAS = "texas", 45, "state"
    UTAH = "utah", 46, "state"
    VERMONT = "vermont", 47, "state"
    VIRGINIA = "virginia", 48, "state"
    WASHINGTON = "washington", 49, "state"
    WEST_VIRGINIA = "west-virginia", 50, "state"
    WISCONSIN = "wisconsin", 51, "state"
    WYOMING = "wyoming", 52, "state"
    US_TERRITORIES = "us-territories", 53, "state"
    REMOTE = "remote", 9, "region"
    AFRICA = "africa", 1, "region"
    ASIA = "asia", 2, "region"
    EUROPE = "europe", 3, "region"
    AUSTRALIA = "australia", 4, "region"
    LATIN_AMERICA = "latin-america", 5, "region"
    CANADA = "canada", 6, "region"
    OTHER_INTERNATIONAL = "other-international", 8, "region"


class JobFilter(BaseModel):
    """Filters for `get_jobs`. Every field is optional; unset means "any". Values within a
    list are OR-ed; different fields are AND-ed."""

    keyword: str | None = Field(default=None, description="Free-text search term.")
    categories: list[Category] = []
    locations: list[Location] = []
    job_types: list[JobType] = []
    experience_levels: list[ExperienceLevel] = []


class Job(BaseModel):
    """A job listing on the Conservation Job Board."""

    id: int
    title: str
    url: str = Field(description="Absolute URL of the job posting page (no query string).")
    organization: str
    location: str | None = None
    job_type: str | None = Field(default=None, description='e.g. "Permanent", "Temporary".')
    salary: str | None = Field(default=None, description='e.g. "$20 - $22 per hour".')
    deadline: str | None = Field(default=None, description='e.g. "Nov 30, 2026".')
    experience: str | None = Field(default=None, description='Minimum, e.g. "0 - 1 year".')
    posted: str | None = Field(default=None, description='Relative age, e.g. "7 days ago".')
