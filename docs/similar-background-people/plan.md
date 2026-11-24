# People with a similar background

TODO: search for people who share the user's background (education for now) in addition to the
current-company search, and relax the criteria when too few turn up.

## Decisions

- **Where education comes from.** The profile was only free text (`SearchRequest.background`).
  Added `SearchRequest.education: list[str]` (default `[]`, so saved searches still load),
  mirrored on `SearchParams` (drafts, saved configs), and `ResumeProfile.education`, which the
  resume LLM fills (full school names, most recent or highest degree first; required in the LLM
  schema, defaulted on load so old saved resumes still validate). The hero form gets an optional
  "School(s)" box (names separated by `;`), pre-filled from the resume. No education: the
  similar-background search is skipped, nothing else changes.
- **One shared code path.** `steps.search_people()` (used by the `find_people` node and by the
  on-demand "Find People To Connect With") gains `education=` and, after the normal ladder, runs
  `search_similar_people()`. Both callers pass `request.education`.
- **Query.** `site:linkedin.com/in "Company" "School" <keywords> <location>`
  (`linkedin.build_query(..., school=)`, `tools.linkedin_people(..., school=)`; the retry query
  with the operator at the end carries the school too). Only the user's first school is searched.

## Relaxation ladder (`steps.similar_ladder`)

1. school + company + first planned role keywords + location
2. school + company + location (drop role keywords)
3. school + company (drop location)

Duplicate rungs collapse (no keywords, no location). Stops as soon as
`PEOPLE_SIMILAR_PER_COMPANY` people with a shared school were found.

## Caps (config.py)

- `PEOPLE_SIMILAR_MAX_QUERIES` (default 2, 0 turns the feature off): hard cap on extra Google
  searches per company. Default worst case is +2 per company (+6 for the 3 auto companies).
- `PEOPLE_SIMILAR_PER_COMPANY` (default 2): target number of shared-school people.

## Merge, dedupe, marking

- People are deduped by profile URL against the normal results and `known_urls` (already saved
  people on the on-demand path); a person found both ways appears once.
- `Person.shared_background` / `PersonResult.shared_background` = `"Same school: <School>"`,
  set by code only when the result is a current employee **and** the school name appears in the
  result's headline or snippet (`linkedin.mentions_school`); never by the LLM (hidden from its
  schema, copied across in `match_people`). A person the school query returned without the
  school visible is kept but unmarked.
- The compile and on-demand people prompts keep marked people first and use the shared school as
  the "why connect" / connection-note overlap. `<education>` is added to the profile text given
  to the LLM steps.

## Trace

Each extra search is a trace step in the same `step` as the people search (`find_people` /
`find_people_on_demand`), source `linkedin_people`, `args` with `school`, and a note
"similar background: N people with a shared school so far". Errors are recorded and the next
rung runs.

## UI

A small `pill per tight` with the shared-background text on the person row in the results page
and the People entities page; the hero gets the "School(s)" field.

## Tests

`backend/tests/test_similar_people.py` (query/ladder, relaxation, cap, dedupe/merge, marking,
skip without education, knob 0, node wiring), additions to `test_linkedin.py`,
`test_find_people.py` (on-demand), `test_resume.py`; frontend `hero.test.tsx`,
`results.test.tsx`. Fakes only, no live Google or LLM.
