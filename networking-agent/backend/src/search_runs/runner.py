"""Run a search in a background thread and let any number of clients follow it."""

import logging
import threading
from collections.abc import Iterator

import pipeline
from entities import keys
from llm_usage import usage_context
from schemas import (
    AgentEvent,
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


class _Run:
    """The live events of one running search, shared by every client following it."""

    def __init__(self) -> None:
        self.events: list[AgentEvent] = []
        self.finished = False
        self.changed = threading.Condition()

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
    """Save the search as `running` and run it in the background."""
    record = history.start_search(user_id, request, search_id)
    run = _Run()
    run.publish(StartedEvent(search=_summary(record)))
    with _runs_guard:
        _runs[(user_id, search_id)] = run
    threading.Thread(
        target=_execute,
        args=(run, user_id, request, search_id),
        name=f"search-{search_id[:8]}",
        daemon=True,
    ).start()


def _execute(run: _Run, user_id: str, request: SearchRequest, search_id: str) -> None:
    trace: list[TraceStep] | None = None
    try:
        with usage_context(user_id=user_id, request_id=search_id, search_id=search_id):
            for event in pipeline.run_search(request):
                if isinstance(event, TraceEvent):
                    trace = event.steps  # Saved with the results; not streamed.
                elif isinstance(event, ResultEvent):
                    results = keys.annotate(event.data)
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
        # Finished (and saved) before it leaves the registry, so a late `attach` finds the
        # final record on disk.
        run.finish()
        with _runs_guard:
            _runs.pop((user_id, search_id), None)


def _record_message(user_id: str, search_id: str, message: str) -> None:
    try:
        history.add_message(user_id, search_id, message)
    except Exception:  # noqa: BLE001
        log.exception("Could not save a search progress message")  # Never stop the search.


def _fail(run: _Run, user_id: str, search_id: str, message: str) -> None:
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
    replayed from its saved record: progress messages, then the result or the error.
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
    else:
        # `running` with no live run only happens for an orphan; report it as interrupted.
        events.append(ErrorEvent(message=record.error or history.INTERRUPTED_MESSAGE))
    return events
