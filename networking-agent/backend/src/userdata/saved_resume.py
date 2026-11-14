"""The user's latest resume PDF, compressed on disk, plus its parsed profile.

Layout: `<DATABASE_DIR>/users/<user_id>/resume/`:

    resume.pdf.gz   the uploaded bytes, gzip level 9 (lossless: the download is byte-identical)
    resume.json     {"filename", "size", "stored_size", "uploaded_at", "profile"}

Only the latest resume is kept; saving replaces both files. The parsed `profile` is cached
in the metadata so returning to the search page never re-parses (no LLM call).
The folder is git-ignored (personal data). Keep all resume storage in this module
(Supabase Storage later).
"""

import gzip
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from schemas import ResumeProfile
from userdata import accounts, storage

_lock = threading.Lock()
_PDF_NAME = "resume.pdf.gz"
_META_NAME = "resume.json"


class SavedResume(BaseModel):
    filename: str
    size: int
    """Bytes of the original PDF."""
    stored_size: int
    """Bytes on disk after compression."""
    uploaded_at: datetime
    profile: ResumeProfile


def _folder(user_id: str) -> Path:
    return accounts.user_dir(user_id) / "resume"


def save(user_id: str, filename: str, data: bytes, profile: ResumeProfile) -> SavedResume:
    """Compress and store `data` as the user's resume, replacing any earlier one."""
    packed = gzip.compress(data, compresslevel=9, mtime=0)
    meta = SavedResume(
        filename=filename or "resume.pdf",
        size=len(data),
        stored_size=len(packed),
        uploaded_at=datetime.now(UTC),
        profile=profile,
    )
    folder = _folder(user_id)
    with _lock:
        folder.mkdir(parents=True, exist_ok=True)
        pdf_tmp = folder / (_PDF_NAME + ".tmp")
        pdf_tmp.write_bytes(packed)
        pdf_tmp.replace(folder / _PDF_NAME)
        storage.write_atomic(folder / _META_NAME, json.loads(meta.model_dump_json()))
    return meta


def get(user_id: str) -> SavedResume | None:
    """The saved resume's metadata and profile, or None (also if the file is unreadable)."""
    path = _folder(user_id) / _META_NAME
    with _lock:
        if not path.is_file():
            return None
        try:
            return SavedResume.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None


def read_pdf(user_id: str) -> bytes | None:
    """The original PDF bytes, or None if nothing is saved."""
    path = _folder(user_id) / _PDF_NAME
    with _lock:
        if not path.is_file():
            return None
        try:
            return gzip.decompress(path.read_bytes())
        except (OSError, EOFError):
            return None


def delete(user_id: str) -> bool:
    """Remove the saved resume. True if there was one."""
    folder = _folder(user_id)
    found = False
    with _lock:
        for name in (_PDF_NAME, _META_NAME):
            path = folder / name
            if path.is_file():
                path.unlink()
                found = True
    return found
