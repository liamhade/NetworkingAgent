"""Filters and result models for the BuiltInNYC API.

Each enum value is the URL path alias https://www.builtinnyc.com uses for that filter.
"""

from enum import StrEnum

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
    """Employee-count buckets offered by the companies filter."""

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


class JobFilter(BaseModel):
    """Filters for `get_jobs`. Every field is optional; unset means "any"."""

    search: str | None = Field(default=None, description="Free-text search term.")
    category: JobCategory | None = None
    remote_preferences: list[RemotePreference] = []
    experience_levels: list[ExperienceLevel] = []


class CompanyFilter(BaseModel):
    """Filters for `get_companies`. Every field is optional; unset means "any"."""

    industries: list[str] = Field(
        default=[], description='Industry aliases, e.g. "fintech", "artificial-intelligence".'
    )
    sizes: list[CompanySize] = []
    tech_stack: list[str] = Field(default=[], description='Tech aliases, e.g. "python".')
    hiring_only: bool = Field(default=False, description="Only companies with open jobs.")
    fully_remote: bool = False


class Job(BaseModel):
    """A job listing on BuiltInNYC."""

    id: int
    title: str
    url: str = Field(description="Absolute URL of the job posting page.")
    company_name: str
    company_url: str | None = None
    posted: str | None = Field(default=None, description='Relative age, e.g. "Yesterday".')
    work_arrangement: str | None = Field(default=None, description='"Hybrid", "In-Office", ...')
    location: str | None = None
    salary: str | None = Field(default=None, description='e.g. "113K-158K Annually".')
    experience_level: str | None = None
    industries: list[str] = []
    skills: list[str] = []
    description: str | None = Field(default=None, description="Short summary from the card.")


class Company(BaseModel):
    """A company listed on BuiltInNYC."""

    id: int
    name: str
    url: str = Field(description="Absolute URL of the BuiltInNYC company profile.")
    industries: list[str] = []
    office_locations: list[str] = []
    employee_count: str | None = Field(
        default=None, description='Employee bucket as shown on the site, e.g. "800 Employees".'
    )
    is_hiring: bool = False
    mission: str | None = Field(default=None, description="Bolded mission/tagline, if any.")
    description: str | None = None
