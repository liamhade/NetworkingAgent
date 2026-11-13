"""The registered ATS providers. Adding one = one module + one entry in `PROVIDERS`."""

from .base import Provider
from .greenhouse import GREENHOUSE
from .models import BoardRef

PROVIDERS: dict[str, Provider] = {p.name: p for p in (GREENHOUSE,)}
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
