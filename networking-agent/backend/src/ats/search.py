"""Provider-agnostic search helpers: Google `site:` queries, reading board slugs off Google
results, and matching a board's postings to the user's keywords and location.

Pure functions (no network): `tools.ats_boards` / `tools.ats_jobs` do the I/O.
"""

import re
from collections.abc import Iterable
from typing import Protocol
from urllib.parse import urlsplit

from .base import Provider
from .models import AtsJob, Board, BoardRef


class ResultLike(Protocol):
    """The parts of a `google_serp.SearchResult` used here."""

    url: str
    display_url: str


# ------------------------------------------------------------------------ the query


def _city(location: str) -> str:
    """ "New York, NY" -> "New York"; "" stays ""."""
    return location.split(",")[0].strip()


def is_remote(location: str) -> bool:
    return _city(location).lower() in {"remote", "anywhere", "remote us", "remote (us)"}


def site_query(provider: Provider, keywords: str, location: str = "") -> str:
    """e.g. `site:job-boards.greenhouse.io OR site:boards.greenhouse.io "data analyst"
    "New York"`. Google binds OR to its neighbours, so the sites are OR-ed and the rest
    AND-ed."""
    sites = " OR ".join(f"site:{d}" for d in provider.site_domains)
    keywords = keywords.strip().strip('"')
    city = "remote" if is_remote(location) else _city(location).strip('"')
    parts = [sites]
    if keywords:
        parts.append(f'"{keywords}"')
    if city:
        parts.append(f'"{city}"' if " " in city else city)
    return " ".join(parts)


# ------------------------------------------------------------------ boards from Google


def breadcrumb_url(display_url: str) -> str:
    """Google's breadcrumb `https://job-boards.greenhouse.io › acme › jobs › 123` as a URL.

    Segments after a truncation ("…") are dropped, since they no longer line up.
    """
    if not display_url.startswith("http"):
        return ""
    segments: list[str] = []
    for part in display_url.split("›"):
        part = part.strip()
        if not part or part in {"...", "…"} or part.endswith(("...", "…")):
            break
        segments.append(part)
    return "/".join(segments)


def _is_google_link(url: str) -> bool:
    host = urlsplit(url).netloc.lower()
    return host == "google.com" or host.endswith(".google.com")


def board_ref(result: ResultLike, provider: Provider) -> BoardRef | None:
    """The board a result points at, from its URL (once resolved) or else its breadcrumb,
    so most results need no `/goto` resolving."""
    return provider.parse_url(result.url) or provider.parse_url(breadcrumb_url(result.display_url))


def needs_resolving(result: ResultLike, provider: Provider) -> bool:
    """An unresolved Google link whose breadcrumb hides the board (e.g. an embed URL) but
    may still be on the provider's hosts."""
    if not _is_google_link(result.url) or board_ref(result, provider) is not None:
        return False
    crumb = breadcrumb_url(result.display_url)
    return not crumb or provider.owns(crumb)


def merge_boards(refs: Iterable[BoardRef]) -> list[Board]:
    """One `Board` per slug (case-insensitive), in first-seen order, with its posting ids."""
    boards: dict[tuple[str, str], Board] = {}
    for ref in refs:
        board = boards.setdefault(
            (ref.provider, ref.slug.lower()), Board(provider=ref.provider, slug=ref.slug)
        )
        if ref.job_id and ref.job_id not in board.job_ids:
            board.job_ids.append(ref.job_id)
    return list(boards.values())


def boards_from_results(results: Iterable[ResultLike], provider: Provider) -> list[Board]:
    return merge_boards(ref for r in results if (ref := board_ref(r, provider)) is not None)


# --------------------------------------------------------------------------- matching

_WORD = re.compile(r"[a-z0-9+#]+")
_STOPWORDS = {
    "a", "an", "and", "at", "for", "in", "job", "jobs", "of", "on", "or", "position", "role",
    "roles", "the", "to", "with",
}  # fmt: skip
_CITY_ALIASES = {
    "new york": ("new york", "nyc"),
    "new york city": ("new york", "nyc"),
    "nyc": ("new york", "nyc"),
    "san francisco": ("san francisco", "bay area"),
    "sf": ("san francisco", "bay area"),
    "washington dc": ("washington", "dc"),
    "dc": ("washington", "dc"),
}


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _stem(token: str) -> str:
    """Crude stem: "analyst" -> "analy" (matches "analytics"), "engineer" -> "engine"."""
    return token if len(token) <= 4 else token[: max(4, len(token) - 2)]


def matches_keywords(job: AtsJob, keywords: str) -> bool:
    """Every keyword (stopwords aside) starts a word of the title or a department."""
    tokens = [t for t in _words(keywords) if t not in _STOPWORDS]
    words = _words(" ".join([job.title, *job.departments]))
    return all(any(w.startswith(_stem(t)) for w in words) for t in tokens)


def matches_location(job: AtsJob, location: str) -> bool:
    """Empty `location` matches anything; "remote" matches remote postings; a city matches
    postings that name it (or a common alias: NYC, Bay Area, DC)."""
    if not location.strip():
        return True
    text = " ".join(_words(job.location))
    if is_remote(location):
        return "remote" in text
    city = " ".join(_words(_city(location)))
    names = _CITY_ALIASES.get(city, (city,))
    return any(re.search(rf"\b{re.escape(name)}\b", text) for name in names if name)


def filter_jobs(
    jobs: list[AtsJob],
    keywords: str,
    location: str = "",
    job_ids: Iterable[str] = (),
    n: int = 5,
) -> list[AtsJob]:
    """Up to `n` postings: the ones Google pointed at (`job_ids`, still open) first, then
    those matching `keywords` and `location`, in board order."""
    wanted = list(job_ids)
    by_id = {j.id: j for j in jobs}
    picked = [by_id[i] for i in dict.fromkeys(wanted) if i in by_id]
    seen = {j.id for j in picked}
    for job in jobs:
        if len(picked) >= n:
            break
        if job.id not in seen and matches_keywords(job, keywords):
            if matches_location(job, location):
                picked.append(job)
                seen.add(job.id)
    return picked[:n]
