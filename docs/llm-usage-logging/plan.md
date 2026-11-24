# LLM token usage + cost logging

TODO item: "(Log token usage for each LLM) Logs LLM token usage + cost to `logs` in a csv
format so that I can easily calculate token usage per person, per timeframe, or just overall."

## Current state
- All LLM calls go through LangChain: `llm.get_llm()` → `init_chat_model("anthropic:claude-haiku-5-5")`.
- Call sites: `agent.run_search` (a `create_agent` tool-calling loop, one model request per
  turn, streamed with `stream_mode="updates"`), `agent.compile_results` and
  `resume.parse_resume` (both `with_structured_output(method="json_schema")`).
- Who's calling comes from `accounts.get_current_user()` (always TEST_USER) via the
  `CurrentUser` dependency. Search ids were only created at save time.

## Design
### Capture: a LangChain callback
`llm_usage.callback.UsageCallbackHandler` gets `on_chat_model_start` / `on_llm_start` (start
time, context snapshot, purpose, `ls_provider` / `ls_model_name` from run metadata),
`on_llm_end` (reads `AIMessage.usage_metadata` and `response_metadata.model_name`), and
`on_llm_error` (writes a `status=error` row). It fires once per model request, so every
tool-loop turn and every structured-output call gets its own row.

One shared handler is attached in two places so no call is missed:
1. on the model itself in `get_llm()` (`callbacks=[usage_handler]`), which covers any
   future call site;
2. in each call site's `config` via `run_config(purpose)`, which also labels the call
   (`metadata.llm_purpose`) and covers models injected for tests.

LangChain de-duplicates the same handler instance, so a call is never logged twice.

### Context: contextvars, not function arguments
`llm_usage.context` keeps a `UsageContext(user_id, request_id, search_id, purpose)` in a
ContextVar.
- `usage_context(...)` sets it for a `with` block (used by `/api/resume`).
- `bind_context(iterator, ...)` is for streaming generators. Starlette advances a sync
  `StreamingResponse` generator in worker threads, and each step gets a copied context, so
  values set inside the generator would be lost. `bind_context` runs every step inside one
  dedicated `contextvars.Context`. LangGraph copies the current context into its worker
  threads, and the handler takes its snapshot at call start.
- `/api/search` now creates the search id up front (`history.new_search_id()`), tags rows
  with it, and saves the search under the same id
  (`history.save_search(..., search_id=...)`), so usage rows join directly to saved searches.

### Token split and cost
LangChain's `input_tokens` includes cache tokens. `split_usage()` reports billed categories:
uncached input, cache read, cache write 5m, cache write 1h (a write with no TTL breakdown
counts as 5m), output, and total. `llm_usage/pricing.py` is the single pricing table (USD per
1M tokens; base input, 5m write, 1h write, cache read, output) taken from
https://platform.claude.com/docs/en/about-claude/pricing (checked 2026-11-12), including
Claude Haiku 5.5's higher prices for prompts over 100K tokens (cache tokens included in the
count). Dated snapshot ids match the base model. An unknown model is logged with a blank
`cost_usd` and one warning per model.

### Storage
`config.LLM_USAGE_LOG` (env `LLM_USAGE_LOG`, default `backend/logs/llm_usage.csv`). The header
is written when the file is new or empty; each row is one `write()` under a thread lock
(append mode). Any failure is caught and logged as a warning: usage logging never breaks a
search. `backend/logs/` is gitignored.

Columns:
`timestamp` (ISO UTC), `user_id`, `request_id`, `search_id`, `purpose` (`research` /
`compile_results` / `parse_resume`), `provider`, `model`, `status` (`ok`/`error`),
`input_tokens` (uncached), `cache_read_tokens`, `cache_write_5m_tokens`,
`cache_write_1h_tokens`, `output_tokens`, `total_tokens` (all input + output), `cost_usd`,
`latency_ms`, `error`.

### Summaries
From `backend/src`:

    ..\.venv\Scripts\python.exe -m llm_usage                      # overall
    ..\.venv\Scripts\python.exe -m llm_usage --by user            # per person
    ..\.venv\Scripts\python.exe -m llm_usage --by user day        # per person per day
    ..\.venv\Scripts\python.exe -m llm_usage --by month model --since 2026-11-01 --user TEST_USER

Groups: user, day, month, model, purpose, search, request. Blank costs count as 0 and show
up in `unpriced_calls`. pandas equivalent:

    df = pd.read_csv("logs/llm_usage.csv", parse_dates=["timestamp"])
    df.groupby(["user_id", df.timestamp.dt.date])[["total_tokens", "cost_usd"]].sum()

## Tests (`tests/test_llm_usage.py`, mocked models, tmp log path)
Row per call through the real `create_agent` tool loop and the structured compile call;
header once and whole rows under concurrent writes; cost math (Opus 5.5, dated ids, Haiku 5.5
over 100K); generic cache-creation split; unknown model (blank cost, one warning); error rows;
context carried through fresh per-step contexts/threads and end to end through
`/api/search` (row `search_id` == saved search id); pricing/writer failures don't break a
search; `get_llm` attaches the handler; summary grouping and CLI.

## Limitations / follow-ups
- No cross-process file lock (fine for the single-process POC). Move to a Supabase table
  together with the database migration.
- US-only `inference_geo` (1.1x), Bedrock/Vertex pricing and server-tool fees aren't
  modelled.
- Changing the columns needs a new file (the header is only written once).
- Not yet validated against a real Anthropic API call (mocked models only).
- Once real auth exists, `get_current_user()` provides the real `user_id` with no further
  changes.
