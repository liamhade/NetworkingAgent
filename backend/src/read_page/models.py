"""Result type and errors for `read_page`."""

from pydantic import BaseModel


class PageResult(BaseModel):
    url: str
    """The URL that was asked for."""
    final_url: str
    """The URL after redirects (or the API's canonical posting URL)."""
    method: str
    """The method that actually produced `markdown`."""
    title: str | None = None
    markdown: str
    truncated: bool = False


class ReadPageError(Exception):
    """The page could not be read (no content, unknown method, ...)."""


class PageBlocked(ReadPageError):
    """The URL belongs to a site `read_page` refuses to read."""


class MethodUnavailable(ReadPageError):
    """A specialized method does not apply to this URL/page; try another method."""
