"""Per-URL method registry: which method `auto` should try first for a page or site.

Rules are regexes searched against the full URL; the first match wins. Rules added with
`register()` are checked before the built-in ones, so a better method found later for a
site can be plugged in without touching the pipeline.
"""

import re
import threading

BLOCKED = "blocked"

_BUILTIN_RULES: list[tuple[str, str]] = [
    (r"^https?://([a-z0-9-]+\.)?linkedin\.com/(in|pub)/", BLOCKED),
    (r"^https?://(job-)?boards(\.eu)?\.greenhouse\.io/[^/?#]+/jobs/\d+", "greenhouse_api"),
    (r"^https?://(job-)?boards(\.eu)?\.greenhouse\.io/embed/job_app\?.*\bfor=", "greenhouse_api"),
    (r"^https?://jobs(\.eu)?\.lever\.co/[^/?#]+/[0-9a-f-]{36}", "lever_api"),
    (r"^https?://jobs\.ashbyhq\.com/[^/?#]+/[0-9a-f-]{36}", "ashby_api"),
    (r"^https?://(www\.)?builtin[a-z]*\.com/job/", "jsonld"),
]

_lock = threading.Lock()
_custom: list[tuple[re.Pattern[str], str]] = []
_builtin: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p, re.IGNORECASE), m) for p, m in _BUILTIN_RULES
]


def register(pattern: str, method: str) -> None:
    """Prefer `method` for URLs matching `pattern` (checked before built-in rules).

    `method` must be a known method name or `"blocked"`; validated by `read_page` at use.
    """
    with _lock:
        _custom.insert(0, (re.compile(pattern, re.IGNORECASE), method))


def unregister_all() -> None:
    """Remove every rule added with `register()` (used by tests)."""
    with _lock:
        _custom.clear()


def match(url: str) -> str | None:
    """The method for `url`, or None if no rule matches."""
    with _lock:
        rules = [*_custom, *_builtin]
    return next((method for pattern, method in rules if pattern.search(url)), None)
