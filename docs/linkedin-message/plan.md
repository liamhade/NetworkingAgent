# Plan: example LinkedIn connection message per person

TODO item: *"(example message to send over linkedin) For people, add an extra bubble below the
Why Connect bubble that is an example linkedin message. It should be an under 300
(configurable value) character message that I can send to that person to connect with them.
Expose the prompt for creating this message in the `prompts.py` file."*

## Generation: one more field in the existing compile call

The compile step (`agent.compile_results`) already makes one structured-output call that
writes every person's `alignment` ("Why connect") from the full research transcript and the
user's profile. The connection note needs exactly the same context, so `PersonResult` gets a
new `connect_message` field that the same call fills in.

Alternatives considered:

- **One LLM call per person** after compiling: up to ~20 extra calls per search, more latency
  and cost, and each call would need the profile + person context re-sent. Rejected.
- **One extra batched call** for all people: still an extra round trip and a second schema;
  no quality benefit over writing the note right next to the alignment it is based on.

Cost: roughly 60-80 output tokens per person, no extra calls. Usage is still logged because
the call goes through the same `get_llm()` model and `run_config("compile_results")`.

## Prompt (`backend/src/prompts.py`)

New top-level module holding the agent prompts:

- `RESEARCH_PROMPT`, `COMPILE_PROMPT` (moved verbatim from `agent.py`, re-exported there).
- `LINKEDIN_MESSAGE_PROMPT`: template with `{max_chars}`; `linkedin_message_prompt()` fills it
  from config. `compile_prompt()` = `COMPILE_PROMPT` + the LinkedIn message rules, and is what
  `compile_results` sends.

Message rules: first person, addressed by first name, mention one concrete overlap, a light
ask (connect / quick chat), no placeholders, no emojis or hashtags, no invented facts, under
the limit.

## Length limit

- `config.LINKEDIN_MESSAGE_MAX_CHARS` (env `LINKEDIN_MESSAGE_MAX_CHARS`, default 300; LinkedIn's
  connection-note limit).
- Enforced in the backend by a `PersonResult` field validator (`schemas.clamp_message`): the
  model is told the limit, but if it overshoots, the text is cut at the last sentence end
  that fits, otherwise at the last word boundary with "…" — never above the limit.
  The validator runs on LLM output and on loading saved searches, so a lowered limit also
  applies to old data.
- No `maxLength` in the JSON schema (structured-output providers don't all support it).

## Persistence and old data

- `connect_message: str = ""` on `PersonResult` (saved with the search) and `PersonEntity`
  (People page, merged by `entities.catalog` with the usual "newest non-blank wins" rule).
- The default keeps old saved searches loadable; the field is forced into the LLM schema's
  `required` list (via `json_schema_extra`) so the model always writes it.
- Frontend: `connect_message?: string`; the bubble renders nothing when it is empty/missing.

## Frontend

`ConnectMessageBox` (`components/connect-message-box.tsx`) below "Why connect" on both the
results page and the People page: same expandable bubble shape as `AlignmentBox`, information
(blue) notification tokens to tell it apart, the message text, a character count, and a
copy-to-clipboard ghost button (shows "Copied" briefly).

## Tests

- `clamp_message`: short text unchanged, sentence cut, word cut with ellipsis, never over
  limit, tiny limits.
- `PersonResult` validation truncates over-long messages; old data without the field loads.
- LLM JSON schema lists `connect_message` as required and still hides `key`.
- Compile prompt sent to the (scripted) model includes the LinkedIn message rules and limit.
- Catalog carries `connect_message` to `PersonEntity` and fills blanks from older sightings.
