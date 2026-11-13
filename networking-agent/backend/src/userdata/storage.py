"""Small JSON-file helpers shared by the per-user stores (statuses, pins)."""

import json
from pathlib import Path


def read_keyed(path: Path, kinds: tuple[str, ...]) -> dict[str, dict[str, dict]]:
    """`{kind: {key: entry}}` from `path`; a missing or corrupt file reads as empty."""
    data: object = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}  # A corrupt file must not take the page down.
    if not isinstance(data, dict):
        data = {}
    return {kind: dict(data.get(kind) or {}) for kind in kinds}


def write_atomic(path: Path, data: object) -> None:
    """Write JSON via a tmp file + replace, so readers never see a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
