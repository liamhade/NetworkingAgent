"""Who/what an LLM call is for, carried through `contextvars` instead of arguments.

`usage_context(user_id=..., search_id=...)` sets the values for a `with` block.
`bind_context(iterator, ...)` does the same for a generator that is advanced from
different threads/contexts (e.g. a Starlette `StreamingResponse`), by running every
step inside one dedicated `contextvars.Context`.
"""

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class UsageContext:
    user_id: str = ""
    request_id: str = ""
    search_id: str = ""
    purpose: str = ""


_EMPTY = UsageContext()
_current: contextvars.ContextVar[UsageContext | None] = contextvars.ContextVar(
    "llm_usage_context", default=None
)


def current() -> UsageContext:
    return _current.get() or _EMPTY


def _merged(**fields: str | None) -> UsageContext:
    return replace(current(), **{k: v for k, v in fields.items() if v is not None})


@contextmanager
def usage_context(
    *,
    user_id: str | None = None,
    request_id: str | None = None,
    search_id: str | None = None,
    purpose: str | None = None,
) -> Iterator[UsageContext]:
    """Set (and afterwards restore) the usage context; unset fields are inherited."""
    token = _current.set(
        _merged(user_id=user_id, request_id=request_id, search_id=search_id, purpose=purpose)
    )
    try:
        yield current()
    finally:
        _current.reset(token)


def bind_context(
    iterator: Iterator[T],
    *,
    user_id: str | None = None,
    request_id: str | None = None,
    search_id: str | None = None,
    purpose: str | None = None,
) -> Iterator[T]:
    """Yield from `iterator`, running each step with the given usage context set."""
    ctx = contextvars.copy_context()
    value = _merged(user_id=user_id, request_id=request_id, search_id=search_id, purpose=purpose)
    ctx.run(_current.set, value)
    sentinel = object()
    while True:
        item = ctx.run(next, iterator, sentinel)
        if item is sentinel:
            return
        yield item  # type: ignore[misc]
