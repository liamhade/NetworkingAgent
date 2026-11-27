# Phase 1: measure

Date: 2026-11-27. Script: `research/job_ranking_measure/run.py` (no LLM; reads nothing back
into the database). Numbers feed [plan.md](plan.md).

## Method

- Input: the finished saved searches of the `TEST_USER` account. There is **one** (6
  companies, 9 jobs in the final results); the sample is small, so read the numbers as a
  single realistic search, not a distribution.
- Jobs found: the saved trace's `find_jobs` steps, plus a re-run of that search's saved plan
  through `find_jobs_node` with the default boards (no LLM). The saved plan had the ATS
  boards turned off, so the re-run only covers BuiltInNYC and Google.
- Text from the board API: decided per board by reading `backend/src/ats/*`,
  `usajobs/api.py`, `builtin_nyc/api.py`.
- Reads: the 30 jobs with no API text went through `read_page` with the app's 6 parallel
  workers. Times are per read; "inside the batch" counts reads finished within
  `READ_TIMEOUT_S` (8 s) of the batch start.
- Token sizes: `backend/logs/llm_usage.csv` (`rank_companies` rows).

## Jobs found before ranking

| Source | Jobs | Notes |
|---|---|---|
| BuiltInNYC (2 queries, 15 each) | 30 | the saved run kept 20 after de-duplication, the re-run 30 |
| Google `site:ashbyhq.com` | 10 | search-result links only |
| **Total in re-run** | **40** | saved run: 30 sent to `rank_companies` |

Both runs sit at or under the per-board caps, so about 30-40 jobs reach ranking, and the
plan's 40-60 estimate from the usage log is the upper end. The final result had 9 jobs.

## Full posting text from the board

| Board | Text in the search response (verified in code) |
|---|---|
| Lever, Ashby | full description, parsed only for `years_required` then dropped by `AtsJob` |
| USAJOBS | qualification summary only (not duties) |
| Greenhouse | none (`?content=true` is not used; it is ~12x larger) |
| Workable | none (list API has no description) |
| BuiltInNYC | card tagline only |
| Conservation Job Board | card fields (experience, pay), no description |
| Google results | title and snippet only, from any site |

In the re-run, 0 of 40 jobs had full text today. The 10 Ashby links came through Google, not
the Ashby API, so they have none until Phase 2 fetches them through the board API; if they
had, 10/40 = 25 % would. The other 30 (BuiltInNYC, 75 %) always need a page read.

## Page reads (30 BuiltInNYC postings, 6 parallel)

| Metric | Value |
|---|---|
| Success | 30/30 (100 %) |
| Per read p50 / p90 / max | 0.9 s / 1.2 s / 1.3 s |
| Whole batch | 5.1 s (all inside the 8 s `READ_TIMEOUT_S`) |
| Characters per read (median / min / max) | 6,823 / 2,937 / 11,287 |

The real run's two reads took 0.9 and 1.0 s (3.8k chars each), matching this.

Caveat: this was the first burst. Repeating the same 30-read burst a few minutes later got
`429 Too Many Requests` from builtinnyc.com on every page (0/30 read, each failing in 2.5 s).
So reading ~30 BuiltIn pages at once is fine once, but not repeatedly. Phase 2 should read
only the jobs that survive the filter, retry once with a delay, and fall back to the card
text (`text_source` = `none`) rather than failing.

## Ranking input today

`rank_companies` calls in the usage log (8 calls, Haiku): input 3,397 / 6,617 / 9,462 tokens
(min / p50 / max), output 788 / 1,611 / 1,771. Listings ranked in the saved search: 30.
Mean cost $0.0013 per call.

## `rank_jobs` cost estimate (Sonnet 5.5, $2/M in, $10/M out)

30 cards x 250 tokens = 7.5k, plus about 1.5k of instructions and profile = **9k input**.
Output: a score, reason, alignment note and keywords for each job kept, about 2k.

| | Tokens | Cost |
|---|---|---|
| Input | 9,000 | $0.018 |
| Output | 2,000 | $0.020 |
| **`rank_jobs`** | | **$0.038** |

Plus the slimmed `compile` call, this lands at the plan's $0.04-0.05 per search. Reads add
no LLM cost.

## Conclusion

The data does not contradict the plan's defaults, so `RANK_MAX_JOBS=30` and `MAX_JOBS=12`
stay. Searches find 30-40 jobs, so 30 is a real cap rather than a number above the supply,
and reads take about 1 s each (5 s for 30 in parallel), inside the 8 s timeout.

Limitations: one saved search for `TEST_USER`; the re-run excluded Greenhouse, Lever,
Workable and USAJOBS, so their job counts and read times are unmeasured (their pages are
plain HTTP / API reads, `read_page` has dedicated Greenhouse, Lever and Ashby readers);
source is derived from the URL host; BuiltInNYC rate-limited the second burst.
