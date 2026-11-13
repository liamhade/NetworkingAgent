"""Where the FastAPI server lives.

Run from `networking-agent/backend`:

    .venv\\Scripts\\python.exe -m uvicorn server:app --app-dir src --port 8000
"""

import logging
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import config
import pipeline
import resume
import tools
from entities import catalog, keys
from llm_usage import bind_context, usage_context
from schemas import (
    AgentEvent,
    CompanyEntity,
    CompanyResult,
    EntityPin,
    EntityStatus,
    EntityStatusKind,
    ErrorEvent,
    FindPeopleRequest,
    JobEntity,
    PersonEntity,
    PinKind,
    PinUpdate,
    ResultEvent,
    ResumeProfile,
    SavedEvent,
    SavedSearch,
    SearchRequest,
    SearchSummary,
    StatusUpdate,
    TraceEvent,
    TraceStep,
)
from userdata import accounts, history, pins, statuses

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

MAX_RESUME_BYTES = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI):
    accounts.seed()
    yield
    tools.shutdown()


app = FastAPI(title="Networking Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)


CurrentUser = Annotated[accounts.User, Depends(accounts.get_current_user)]
"""Who is calling. Every per-user endpoint takes this, so auth plugs in at one place."""


@app.get("/api/me")
def me(user: CurrentUser) -> accounts.User:
    """The account the app is running as (always TEST_USER until auth exists)."""
    return user


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": config.LLM_MODEL}


@app.post("/api/resume")
def parse_resume(file: Annotated[UploadFile, File()], user: CurrentUser) -> ResumeProfile:
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
        with usage_context(user_id=user.id, request_id=uuid.uuid4().hex):
            return resume.parse_resume(data)
    except resume.ResumeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _sse(event: AgentEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


def _event_stream(request: SearchRequest, user_id: str, search_id: str) -> Iterator[str]:
    trace: list[TraceStep] | None = None
    try:
        for event in pipeline.run_search(request):
            if isinstance(event, TraceEvent):
                trace = event.steps  # Saved with the results; not sent to the browser.
            elif isinstance(event, ResultEvent):
                event = ResultEvent(data=keys.annotate(event.data))
                yield _sse(event)
                yield from _save(user_id, request, event, search_id, trace)
            else:
                yield _sse(event)
    except Exception as exc:  # noqa: BLE001
        log.exception("Search failed")
        yield _sse(ErrorEvent(message=f"Search failed: {exc}"))


def _save(
    user_id: str,
    request: SearchRequest,
    event: ResultEvent,
    search_id: str,
    trace: list[TraceStep] | None = None,
) -> Iterator[str]:
    """Persist a finished search; a storage failure must not hide the results."""
    try:
        record = history.save_search(user_id, request, event.data, search_id=search_id, trace=trace)
    except Exception:  # noqa: BLE001
        log.exception("Could not save search to history")
        return
    summary = SearchSummary(id=record.id, title=record.title, created_at=record.created_at)
    yield _sse(SavedEvent(search=summary))


@app.post("/api/search")
def search(request: SearchRequest, user: CurrentUser) -> StreamingResponse:
    """Run the networking agent. Streams Server-Sent Events (`data: <json>` lines)."""
    search_id = history.new_search_id()
    # LLM usage rows are tagged with this user and the id the search is saved under.
    events = bind_context(
        _event_stream(request, user.id, search_id),
        user_id=user.id,
        request_id=search_id,
        search_id=search_id,
    )
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/searches")
def list_searches(user: CurrentUser) -> list[SearchSummary]:
    """The current user's previous searches, most recent first."""
    return history.list_searches(user.id)


@app.get("/api/searches/{search_id}")
def get_search(search_id: str, user: CurrentUser) -> SavedSearch:
    """One of the current user's previous searches, with the results to reopen it."""
    record = history.get_search(user.id, search_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Search not found.")
    # Re-key on read so older searches (and normalization changes) match current statuses.
    return record.model_copy(update={"results": keys.annotate(record.results)})


@app.post("/api/searches/{search_id}/people")
def find_people(search_id: str, body: FindPeopleRequest, user: CurrentUser) -> CompanyResult:
    """Find people to connect with at one company of a saved search (optionally for one of
    its jobs), save them into the search and return the updated company.

    A plain `def`, so FastAPI runs it in its threadpool: several requests (other companies,
    or the same one twice) run at once. Their Google searches queue in the one shared
    Chrome worker; saving is serialized per search (`history.update_search`).
    """
    try:
        with usage_context(user_id=user.id, request_id=uuid.uuid4().hex, search_id=search_id):
            return pipeline.find_people(user.id, search_id, body.company_key, body.job_key)
    except pipeline.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/statuses")
def get_statuses(user: CurrentUser) -> dict[EntityStatusKind, dict[str, bool]]:
    """The current user's APPLIED (jobs) / CONNECTED (people) toggles, by entity key."""
    return statuses.get_statuses(user.id)


@app.put("/api/statuses")
def set_status(update: StatusUpdate, user: CurrentUser) -> EntityStatus:
    """Set one toggle. Keys come from the `key` field on jobs/people in search results."""
    try:
        return statuses.set_status(user.id, update)
    except statuses.InvalidStatusKey as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/pins")
def get_pins(user: CurrentUser) -> dict[PinKind, dict[str, bool]]:
    """The current user's pinned companies / jobs / people, by entity key."""
    return pins.get_pins(user.id)


@app.put("/api/pins")
def set_pin(update: PinUpdate, user: CurrentUser) -> EntityPin:
    """Pin or unpin one entity. Keys come from `key` on search results and entity lists."""
    try:
        return pins.set_pin(user.id, update)
    except pins.InvalidPinKey as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/entities/companies")
def list_companies(user: CurrentUser) -> list[CompanyEntity]:
    """Every company in the current user's searches, de-duplicated, most recently seen first."""
    return catalog.companies(history.load_searches(user.id))


@app.get("/api/entities/jobs")
def list_jobs(user: CurrentUser) -> list[JobEntity]:
    """Every job in the current user's searches, de-duplicated, most recently seen first."""
    return catalog.jobs(history.load_searches(user.id))


@app.get("/api/entities/people")
def list_people(user: CurrentUser) -> list[PersonEntity]:
    """Every person in the current user's searches, de-duplicated, most recently seen first."""
    return catalog.people(history.load_searches(user.id))
