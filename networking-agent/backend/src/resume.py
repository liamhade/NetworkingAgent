"""Turn an uploaded resume PDF into the hero form's fields."""

import io

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from llm import get_llm
from llm_usage import run_config
from schemas import ResumeProfile

MAX_RESUME_CHARS = 60_000

SYSTEM_PROMPT = """You read resumes and summarize them for a job-search assistant.
Write `background` in the first person ("I am a ..."), 2-5 sentences covering current
role, years of experience, key skills, notable accomplishments and education.
Only use facts that appear in the resume. Use an empty string for unknown fields."""


class ResumeError(ValueError):
    """The upload could not be read as a resume."""


def extract_pdf_text(data: bytes) -> str:
    """All text in the PDF, page by page."""
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except (PdfReadError, ValueError, OSError) as exc:
        raise ResumeError(f"Could not read PDF: {exc}") from exc
    text = text.strip()
    if not text:
        raise ResumeError("No text found in the PDF (is it a scanned image?).")
    return text[:MAX_RESUME_CHARS]


def parse_resume(data: bytes, llm: BaseChatModel | None = None) -> ResumeProfile:
    """Extract a `ResumeProfile` from PDF bytes."""
    text = extract_pdf_text(data)
    model = (llm or get_llm()).with_structured_output(ResumeProfile, method="json_schema")
    result = model.invoke(
        [SystemMessage(SYSTEM_PROMPT), HumanMessage(f"<resume>\n{text}\n</resume>")],
        config=run_config("parse_resume"),
    )
    return result if isinstance(result, ResumeProfile) else ResumeProfile.model_validate(result)
