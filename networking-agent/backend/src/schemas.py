"""Request, response and result models shared by the agent and the server."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.json_schema import SkipJsonSchema

import config
from boards import BoardsConfig, default_config, normalize

SCORE_DESCRIPTION = (
    "Fit with the user's profile, 0-100, from the ranking step (`pipeline`). Results are "
    "sorted by it. Hidden from the LLM's structured-output schema; None for older searches."
)

ENTITY_KEY_DESCRIPTION = (
    "Stable identity across searches, filled in by the server (`entities.keys`). "
    "Hidden from the LLM's structured-output schema."
)


class SearchRequest(BaseModel):
    """What the user typed on the hero page."""

    background: str = Field(min_length=1, max_length=20_000)
    location: str = Field(default="", max_length=200)
    looking_for: str = Field(min_length=1, max_length=5_000)
    boards: BoardsConfig = Field(
        default_factory=default_config,
        description="Which job boards to search and how many jobs to gather from each: "
        '`{board_id: {"enabled": bool, "max_jobs": int}}`. Normalised on input (unknown ids '
        "dropped, limits clamped, defaults for what is missing); see `boards`.",
    )

    @field_validator("boards", mode="before")
    @classmethod
    def _normalize_boards(cls, value: Any) -> BoardsConfig:
        return normalize(value)


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
    score: SkipJsonSchema[int | None] = Field(default=None, description=SCORE_DESCRIPTION)
    key: SkipJsonSchema[str] = Field(default="", description=ENTITY_KEY_DESCRIPTION)


_SENTENCE_ENDS = (". ", "! ", "? ")


def clamp_message(text: str, limit: int) -> str:
    """`text` trimmed to at most `limit` characters, cut at a sentence or word boundary.

    Prefers ending on the last complete sentence that fits (if it keeps at least half of
    the limit); otherwise cuts at the last word boundary and adds "…". Never returns more
    than `limit` characters.
    """
    text = text.strip()
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    head = text[: limit + 1]  # One extra character so a sentence end at `limit` is found.
    sentence_end = max(head.rfind(end) for end in _SENTENCE_ENDS)
    if sentence_end >= 0 and sentence_end + 1 >= limit // 2:
        return text[: sentence_end + 1]
    if limit == 1:
        return "…"
    cut = text[: limit - 1]
    space = cut.rfind(" ")
    if space >= limit // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:-–—") + "…"


def _require_connect_message(schema: dict) -> None:
    # `connect_message` has a default so older saved searches still load, but the LLM must
    # always write one, so it stays required in the structured-output schema.
    required = schema.setdefault("required", [])
    if "connect_message" not in required:
        required.append("connect_message")


class PersonResult(BaseModel):
    model_config = ConfigDict(json_schema_extra=_require_connect_message)

    name: str
    title: str = Field(description="Their role/headline, or empty string.")
    profile_url: str = Field(description="Exact profile URL from a tool result.")
    alignment: str = Field(
        description="1-3 sentences on why the user should connect with them and what "
        "they have in common."
    )
    connect_message: str = Field(
        default="",
        description="Example LinkedIn connection note from the user to this person, at most "
        f"{config.LINKEDIN_MESSAGE_MAX_CHARS} characters.",
    )
    key: SkipJsonSchema[str] = Field(default="", description=ENTITY_KEY_DESCRIPTION)

    @field_validator("connect_message")
    @classmethod
    def _clamp_connect_message(cls, value: str) -> str:
        return clamp_message(value, config.LINKEDIN_MESSAGE_MAX_CHARS)


class CompanyResult(BaseModel):
    name: str
    url: str = Field(description="Company profile or website URL from a tool result.")
    description: str = Field(description="One-sentence description of the company.")
    alignment: str = Field(description="1-3 sentences on why this company fits the user.")
    jobs: list[JobResult]
    people: list[PersonResult]
    score: SkipJsonSchema[int | None] = Field(default=None, description=SCORE_DESCRIPTION)
    people_searched: SkipJsonSchema[bool] = Field(
        default=False,
        description="True once a people search ran for this company, so an empty `people` "
        'means "no one found" rather than "not searched yet". Set by the server.',
    )
    people_keywords: SkipJsonSchema[list[str]] = Field(
        default=[],
        description="People-search keyword sets from the ranking step, reused by the "
        "on-demand people search. Set by the server.",
    )
    key: SkipJsonSchema[str] = Field(default="", description=ENTITY_KEY_DESCRIPTION)


class SearchResults(BaseModel):
    summary: str = Field(description="2-3 sentence overview of the search and the strategy.")
    companies: list[CompanyResult]


class SearchSummary(BaseModel):
    """One entry in the search-history side panel."""

    id: str
    title: str
    created_at: datetime


class TraceStep(BaseModel):
    """One step of a search run: a source call, an LLM call or a validation.

    Saved with the search so "why is this list empty?" can be answered from data later.
    """

    step: str = Field(description='Pipeline node, e.g. "find_people".')
    source: str = Field(description='"llm", "linkedin_people", "builtin_jobs", "validate", ...')
    args: dict[str, Any] = {}
    count: int | None = Field(default=None, description="Results returned, if it applies.")
    error: str = ""
    duration_ms: int = 0
    note: str = ""


class SavedSearch(SearchSummary):
    """A persisted search: what was asked and what came back."""

    user_id: str
    request: SearchRequest
    results: SearchResults
    trace: list[TraceStep] | None = Field(
        default=None, description="How the results were found; None for older searches."
    )


EntityStatusKind = Literal["job", "person"]
"""Entities that carry a toggle: jobs (APPLIED) and people (CONNECTED)."""


class StatusUpdate(BaseModel):
    """Set one toggle: `active` means APPLIED (jobs) / CONNECTED (people)."""

    kind: EntityStatusKind
    key: str = Field(min_length=1, max_length=1000)
    active: bool


class EntityStatus(StatusUpdate):
    updated_at: datetime


PinKind = Literal["company", "job", "person"]
"""Entities that can be pinned to come back to later."""


class PinUpdate(BaseModel):
    """Pin (or unpin) one entity, identified by its `entities.keys` key."""

    kind: PinKind
    key: str = Field(min_length=1, max_length=1000)
    pinned: bool


class EntityPin(PinUpdate):
    updated_at: datetime


class FindPeopleRequest(BaseModel):
    """On-demand people search for one company of a saved search, optionally for one job."""

    company_key: str = Field(min_length=1, max_length=1000)
    job_key: str | None = Field(default=None, max_length=1000)


class StatusEvent(BaseModel):
    type: Literal["status"] = "status"
    message: str


class ResultEvent(BaseModel):
    type: Literal["result"] = "result"
    data: SearchResults


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class TraceEvent(BaseModel):
    """The run's trace, sent just before `ResultEvent`. Server-internal: saved with the
    search, never streamed to the browser."""

    type: Literal["trace"] = "trace"
    steps: list[TraceStep]


class SavedEvent(BaseModel):
    type: Literal["saved"] = "saved"
    search: SearchSummary


AgentEvent = StatusEvent | ResultEvent | ErrorEvent | TraceEvent | SavedEvent


class Sighting(BaseModel):
    """Where and when an entity was seen across the user's searches (Companies/Jobs/People)."""

    key: str = Field(description="Entity key from `entities.keys`.")
    first_seen: datetime
    last_seen: datetime
    searches: list[SearchSummary] = Field(
        description="Searches the entity appeared in, most recent first."
    )


class CompanyEntity(Sighting):
    """A company seen in any search; fields come from the most recent sighting."""

    name: str
    url: str
    description: str
    alignment: str
    job_count: int = Field(description="Distinct jobs seen at this company across searches.")
    person_count: int = Field(description="Distinct people seen at this company.")


class JobEntity(Sighting):
    """A job seen in any search; fields come from the most recent sighting."""

    title: str
    url: str
    location: str
    salary: str
    alignment: str
    company: str
    company_key: str


class PersonEntity(Sighting):
    """A person seen in any search; fields come from the most recent sighting."""

    name: str
    title: str
    profile_url: str
    alignment: str
    connect_message: str = Field(
        default="", description="Example LinkedIn connection note; empty for older searches."
    )
    company: str
    company_key: str
