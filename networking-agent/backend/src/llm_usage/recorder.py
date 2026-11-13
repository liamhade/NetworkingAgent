"""Append one CSV row per LLM call to `config.LLM_USAGE_LOG`."""

import csv
import io
import logging
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import config

log = logging.getLogger(__name__)


@dataclass
class UsageRow:
    timestamp: str
    """ISO 8601 UTC time the call finished."""
    user_id: str
    request_id: str
    search_id: str
    purpose: str
    provider: str
    model: str
    status: str
    """`ok` or `error`."""
    input_tokens: int | None
    """Uncached input tokens (cache reads/writes are in their own columns)."""
    cache_read_tokens: int | None
    cache_write_5m_tokens: int | None
    cache_write_1h_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    """All input (uncached + cache read + cache write) plus output."""
    cost_usd: float | None
    latency_ms: int | None
    error: str = ""


COLUMNS = [f.name for f in fields(UsageRow)]

_lock = threading.Lock()


def log_path() -> Path:
    return Path(config.LLM_USAGE_LOG)


def _format(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.8f}"
    return value


def write_row(row: UsageRow) -> None:
    """Append `row`, writing the header first if the file is new. Never raises."""
    try:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        values = asdict(row)
        path = log_path()
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.stat().st_size == 0:
                writer.writerow(COLUMNS)
            writer.writerow([_format(values[c]) for c in COLUMNS])
            # One write call per row keeps concurrent appends from interleaving mid-line.
            with path.open("a", encoding="utf-8", newline="") as file:
                file.write(buffer.getvalue())
    except Exception:  # noqa: BLE001
        log.warning("Could not write LLM usage row", exc_info=True)
