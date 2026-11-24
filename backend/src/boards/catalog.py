"""The board catalog and the normalisation of a search's `boards` config."""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

import ats
import config

BUILTIN_RESULTS_PER_QUERY = 15
"""Matches `tools.builtin_jobs` / `tools.conservation_jobs` (`n=15`)."""
GOOGLE_RESULTS_PER_QUERY = 10
"""Matches `tools.google_search` (`n=10`)."""
BUILTIN_QUERIES = 3
GOOGLE_QUERIES = 2
"""Most queries per search (`pipeline.steps.MAX_JOB_QUERIES` / `MAX_GOOGLE_QUERIES`)."""
ATS_PROVIDER_COUNT = 4
"""Providers that used to share the `ATS_MAX_BOARDS` budget; each now has its own."""


class BoardSetting(BaseModel):
    """One board in a search: on or off, and the most jobs to gather from it."""

    enabled: bool
    max_jobs: int


BoardsConfig = dict[str, BoardSetting]
"""`{board_id: BoardSetting}`; a normalised config has every catalog board."""


class BoardInfo(BaseModel):
    """A board as the catalog describes it to the frontend."""

    id: str
    label: str
    description: str
    available: bool
    unavailable_reason: str = ""
    default: BoardSetting
    min_jobs: int = Field(description="Lowest allowed `max_jobs`.")
    max_jobs: int = Field(description="Highest allowed `max_jobs`.")


@dataclass
class _Def:
    id: str
    label: str
    description: str
    min_jobs: int
    max_jobs: int
    default_jobs: Callable[[], int]
    unavailable: Callable[[], str]
    """Returns "" when the board is usable, else why not."""


def _always() -> str:
    return ""


def _usajobs_unavailable() -> str:
    if config.usajobs_configured():
        return ""
    return "Needs an API key (USAJOBS_API_KEY and USAJOBS_EMAIL)"


def _ats_unavailable() -> str:
    return "" if config.ATS_MAX_BOARDS > 0 else "Turned off on the server (ATS_MAX_BOARDS=0)"


def _ats_default() -> int:
    boards = max(1, math.ceil(config.ATS_MAX_BOARDS / ATS_PROVIDER_COUNT))
    return boards * config.ATS_JOBS_PER_BOARD


def _definitions() -> list[_Def]:
    defs = [
        _Def(
            "builtin_nyc",
            "Built In NYC",
            "New York City tech companies and their jobs.",
            1,
            100,
            lambda: BUILTIN_QUERIES * BUILTIN_RESULTS_PER_QUERY,
            _always,
        ),
        _Def(
            "conservation",
            "Conservation Job Board",
            "Conservation, wildlife and environmental jobs.",
            1,
            100,
            lambda: BUILTIN_QUERIES * BUILTIN_RESULTS_PER_QUERY,
            _always,
        ),
    ]
    for provider in ats.PROVIDERS.values():
        defs.append(
            _Def(
                provider.name,
                provider.label,
                f"Employer career boards on {provider.label}, found through Google.",
                1,
                40,
                _ats_default,
                _ats_unavailable,
            )
        )
    defs += [
        _Def(
            "usajobs",
            "USAJOBS",
            "US federal government jobs.",
            1,
            100,
            lambda: config.USAJOBS_MAX_QUERIES * config.USAJOBS_RESULTS,
            _usajobs_unavailable,
        ),
        _Def(
            "google",
            "Google job searches",
            "General Google searches for postings the other boards miss. Slow.",
            1,
            50,
            lambda: GOOGLE_QUERIES * GOOGLE_RESULTS_PER_QUERY,
            _always,
        ),
    ]
    return defs


def catalog() -> list[BoardInfo]:
    """Every board with its label, availability, default setting and limits."""
    out = []
    for d in _definitions():
        reason = d.unavailable()
        out.append(
            BoardInfo(
                id=d.id,
                label=d.label,
                description=d.description,
                available=not reason,
                unavailable_reason=reason,
                default=BoardSetting(
                    enabled=True, max_jobs=max(d.min_jobs, min(d.max_jobs, d.default_jobs()))
                ),
                min_jobs=d.min_jobs,
                max_jobs=d.max_jobs,
            )
        )
    return out


def default_config() -> BoardsConfig:
    """Today's behaviour: every board on at its default limit."""
    return {b.id: b.default.model_copy() for b in catalog()}


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return None
    return None


def normalize(raw: Any) -> BoardsConfig:
    """A complete, safe config from whatever a client sent.

    Unknown ids are dropped, `max_jobs` is clamped to the board's limits, and anything
    missing or malformed (including a missing `raw`) falls back to the board's default.
    """
    given = raw if isinstance(raw, dict) else {}
    result: BoardsConfig = {}
    for info in catalog():
        setting = given.get(info.id)
        if isinstance(setting, BoardSetting):
            setting = setting.model_dump()
        setting = setting if isinstance(setting, dict) else {}
        enabled = setting.get("enabled")
        jobs = _as_int(setting.get("max_jobs"))
        result[info.id] = BoardSetting(
            enabled=enabled if isinstance(enabled, bool) else info.default.enabled,
            max_jobs=info.default.max_jobs
            if jobs is None
            else max(info.min_jobs, min(info.max_jobs, jobs)),
        )
    return result


def is_on(boards: BoardsConfig, board_id: str) -> bool:
    """True when the board is enabled in `boards` and available (e.g. USAJOBS has its key).

    `enabled` is the user's intent and stays True by default even for a board that is
    unavailable right now, so a config saved before the key was added keeps its meaning.
    """
    info = next((b for b in catalog() if b.id == board_id), None)
    setting = boards.get(board_id)
    return bool(info and info.available and setting and setting.enabled)


def effective_limit(boards: BoardsConfig, board_id: str) -> int:
    """The board's `max_jobs`, or 0 when it is off or unavailable."""
    return boards[board_id].max_jobs if is_on(boards, board_id) else 0


def on_boards(boards: BoardsConfig) -> list[str]:
    return [b.id for b in catalog() if is_on(boards, b.id)]


def off_boards(boards: BoardsConfig) -> list[str]:
    """Boards that won't be searched: turned off by the user or unavailable."""
    return [b.id for b in catalog() if not is_on(boards, b.id)]
