"""USD prices per 1M tokens, and the cost of one call.

Source: https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-11-12),
Claude API first-party rates, global routing (US-only `inference_geo` is 1.1x; Bedrock and
Vertex AI have their own prices). Add a row here when a new model is used; a model missing
from the table is logged with a blank cost and a one-time warning.
"""

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_write_5m: float
    cache_write_1h: float
    cache_read: float


@dataclass(frozen=True)
class ModelPricing:
    standard: Price
    long_context: Price | None = None
    """Prices for prompts over `long_context_threshold` tokens (Claude Haiku 5.5 only)."""
    long_context_threshold: int = 0


def _p(inp: float, w5: float, w1h: float, read: float, out: float) -> Price:
    return Price(input=inp, output=out, cache_write_5m=w5, cache_write_1h=w1h, cache_read=read)


# Columns: base input, 5m cache write, 1h cache write, cache read, output.
PRICING: dict[str, ModelPricing] = {
    "anthropic:claude-fable-5-2": ModelPricing(_p(8, 10, 16, 0.20, 40)),
    "anthropic:claude-fable-5-1": ModelPricing(_p(10, 12.50, 20, 0.25, 50)),
    "anthropic:claude-fable-5": ModelPricing(_p(10, 12.50, 20, 1, 50)),
    "anthropic:claude-opus-5-5": ModelPricing(_p(4, 5, 8, 0.20, 20)),
    "anthropic:claude-opus-5": ModelPricing(_p(5, 6.25, 10, 0.50, 25)),
    "anthropic:claude-opus-4-8": ModelPricing(_p(5, 6.25, 10, 0.50, 25)),
    "anthropic:claude-opus-4-7": ModelPricing(_p(5, 6.25, 10, 0.50, 25)),
    "anthropic:claude-opus-4-6": ModelPricing(_p(5, 6.25, 10, 0.50, 25)),
    "anthropic:claude-sonnet-5-5": ModelPricing(_p(2, 2.50, 4, 0.10, 10)),
    "anthropic:claude-sonnet-5": ModelPricing(_p(2, 2.50, 4, 0.20, 10)),
    "anthropic:claude-sonnet-4-6": ModelPricing(_p(3, 3.75, 6, 0.30, 15)),
    "anthropic:claude-haiku-5-5": ModelPricing(
        standard=_p(0.10, 0.125, 0.20, 0.01, 0.50),
        long_context=_p(0.50, 0.625, 1, 0.05, 2.50),
        long_context_threshold=100_000,
    ),
    "anthropic:claude-haiku-4-5": ModelPricing(_p(1, 1.25, 2, 0.10, 5)),
}

_warned: set[str] = set()


def lookup(provider: str, model: str) -> ModelPricing | None:
    """Pricing for `provider:model`, also matching dated ids like `claude-x-20250101`."""
    key = f"{provider}:{model}"
    if key in PRICING:
        return PRICING[key]
    for known, pricing in PRICING.items():
        if key.startswith(known + "-") and key[len(known) + 1 :].isdigit():
            return pricing
    return None


def cost_usd(
    provider: str,
    model: str,
    *,
    uncached_input: int,
    output: int,
    cache_read: int = 0,
    cache_write_5m: int = 0,
    cache_write_1h: int = 0,
) -> float | None:
    """Dollar cost of one call, or None (with a one-time warning) for an unknown model."""
    pricing = lookup(provider, model)
    if pricing is None:
        key = f"{provider}:{model}"
        if key not in _warned:
            _warned.add(key)
            log.warning("No pricing for LLM model %r; its cost is logged blank", key)
        return None
    prompt = uncached_input + cache_read + cache_write_5m + cache_write_1h
    price = pricing.standard
    if pricing.long_context and prompt > pricing.long_context_threshold:
        price = pricing.long_context
    total = (
        uncached_input * price.input
        + output * price.output
        + cache_read * price.cache_read
        + cache_write_5m * price.cache_write_5m
        + cache_write_1h * price.cache_write_1h
    )
    return total / 1_000_000
