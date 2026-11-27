"""Where the FastAPI server lives.

Run from `backend`:

    .venv\\Scripts\\python.exe -m uvicorn server:app --app-dir src --port 8000
"""

import logging
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, TypeVar

from fastapi import Body, Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator

import boards
import config
import pipeline
import resume
import search_runs
import tools
from admin import overview as admin_overview
from auth import access, passwords, session, supabase
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
    if config.LOCAL_DEV_MODE:
        log.warning(
            "LOCAL_DEV_MODE is on: any sign-in from this machine is TEST_USER. Never deploy it."
        )
    accounts.seed()
    history.mark_interrupted()  # Nothing survives a restart: stale `running` -> failed.
    yield
    tools.shutdown()


app = FastAPI(title="Enishi", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
app.add_middleware(session.SessionMiddleware)


@app.exception_handler(supabase.AuthError)
def _auth_error(_: Request, exc: supabase.AuthError) -> JSONResponse:
    return JSONResponse({"detail": exc.message}, status_code=exc.status)


CurrentUser = Annotated[accounts.User, Depends(session.current_user)]
"""Who is calling. Every per-user endpoint takes this, so auth plugs in at one place."""


class Me(accounts.User):
    is_admin: bool = False
    """The owner (`OWNER_EMAIL`): the page shows the Admin tab."""


@app.get("/api/me")
def me(user: CurrentUser, request: Request) -> Me:
    """The signed-in account (TEST_USER without accounts), and whether it is the owner."""
    return Me(**user.model_dump(), is_admin=session.is_admin(request))


AdminOnly = [Depends(session.require_admin)]


class WhitelistRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @field_validator("email", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


@app.get("/api/admin/users", dependencies=AdminOnly)
def admin_users() -> admin_overview.AdminOverview:
    """Every known email with its access status and LLM usage (owner only)."""
    return admin_overview.build()


@app.put("/api/admin/whitelist", dependencies=AdminOnly)
def admin_whitelist_add(body: WhitelistRequest) -> access.Entry:
    """Let an email in: approves a request, or pre-approves an email that hasn't asked."""
    entry = access.approve(body.email)
    log.info("Owner approved %s", entry.email)
    return entry


class TemporaryPassword(BaseModel):
    email: str
    password: str
    """Shown to the owner once, to pass on; the user should change it after signing in."""


@app.post("/api/admin/users/{email}/reset-password", dependencies=AdminOnly)
def admin_reset_password(email: str) -> TemporaryPassword:
    """Give an account a new temporary password (owner only). No email is sent."""
    _require_auth()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Not an email address.")
    password = passwords.reset(email)
    log.info("Owner reset the password of %s", access.normalize(email))
    return TemporaryPassword(email=access.normalize(email), password=password)


@app.delete("/api/admin/whitelist/{email}", dependencies=AdminOnly)
def admin_whitelist_remove(email: str) -> access.Entry:
    """Take an email off the whitelist (or turn down its request); blocked at once."""
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Not an email address.")
    try:
        entry = access.deny(email)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log.info("Owner removed %s from the whitelist", entry.email)
    return entry


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1, max_length=128)


class SignupRequest(LoginRequest):
    password: str = Field(min_length=8, max_length=128)


class AuthConfig(BaseModel):
    enabled: bool
    """False in development: everyone is TEST_USER and there is nothing to sign in to."""
    request_email: str = ""
    """Where people email their access request (`ACCESS_REQUEST_EMAIL`); empty if unset."""
    local_dev: bool = False
    """`LOCAL_DEV_MODE`: any credentials sign in as TEST_USER."""


@app.get("/api/auth/config")
def auth_config() -> AuthConfig:
    if config.LOCAL_DEV_MODE:
        return AuthConfig(enabled=True, local_dev=True)
    enabled = config.auth_enabled()
    return AuthConfig(enabled=enabled, request_email=config.ACCESS_REQUEST_EMAIL if enabled else "")


_NOT_APPROVED = {
    "pending": "Your access request is waiting for approval. If you haven't yet, send the "
    "request email so your address can be confirmed.",
    "denied": "Your access request wasn't approved.",
}


def _access_refused(status: str) -> JSONResponse:
    """403 for an account the owner hasn't approved; `access` tells the page which."""
    return JSONResponse({"detail": _NOT_APPROVED[status], "access": status}, status_code=403)


def _require_auth() -> None:
    """404 unless real Supabase accounts are in use (not without them, not in LOCAL_DEV_MODE)."""
    if config.LOCAL_DEV_MODE:
        raise HTTPException(status_code=404, detail="There are no passwords in local dev mode.")
    if not config.auth_enabled():
        raise HTTPException(status_code=404, detail="Accounts are not enabled on this server.")


def _dev_sign_in(request: Request) -> JSONResponse:
    """`LOCAL_DEV_MODE`: sign in as TEST_USER whatever was typed (loopback requests only)."""
    if not session.is_local_request(request.scope):
        raise HTTPException(
            status_code=403, detail="Local dev mode only signs in from this machine (localhost)."
        )
    response = JSONResponse(accounts.get_current_user().model_dump(mode="json"))
    session.set_dev_cookie(response)
    return response


AuthBody = Annotated[dict[str, Any] | None, Body()]
"""Sign-in bodies are checked inside the endpoint, so LOCAL_DEV_MODE can take anything."""


_Model = TypeVar("_Model", bound=BaseModel)


def _parse(model: type[_Model], body: dict[str, Any] | None) -> _Model:
    try:
        return model.model_validate(body or {})
    except ValidationError as exc:
        raise RequestValidationError(exc.errors(include_url=False)) from exc


def _signed_in(request: Request, new_session: supabase.Session) -> JSONResponse:
    user = accounts.ensure_user(new_session.user.id, new_session.user.email or new_session.user.id)
    response = JSONResponse(user.model_dump(mode="json"))
    session.set_session_cookies(response, new_session, session.is_secure(request))
    return response


@app.post("/api/auth/login")
def login(request: Request, raw: AuthBody = None) -> JSONResponse:
    """Sign in with email + password; sets the session cookies once the owner approved them."""
    if config.LOCAL_DEV_MODE:
        return _dev_sign_in(request)
    _require_auth()
    body = _parse(LoginRequest, raw)
    new_session = supabase.password_login(body.email.strip(), body.password)
    user = new_session.user
    email = user.email or body.email
    status = access.status_of(user.id, email)
    if status is None:  # account made outside the app (e.g. Supabase dashboard): ask
        status = access.request(email, user.id).status
    if status != "approved":
        supabase.logout(new_session.access_token)
        return _access_refused(status)
    return _signed_in(request, new_session)


@app.post("/api/auth/signup")
def signup(request: Request, raw: AuthBody = None) -> JSONResponse:
    """Request access: create the account, pending until the owner approves the email.

    202 `{"access": "pending"}` (no session yet), or the signed-in user if the email was
    approved in advance. In LOCAL_DEV_MODE: signs in as TEST_USER, like `login`.
    """
    if config.LOCAL_DEV_MODE:
        return _dev_sign_in(request)
    _require_auth()
    body = _parse(SignupRequest, raw)
    email = access.normalize(body.email)
    earlier = access.get(email)
    if earlier is not None and earlier.status == "denied":
        return _access_refused("denied")
    created = supabase.admin_create_user(email, body.password)
    entry = access.request(email, created.id)
    log.info("Access request from account %s: %s", created.id, entry.status)
    if entry.status == "approved":
        return _signed_in(request, supabase.password_login(email, body.password))
    return JSONResponse({"access": "pending"}, status_code=202)


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request) -> Response:
    """Sign out: revoke the session at Supabase and drop the cookies."""
    access = request.cookies.get(session.ACCESS_COOKIE)
    if access and config.accounts_active():
        session.forget_token(access)
        supabase.logout(access)
    response = Response(status_code=204)
    session.clear_session_cookies(response, session.is_secure(request))
    return response


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=passwords.MIN_LENGTH, max_length=128)


@app.post("/api/account/password", status_code=204)
def change_password(body: ChangePasswordRequest, request: Request) -> Response:
    """The signed-in user changes their own password (needs the current one)."""
    _require_auth()
    user = session.signed_in_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Please sign in.")
    passwords.change(user.id, user.email, body.current_password, body.new_password)
    log.info("Account %s changed its password", user.id)
    return Response(status_code=204)


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
    try:
        search_runs.start(user.id, request, search_id)
    except search_runs.TooManySearches as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
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


@app.post("/api/searches/{search_id}/cancel")
def cancel_search(search_id: str, user: CurrentUser) -> SearchSummary:
    """Cancel a running search (saved as `cancelled`); 404 if unknown, 409 if not running."""
    try:
        return search_runs.cancel(user.id, search_id)
    except search_runs.SearchNotFound as exc:
        raise HTTPException(status_code=404, detail="Search not found.") from exc
    except search_runs.SearchNotRunning as exc:
        raise HTTPException(status_code=409, detail="That search is not running.") from exc


@app.delete("/api/searches/{search_id}", status_code=204)
def delete_search(search_id: str, user: CurrentUser) -> Response:
    """Delete a saved search (and so its entities from the entity pages).

    404 if unknown; 409 if it is still running (cancel it first). Applied/connected marks
    and pins are kept: they are stored per entity, not per search.
    """
    try:
        found = history.delete_search(user.id, search_id)
    except history.SearchRunning as exc:
        raise HTTPException(
            status_code=409, detail="That search is still running. Cancel it before deleting."
        ) from exc
    if not found:
        raise HTTPException(status_code=404, detail="Search not found.")
    return Response(status_code=204)


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
    its jobs, or only from the user's school with `same_school`), save them into the search
    and return the updated company.

    A plain `def`, so FastAPI runs it in its threadpool: several requests (other companies,
    or the same one twice) run at once. Their Google searches queue in the one shared
    Chrome worker; saving is serialized per search (`history.update_search`).
    """
    try:
        with usage_context(user_id=user.id, request_id=uuid.uuid4().hex, search_id=search_id):
            return pipeline.find_people(
                user.id, search_id, body.company_key, body.job_key, same_school=body.same_school
            )
    except pipeline.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except pipeline.NoSchool as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


def mount_frontend(target: FastAPI, dist: Path) -> bool:
    """Serve the built frontend (`npm run build`) at `/`, after every `/api` route.

    One origin then serves both, so the frontend's relative `/api` calls need no proxy.
    Does nothing (returns False) when `dist` has no `index.html`, e.g. in development,
    where Vite serves the frontend.
    """
    if not (dist / "index.html").is_file():
        return False
    target.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return True


if mount_frontend(app, config.FRONTEND_DIST):
    log.info("Serving the frontend from %s", config.FRONTEND_DIST)
