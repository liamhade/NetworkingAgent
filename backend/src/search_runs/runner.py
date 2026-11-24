"""Run a search in a background thread and let any number of clients follow it."""

import logging
import threading
from collections.abc import Iterator

import config
import pipeline
from entities import keys
from llm_usage import usage_context
from schemas import (
    AgentEvent,
    CancelledEvent,
    ErrorEvent,
    ResultEvent,
    SavedEvent,
    SavedSearch,
    SearchRequest,
    SearchSummary,
    StartedEvent,
    StatusEvent,
    TraceEvent,
    TraceStep,
)
from userdata import history

log = logging.getLogger(__name__)

KEEPALIVE_SECONDS = 15.0
"""How long a stream waits for news before yielding `None` (so dead clients are noticed)."""


class SearchNotFound(LookupError):
    """No such search for this user."""


class SearchNotRunning(RuntimeError):
    """The search already ended (done, failed or cancelled), so it cannot be cancelled."""


class TooManySearches(RuntimeError):
    """`config.MAX_CONCURRENT_SEARCHES` searches are already running."""


class _Run:
    """The live events of one running search, shared by every client following it."""

    def __init__(self) -> None:
        self.events: list[AgentEvent] = []
        self.finished = False
        self.changed = threading.Condition()
        self.cancel_requested = threading.Event()
        # Whoever settles the run first (the worker with an outcome, or `cancel`) wins; the
        # other sees `settled` and backs off, so a record never goes done -> cancelled.
        self.settle = threading.Lock()
        self.settled = False

    def publish(self, event: AgentEvent) -> None:
        with self.changed:
            self.events.append(event)
            self.changed.notify_all()

    def finish(self) -> None:
        with self.changed:
            self.finished = True
            self.changed.notify_all()

    def follow(self) -> Iterator[AgentEvent | None]:
        """Every event so far, then new ones; `None` after a quiet spell, until finished."""
        index = 0
        while True:
            with self.changed:
                if index >= len(self.events) and not self.finished:
                    self.changed.wait(KEEPALIVE_SECONDS)
                batch = self.events[index:]
                done = self.finished and not batch
            if done:
                return
            if not batch:
                yield None
            yield from batch
            index += len(batch)


_runs: dict[tuple[str, str], _Run] = {}
_runs_guard = threading.Lock()


def start(user_id: str, request: SearchRequest, search_id: str) -> None:
    """Save the search as `running` and run it in the background.

    Raises `TooManySearches` (nothing saved) when the concurrency cap is reached. A cancelled
    search that is still winding down (it stops at its next step) no longer counts.
    """
    run = _Run()
    with _runs_guard:
        active = sum(1 for other in _runs.values() if not other.cancel_requested.is_set())
        if active >= config.MAX_CONCURRENT_SEARCHES:
            raise TooManySearches(
                f"{active} searches are already running (the limit is "
                f"{config.MAX_CONCURRENT_SEARCHES}). Wait for one to finish or cancel one, "
                "then try again."
            )
        record = history.start_search(user_id, request, search_id)
        run.publish(StartedEvent(search=_summary(record)))
        _runs[(user_id, search_id)] = run
    threading.Thread(
        target=_execute,
        args=(run, user_id, request, search_id),
        name=f"search-{search_id[:8]}",
        daemon=True,
    ).start()


def _execute(run: _Run, user_id: str, request: SearchRequest, search_id: str) -> None:
    trace: list[TraceStep] | None = None
    events = None
    try:
        with usage_context(user_id=user_id, request_id=search_id, search_id=search_id):
            events = pipeline.run_search(request)
            for event in events:
                if run.cancel_requested.is_set():
                    return  # Cancelled between steps; `cancel` already saved and announced it.
                if isinstance(event, TraceEvent):
                    trace = event.steps  # Saved with the results; not streamed.
                elif isinstance(event, ResultEvent):
                    results = keys.annotate(event.data)
                    with run.settle:
                        if run.settled:
                            return
                        run.settled = True
                        record = history.finish_search(user_id, search_id, results, trace)
                    if record is None:
                        raise RuntimeError("The search record disappeared.")
                    run.publish(ResultEvent(data=results))
                    run.publish(SavedEvent(search=_summary(record)))
                    return
                elif isinstance(event, ErrorEvent):
                    _fail(run, user_id, search_id, event.message)
                    return
                elif isinstance(event, StatusEvent):
                    _record_message(user_id, search_id, event.message)
                    run.publish(event)
        _fail(run, user_id, search_id, "Search failed: it ended without results.")
    except Exception as exc:  # noqa: BLE001
        log.exception("Search failed")
        _fail(run, user_id, search_id, f"Search failed: {exc}")
    finally:
        try:
            close = getattr(events, "close", None)  # Plain iterators (in tests) have none.
            if close is not None:
                close()  # Stops a cancelled pipeline at the step it is in.
        except Exception:  # noqa: BLE001
            log.exception("Could not close the search pipeline")
        finally:
            # Finished (and saved) before it leaves the registry, so a late `attach` finds
            # the final record on disk.
            run.finish()
            with _runs_guard:
                if _runs.get((user_id, search_id)) is run:
                    del _runs[(user_id, search_id)]


def cancel(user_id: str, search_id: str) -> SearchSummary:
    """Cancel a running search: it is saved as `cancelled` and its streams end at once.

    Cooperative: the pipeline stops at its next step boundary (a Google/LLM call already in
    flight finishes first, and its output is discarded). Raises `SearchNotFound` or
    `SearchNotRunning`.
    """
    with _runs_guard:
        run = _runs.get((user_id, search_id))
    if run is None:
        if history.get_search(user_id, search_id) is None:
            raise SearchNotFound(search_id)
        raise SearchNotRunning(search_id)
    with run.settle:
        if run.settled:
            raise SearchNotRunning(search_id)
        run.settled = True
        run.cancel_requested.set()
        record = history.cancel_search(user_id, search_id)
    if record is None:
        raise SearchNotFound(search_id)
    run.publish(CancelledEvent(search=_summary(record)))
    run.finish()
    return _summary(record)


def _record_message(user_id: str, search_id: str, message: str) -> None:
    try:
        history.add_message(user_id, search_id, message)
    except Exception:  # noqa: BLE001
        log.exception("Could not save a search progress message")  # Never stop the search.


def _fail(run: _Run, user_id: str, search_id: str, message: str) -> None:
    with run.settle:
        if run.settled:
            return  # Cancelled first.
        run.settled = True
        try:
            history.fail_search(user_id, search_id, message)
        except Exception:  # noqa: BLE001
            log.exception("Could not save the search failure")
    run.publish(ErrorEvent(message=message))


def _summary(record: SavedSearch) -> SearchSummary:
    return SearchSummary(
        id=record.id, title=record.title, created_at=record.created_at, status=record.status
    )


def attach(user_id: str, search_id: str) -> Iterator[AgentEvent | None] | None:
    """Follow a search from its first progress message; None if it doesn't exist.

    A running search streams live (`None` items are keepalive ticks). A finished one is
    replayed from its saved record: progress messages, then the result, error or cancellation.
    """
    with _runs_guard:
        run = _runs.get((user_id, search_id))
    if run is not None:
        return run.follow()
    record = history.get_search(user_id, search_id)
    if record is None:
        return None
    return iter(_replay(record))


def _replay(record: SavedSearch) -> list[AgentEvent]:
    events: list[AgentEvent] = [StartedEvent(search=_summary(record))]
    events += [StatusEvent(message=message) for message in record.messages]
    if record.status == "done":
        events.append(ResultEvent(data=keys.annotate(record.results)))
        events.append(SavedEvent(search=_summary(record)))
    elif record.status == "cancelled":
        events.append(CancelledEvent(search=_summary(record)))
    else:
        # `running` with no live run only happens for an orphan; report it as interrupted.
        events.append(ErrorEvent(message=record.error or history.INTERRUPTED_MESSAGE))
    return events
