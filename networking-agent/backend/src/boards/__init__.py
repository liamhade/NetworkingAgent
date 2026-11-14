"""Which job boards a search uses, and how many jobs to gather from each.

`catalog()` is the single source of truth (ids, labels, defaults, limits, availability);
`GET /api/search/boards` serves it and the frontend renders from it. A search carries one
self-contained `boards` object, `{board_id: {"enabled": bool, "max_jobs": int}}`, which
`normalize()` makes complete and safe (unknown ids dropped, limits clamped, defaults for
what is missing). See `networking-agent/docs/search-board-config/plan.md`.
"""

from .catalog import (
    BoardInfo,
    BoardsConfig,
    BoardSetting,
    catalog,
    default_config,
    effective_limit,
    is_on,
    normalize,
    off_boards,
    on_boards,
)

__all__ = [
    "BoardInfo",
    "BoardSetting",
    "BoardsConfig",
    "catalog",
    "default_config",
    "effective_limit",
    "is_on",
    "normalize",
    "off_boards",
    "on_boards",
]
