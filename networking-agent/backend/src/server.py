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
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

import boards
import config
import pipeline
import resume
import search_runs
import tools
from entities import catalog, keys
from llm_usage import usage_context
from schemas import (
    AgentEvent,
    CompanyEntity,
    CompanyResult,
    EntityPin,
    EntityStatus,
    EntityStatusKind,
    FindPeopleRequest,
    JobEntity,
    PersonEntity,
    PinKind,
    PinUpdate,
    ResumeProfile,
    SavedSearch,
    SearchRequest,
    SearchSummary,
    StatusUpdate,
)
from userdata import (
    accounts,
    history,
    pins,
    saved_resume,
    search_configs,
    search_params,
    statuses,
)
from userdata.search_configs import SearchConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

MAX_RESUME_BYTES = 10 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI):
    accounts.seed()
    history.mark_interrupted()  # Nothing survives a restart: stale `running` -> failed.
    yield
    tools.shutdown()


app = FastAPI(title="Networking Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
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
    """Read an uploaded PDF resume and return pre-filled hero form fields.

    A readable resume is also saved (compressed) as the user's latest, with its parsed
    profile, so returning to the search page needs no re-upload (`GET /api/resume/saved`).
    """
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
            profile = resume.parse_resume(data)
    except resume.ResumeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        saved_resume.save(user.id, file.filename or "resume.pdf", data, profile)
    except Exception:  # noqa: BLE001
        log.exception("Could not save the resume")  # The parsed fields still go back.
    return profile


@app.get("/api/resume/saved")
def get_saved_resume(user: CurrentUser) -> saved_resume.SavedResume | None:
    """The user's saved resume (file name, sizes, upload time, parsed profile), or null."""
    return saved_resume.get(user.id)


@app.get("/api/resume/saved/file")
def download_saved_resume(user: CurrentUser) -> Response:
    """The saved resume as the original PDF."""
    meta = saved_resume.get(user.id)
    data = saved_resume.read_pdf(user.id) if meta else None
    if meta is None or data is None:
        raise HTTPException(status_code=404, detail="No saved resume.")
    name = "".join(c for c in meta.filename if c.isprintable() and c not in '"' + chr(92))
    return Response(
        data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.delete("/api/resume/saved", status_code=204)
def delete_saved_resume(user: CurrentUser) -> Response:
    """Forget the saved resume. Idempotent."""
    saved_resume.delete(user.id)
    return Response(status_code=204)


def _sse(event: AgentEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"


def _follow(events: Iterator[AgentEvent | None]) -> Iterator[str]:
    """Server-Sent Events for a background search; quiet spells send a comment as keepalive."""
    for event in events:
        yield ": keepalive\n\n" if event is None else _sse(event)


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@app.post("/api/search")
def search(request: SearchRequest, user: CurrentUser) -> StreamingResponse:
    """Start the networking agent and stream its Server-Sent Events (`data: <json>` lines).

    The search runs in the background and is saved right away as `running`, so closing the
    stream (leaving the page) does not stop it: follow it again with
    `GET /api/searches/{id}/events`. The first event is `started` (carrying the id).
    """
    search_id = history.new_search_id()
    try:
        search_params.save(user.id, request)
    except Exception:  # noqa: BLE001
        log.exception("Could not save search parameters")  # Never block the search.
    search_runs.start(user.id, request, search_id)
    events = search_runs.attach(user.id, search_id)
    assert events is not None
    return StreamingResponse(_follow(events), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.get("/api/searches/{search_id}/events")
def search_events(search_id: str, user: CurrentUser) -> StreamingResponse:
    """Follow one search from its start: progress, then the result (or error) and `saved`.

    Works while it runs and after it finished (replayed from the saved record).
    """
    events = search_runs.attach(user.id, search_id)
    if events is None:
        raise HTTPException(status_code=404, detail="Search not found.")
    return StreamingResponse(_follow(events), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.get("/api/search/boards")
def search_boards() -> list[boards.BoardInfo]:
    """The job boards a search can use: label, default setting, limits and availability.

    The frontend renders its configuration panel from this list. A search sends back
    `boards: {board_id: {enabled, max_jobs}}` in `POST /api/search`.
    """
    return boards.catalog()


@app.get("/api/search/params")
def get_search_params(user: CurrentUser) -> search_params.SearchParams | None:
    """The user's last saved search parameters (a `SearchRequest`-shaped draft), or null."""
    return search_params.get(user.id)


@app.put("/api/search/params")
def put_search_params(
    params: search_params.SearchParams, user: CurrentUser
) -> search_params.SearchParams:
    """Save the current search parameters; `boards` is normalized. Fields may be empty."""
    return search_params.save(user.id, params)


class NewSearchConfig(BaseModel):
    """`POST /api/search/configs`: the current form, and an optional name."""

    params: search_params.SearchParams
    name: str | None = None


class SearchConfigUpdate(BaseModel):
    """`PATCH /api/search/configs/{id}`: rename and/or overwrite the params."""

    name: str | None = None
    params: search_params.SearchParams | None = None


def _config_or_404(config: SearchConfig | None) -> SearchConfig:
    if config is None:
        raise HTTPException(status_code=404, detail="Search configuration not found.")
    return config


@app.get("/api/search/configs")
def list_search_configs(user: CurrentUser) -> list[SearchConfig]:
    """The user's saved search configurations, in creation order."""
    return search_configs.list_configs(user.id)


@app.post("/api/search/configs", status_code=201)
def create_search_config(body: NewSearchConfig, user: CurrentUser) -> SearchConfig:
    """Save the current parameters. No name: "Search Configuration #n" (n never reused)."""
    try:
        return search_configs.create(user.id, body.params, body.name)
    except search_configs.InvalidName as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.patch("/api/search/configs/{config_id}")
def update_search_config(
    config_id: str, body: SearchConfigUpdate, user: CurrentUser
) -> SearchConfig:
    """Rename a configuration and/or overwrite its parameters."""
    try:
        return _config_or_404(search_configs.update(user.id, config_id, body.name, body.params))
    except search_configs.InvalidName as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.delete("/api/search/configs/{config_id}", status_code=204)
def delete_search_config(config_id: str, user: CurrentUser) -> Response:
    if not search_configs.delete(user.id, config_id):
        raise HTTPException(status_code=404, detail="Search configuration not found.")
    return Response(status_code=204)


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
    return catalog.companies(history.load_searches(user.id, only_done=True))


@app.get("/api/entities/jobs")
def list_jobs(user: CurrentUser) -> list[JobEntity]:
    """Every job in the current user's searches, de-duplicated, most recently seen first."""
    return catalog.jobs(history.load_searches(user.id, only_done=True))


@app.get("/api/entities/people")
def list_people(user: CurrentUser) -> list[PersonEntity]:
    """Every person in the current user's searches, de-duplicated, most recently seen first."""
    return catalog.people(history.load_searches(user.id, only_done=True))
