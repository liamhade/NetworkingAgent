# Find people by typed criteria

## Goal

The people pane's footer gets a text box next to **Find more people**. The user types what
they want ("people who went to my school", "data engineers", "recruiters in Boston") and the
on-demand people search looks for exactly that at the company. An empty box keeps today's
behaviour.

## Design

**API.** `POST /api/searches/{id}/people` takes an optional `query` (≤ 300 chars) next to
`company_key` / `job_key`. Without it nothing changes.

**Interpreting the query.** One small structured LLM call (`PEOPLE_QUERY_PROMPT` in
`prompts.py`, schema `pipeline.state.PeopleQuery`) turns the text plus the user's profile into:

- `keywords`: up to 3 short LinkedIn search phrases (roles, teams, skills); may be empty;
- `school`: a school name when the query asks for one; "my school" resolves to the user's
  first school from their profile;
- `location`: a city when the query names one, else the search's city, or "" for "anywhere".

If the call fails, the raw text is used as the only keyword phrase with the search's city.

**Searching.** `steps.search_people_by_query` runs `tools.linkedin_people` with those
values: one rung per keyword phrase (or one company-only rung), then, if fewer than
`PEOPLE_PER_COMPANY` current employees turned up and a location was used, the same first
rung without the location. At most `QUERY_MAX_SEARCHES` (3) Google searches. People with a
requested school who visibly mention it get `shared_background: "Same school: …"`, as in
the similar-background search. Known profiles are skipped.

The found people then go through the existing notes call and merge (`on_demand._notes`,
`_merge`), so they look like any other person in the pane.

**Frontend.** `findPeople()` takes an optional `query`. The footer's
`FindPeopleButton` becomes `FindPeopleSearch`: a labelled input plus the button in a form
(Enter submits). The loading/error/retry state moves into a `useFindPeople` hook shared by
both, so the per-job "Find people for this role" links are unchanged.

## Tests

- Backend: request validation; query interpretation is used (keywords, school, location);
  LLM failure falls back to the raw text; the location relaxation rung; the search cap.
- Frontend: typing a query sends it; an empty box sends none.
