"""Where the FastAPI server lives.

Run from `networking-agent/backend`:

    .venv\\Scripts\\python.exe -m uvicorn server:app --app-dir src --port 8000
"""

import logging
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import agent
import config
import resume
import tools
from schemas import AgentEvent, ErrorEvent, ResumeProfile, SearchRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

MAX_RESUME_BYTES = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    tools.shutdown()


app = FastAPI(title="Networking Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": config.LLM_MODEL}


@app.post("/api/resume")
def parse_resume(file: Annotated[UploadFile, File()]) -> ResumeProfile:
    """Read an uploaded PDF resume and return pre-filled hero form fields."""
    is_pdf = file.content_type == "application/pdf" or (file.filename or "").lower().endswith(
        ".pdf"
    )
    if not is_pdf:
        raise HTTPException(status_code=415, detail="Please upload a PDF file.")
    data = file.file.read(MAX_RESUME_BYTES + 1)
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="PDF is larger than 10 MB.")
    try:
        return resume.parse_resume(data)
    except resume.ResumeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _sse(event: AgentEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


def _event_stream(request: SearchRequest) -> Iterator[str]:
    try:
        for event in agent.run_search(request):
            yield _sse(event)
    except Exception as exc:  # noqa: BLE001
        log.exception("Search failed")
        yield _sse(ErrorEvent(message=f"Search failed: {exc}"))


@app.post("/api/search")
def search(request: SearchRequest) -> StreamingResponse:
    """Run the networking agent. Streams Server-Sent Events (`data: <json>` lines)."""
    return StreamingResponse(
        _event_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
