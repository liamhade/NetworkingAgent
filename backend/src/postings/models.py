"""What a posting-page parser returns."""

from pydantic import BaseModel


class ParsedPosting(BaseModel):
    """The fields a site parser could read from one posting. Empty means "not on the page"."""

    description: str = ""
    """The posting's full text as Markdown."""
    title: str = ""
    company: str = ""
    location: str = ""
    salary: str = ""
    posted_at: str = ""
    """YYYY-MM-DD when the page says."""
    level: str = ""
    years_required: str = ""
