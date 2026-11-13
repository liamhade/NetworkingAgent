"""Contains the models used by the rest of the program.

Filter values mirror the options offered by https://www.builtinnyc.com. Each enum
value is the URL path alias the site uses for that filter.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class RemotePreference(StrEnum):
    """Where the work is done."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ON_SITE = "office"


class ExperienceLevel(StrEnum):
    """Seniority levels offered by the jobs filter."""

    INTERNSHIP = "internship"
    ENTRY_LEVEL = "entry-level"
    JUNIOR = "junior"
    MID_LEVEL = "mid-level"
    SENIOR = "senior"
    EXPERT_LEADER = "expert-leader"
    NOT_SPECIFIED = "not-specified"


class CompanySize(StrEnum):
    """Employee-count buckets offered by the job and company filters."""

    S_1_10 = "1-10"
    S_11_50 = "11-50"
    S_51_200 = "51-200"
    S_201_500 = "201-500"
    S_501_1000 = "501-1000"
    S_1000_PLUS = "1000"


class JobCategory(StrEnum):
    """Top-level job categories."""

    AI_ML = "ai-machine-learning"
    CONSULTING = "consultant"
    CUSTOMER_SUCCESS = "customer-success-experience"
    CYBERSECURITY = "cyber-security"
    DATA_ANALYTICS = "data-analytics"
    DESIGN = "designer"
    ENGINEERING = "engineering"
    FINANCE = "finance"
    HR_RECRUITING = "hr-recruiting"
    LEGAL = "legal"
    MARKETING = "marketing"
    OPERATIONS = "operations-support"
    PRODUCT = "product-management"
    PROJECT_MANAGEMENT = "program-project-management"
    SALES = "sales"
    SUPPLY_CHAIN = "supply-chain-procurement"


class Company(BaseModel):
    """A company listed on BuiltInNYC."""

    id: int
    name: str
    url: str = Field(description="Absolute URL of the BuiltInNYC company profile.")
    logo_url: str | None = None
    industries: list[str] = []
    office_count: int | None = None
    office_locations: list[str] = []
    employee_count: str | None = Field(
        default=None, description='Employee bucket as shown on the site, e.g. "800 Employees".'
    )
    benefits_count: int | None = None
    is_hiring: bool = False
    is_featured: bool = False
    mission: str | None = Field(default=None, description="Bolded mission/tagline, if any.")
    description: str | None = None


class CompanyFilter(BaseModel):
    """Filters for `get_companies`. Every field is optional; unset means "any"."""

    sizes: list[CompanySize] = []
    industries: list[str] = Field(
        default=[], description='Industry aliases, e.g. "fintech", "artificial-intelligence".'
    )
    tech_stack: list[str] = Field(default=[], description='Tech aliases, e.g. "python".')
    perks: list[str] = Field(default=[], description='Perk aliases, e.g. "401k".')
    office_types: list[Literal["hybrid", "office"]] = []
    fully_remote: bool = False
    hiring_only: bool = Field(default=False, description="Only companies with open jobs.")


class Job(BaseModel):
    """A job listing on BuiltInNYC."""

    id: int
    title: str
    url: str = Field(description="Absolute URL of the job posting page.")
    company_name: str
    company_url: str | None = None
    company_logo_url: str | None = None
    posted: str | None = Field(default=None, description='Relative age, e.g. "Yesterday".')
    work_arrangement: str | None = Field(default=None, description='"Hybrid", "In-Office", ...')
    location: str | None = None
    salary: str | None = Field(default=None, description='e.g. "113K-158K Annually".')
    experience_level: str | None = None
    industries: list[str] = []
    skills: list[str] = []
    description: str | None = Field(default=None, description="Short summary from the card.")


class JobFilter(BaseModel):
    """Filters for `get_jobs`. Every field is optional; unset means "any"."""

    search: str | None = Field(default=None, description="Free-text search term.")
    category: JobCategory | None = None
    subcategories: list[str] = Field(
        default=[],
        description='Sub-category aliases of `category`, e.g. "software-engineering".',
    )
    remote_preferences: list[RemotePreference] = []
    experience_levels: list[ExperienceLevel] = []
    industries: list[str] = Field(default=[], description='Industry aliases, e.g. "fintech".')
    company_sizes: list[CompanySize] = []
    posted_within_days: Literal[1, 3, 7, 30] | None = None
    early_applicant: bool = Field(default=False, description="Posted so you can apply early.")
    skills: list[str] = Field(
        default=[], description="Skill names. Only honoured with `search` or `category`."
    )
