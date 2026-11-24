"""The registered ATS providers. Adding one = one module + one entry in `PROVIDERS`."""

from .ashby import ASHBY
from .base import Provider
from .greenhouse import GREENHOUSE
from .lever import LEVER
from .models import BoardRef
from .workable import WORKABLE

PROVIDERS: dict[str, Provider] = {p.name: p for p in (GREENHOUSE, LEVER, ASHBY, WORKABLE)}
"""Provider name -> provider, in the order the pipeline searches them."""


def get_provider(name: str) -> Provider:
    """The provider called `name`; raises `KeyError` for an unknown name."""
    try:
        return PROVIDERS[name]
    except KeyError:
        raise KeyError(f"Unknown ATS provider: {name!r}") from None


def parse_url(url: str) -> BoardRef | None:
    """The board a URL points at, on whichever registered provider hosts it."""
    for provider in PROVIDERS.values():
        ref = provider.parse_url(url)
        if ref is not None:
            return ref
    return None
