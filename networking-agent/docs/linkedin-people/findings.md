# LinkedIn people search — findings

Question: people searches returned job boards instead of LinkedIn profiles. Is the fix to put
`site:linkedin.com/in` in front of the query?

**Answer: no — that prefix was already there and works.** The bad results had two causes:

1. **Google sometimes ignores the `site:` operator.** It then serves a generic job-board page
   ("About 60 results": Glassdoor, ZipRecruiter, LinkedIn job listings). Two different queries
   got identical pages, and one of them, re-run a few minutes later, returned 9 profiles.
2. **Our filter let non-profiles through.** `find_people`'s `_looks_like_linkedin` accepted any
   result with "LinkedIn" in its site label, title or breadcrumb. On the ignored-operator page,
   the one result it accepted was the LinkedIn jobs list "Ramp Jobs in New York (7000+ Open
   Roles)". That is the "1 LinkedIn hit" seen in `docs/google-serp-speed/findings.md`.

## Live test (Nov 2026)

One Chrome session (warm profile), 11 results pages, at least 13 s apart, no `/goto` links
resolved (results were classified from the site label, breadcrumb and title). No CAPTCHA or
`/sorry/`.

| # | Query | Results | Profiles | Other LinkedIn (posts/jobs) | Job boards / other |
|---|---|---|---|---|---|
| 1 | `"Ramp" data analyst linkedin` (no operator) | 9 | **0** | 6 (2 posts, 1 article, 3 job pages) | 3 |
| 2 | `site:linkedin.com/in "Ramp" data analyst New York` (current form) | 10 | **10** | 0 | 0 |
| 3 | `site:linkedin.com/in "Ramp" data analyst` (current, no location) | 10 | **10**¹ | 0 | 0 |
| 4 | `"Ramp" data analyst site:linkedin.com/in` (operator at end) | 10 | **10**¹ | 0 | 0 |
| 5 | `site:linkedin.com/in Ramp data analyst` (unquoted) | 10 | **0** — operator ignored² | 1 (jobs list) | 9 |
| 6 | `site:linkedin.com/in/ "Ramp" data analyst` (trailing slash) | 10 | **0** — operator ignored² | 1 (jobs list) | 9 |
| 6b | same as 6, re-run ~4 min later | 10 | **10**¹ | 0 | 0 |
| 7 | `inurl:linkedin.com/in "Ramp" data analyst` | 9 | 8 (mostly not at Ramp) | 0 | 1 (ramp.com blog) |
| 8 | `site:linkedin.com/in "Datadog" recruiter New York` | 10 | **10** (all Datadog recruiters) | 0 | 0 |
| 9 | `site:linkedin.com/in "Notion" data analyst hiring` (job word) | 10 | **10** | 0 | 0 |
| 10 | `"Datadog" recruiter linkedin` (no operator) | 9 | **9** | 0 | 0 |

¹ Includes one `br.linkedin.com` profile.
² Rows 5 and 6 returned byte-identical pages ("About 60 results") even though the queries differ
(unquoted vs quoted, with vs without trailing slash). Re-running row 6 gave profiles (row 6b). So
this is Google intermittently dropping the operator, not a problem with those query forms.

Takeaways:

- With the operator honoured, operator at the start = operator at the end (same results). Keep
  the current form.
- A quoted company name is what keeps results relevant. `inurl:` honours LinkedIn but its
  results are less on-company (Ramp Network, Ramp Technology Group, unrelated analysts).
- Without the operator, results depend on the query. A strong recruiter signal still gets
  profiles (row 10); "data analyst" gets posts, LinkedIn job pages and job boards (row 1).
- Job words ("hiring") didn't hurt when the operator was honoured. They match people whose
  headlines say "We're hiring!".
- A location narrows results without hurting them.

## How Google shows a profile result (Nov 2026)

- Site label `LinkedIn · <Name>`; title `<Name> - <Headline>` with no `| LinkedIn` suffix. Some
  titles use an en dash (`Beata Sterner – …`).
- No breadcrumb: the `<cite>` holds "1.2K+ followers". Country subdomains show
  `https://in.linkedin.com › ...`.
- Snippet: `<Location> · <Current title> · <Company><about text…>`, or
  `… · Experience: <Company> · Education: …`.
- Posts: label `LinkedIn · <Name>`, title "…'s Post" or "<article title> | <Name>". Jobs:
  label `LinkedIn`, breadcrumb `linkedin.com › jobs › …`.

## Pipeline checks

- **URL encoding:** OK. `urlencode` sends `q=site%3Alinkedin.com%2Fin+%22Ramp%22+…`, which
  Google decodes correctly (rows 2–4).
- **Parser:** OK. It only reads organic `#rso` results (`<a><h3>`). No "People also ask", ads or
  job widgets showed up.
- **Agent:** there were no saved searches or logs to inspect. In the end-to-end run below, every
  people lookup went through the people tool; `google_search` was never used for people.

## Changes

- `backend/src/linkedin.py` (new, pure functions):
  - `build_query` and `retry_query`
  - `is_profile_url`: strict, `linkedin.com/in/…` on any subdomain
  - `looks_like_profile`: strict URL check once resolved; label, breadcrumb and title before
  - `operator_ignored`: fewer than half the results are on LinkedIn
  - `parse_profile`: name, headline, title, company, `at_company`, location
  - `parse_linkedin_title`
- `backend/src/tools.py`:
  - **`linkedin_people` replaces `find_people`**; no alias, so the model doesn't have to choose
    between two near-identical tools.
  - It returns only profiles, current employees first, and only those links are resolved.
  - If Google ignored the operator, it waits 6 s and retries once with the operator at the end.
    If that also fails, it returns an explicit error instead of job boards.
  - Pages where the operator was ignored are not cached (new optional `cacheable` check on
    `_GoogleWorker.search` and `run_google_search`).
- `backend/src/agent.py`:
  - The research prompt makes `linkedin_people` the only way to find people and asks for
    keywords that describe the person, not job-posting words.
  - The compile prompt skips `at_company: false` and "Ex-<company>" people.
- `backend/src/read_page/core.py`: the LinkedIn-blocked message points to `linkedin_people`.

## End-to-end run (one real LLM run)

Profile: data analyst at a bank (SQL, Python, Tableau, dbt basics, A/B testing, NYU Economics),
New York, looking for data analyst or analytics engineer roles at NYC fintech startups.

- **Tool calls:** 3 BuiltIn calls and 5 `linkedin_people` calls.
- **Google:** the operator was honoured on all 5 (6–10 profiles per page); no retries needed.
- **Tool output:** 18 people, all real `linkedin.com/in/` URLs after resolving (0 job boards or
  posts).
- **Final results:** 7 people at 3 companies, all real profiles at the target company in
  relevant roles:
  - Current: Sean Prentis (Manager, Data Analytics).
  - Till Financial: Cole Burton (Data Analytics Lead), Antall Fernandes (Head of Engineering),
    Kyle Redding (Director of Engineering).
  - Hometap: Jen Houtti (Manager of Analytics Engineering), Sean Moran (Data Engineering
    Manager), Bobby Kelsey (Senior Manager, Data & Analytics).
- **Weak spot:** for generic company names ("Current") and small companies (no recruiters at
  "Till Financial"), most results work elsewhere. Ranking by `at_company` and the compile step
  drop them, but those calls give few contacts.
- **Fixed during the run:** en-dash titles (3 of 9 profiles in one query had been missed).

There were no earlier saved searches to compare with.

## Verification

- pytest 221 passed. ruff check and ruff format --check are clean.
- New tests (`tests/test_linkedin.py`) are built from real result shapes and use no network.

## Caveats

- I don't know what makes Google ignore the operator. One retry plus not caching that page
  covers what I saw; if Google keeps ignoring it, the tool returns an error.
- The snippet runs the company name into the about text, so only the target company can be read
  from that field ("Ramp Network" counts as Ramp).
- `at_company` is a heuristic and only sorts results; the tool never drops people because of
  it. Some profiles have no title or location.
- If links aren't resolved (`GOOGLE_RESOLVE_URLS=false`, or resolving fails), the profile check
  falls back to the label and title heuristic, and the URL stays a Google `/goto` link.
