"""Token usage and cost logging for every LLM call (one CSV row per call).

- `usage_handler`: LangChain callback attached to every model from `llm.get_llm()` and to
  each call site's `config`, so nothing is missed (LangChain de-duplicates it).
- `run_config(purpose)`: the `config=` to pass to `invoke`/`stream` at a call site.
- `usage_context(...)` / `bind_context(iterator, ...)`: who the calls are for.
- `pricing.PRICING`: USD per 1M tokens, per model.
- `python -m llm_usage --by user day`: totals from the CSV.
"""

from llm_usage.callback import UsageCallbackHandler, run_config, usage_handler
from llm_usage.context import UsageContext, bind_context, current, usage_context

__all__ = [
    "UsageCallbackHandler",
    "UsageContext",
    "bind_context",
    "current",
    "run_config",
    "usage_context",
    "usage_handler",
]
