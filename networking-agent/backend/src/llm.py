"""Where the LLM object used by the search pipeline (`pipeline/`) and the resume parser lives.

The model is chosen by the `LLM_MODEL` setting (`<provider>:<model>`, default
`anthropic:claude-haiku-5-5`), so switching providers is a config change. Code that
needs JSON uses `with_structured_output(..., method="json_schema")`, which works on
providers with native structured outputs and does not rely on forced tool calls.
"""

from functools import lru_cache

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

import config
from llm_usage import usage_handler


def _split(model: str) -> tuple[str, str]:
    provider, sep, name = model.partition(":")
    if not sep:
        raise ValueError(f"LLM_MODEL must look like '<provider>:<model>', got {model!r}")
    return provider, name


@lru_cache(maxsize=4)
def get_llm(model: str | None = None, max_tokens: int = 16_000) -> BaseChatModel:
    """Return a chat model for `model` (defaults to `config.LLM_MODEL`)."""
    provider, name = _split(model or config.LLM_MODEL)
    # The usage handler logs tokens and cost of every call made with this model.
    kwargs: dict = {"max_tokens": max_tokens, "callbacks": [usage_handler]}
    api_key = config.provider_api_key(provider)
    if api_key:
        kwargs["api_key"] = api_key
    return init_chat_model(name, model_provider=provider, **kwargs)
