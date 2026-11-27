# Job ranking: results

## Run 1: after phase 3 (2026-11-27)

One real search, scripted with [`research/job_ranking_e2e/run.py`](../../research/job_ranking_e2e/run.py):
the request of the `TEST_USER` account's newest saved search, run through the whole graph
(plan, find_jobs, filter, rank_jobs, find_people, compile) with real boards, models and the
LinkedIn people search. LLM usage went to a scratch CSV (the app's `llm_usage.csv` is
untouched). Nothing was saved to `database/`. Models: Haiku 5.5 for plan and compile,
Sonnet 5.5 for `rank_jobs`.

### LLM cost per step

| Step | Calls | Input tok | Output tok | Cost | Latency |
|---|---|---|---|---|---|
| plan | 1 | 4,920 | 324 | $0.0007 | 2.7 s |
| rank_jobs | 1 | 12,124 | 3,436 | $0.0586 | 25.3 s |
| compile (people notes + messages + company text, one call) | 1 | 15,056 | 9,144 | $0.0061 | 33.4 s |
| **Total** | 3 | 32,100 | 12,904 | **$0.0653** | |

There is no separate people-notes call; `compile` is the only call after `rank_jobs`.

### Wall time per node

| Node | Seconds |
|---|---|
| plan | 2.8 |
| find_jobs | 3.0 |
| filter (includes posting completion / reads) | 7.8 |
| rank_jobs | 25.3 |
| find_people | 7.5 |
| compile | 33.4 |
| **Total** | **88.0** |

### Job counts

- Found by `find_jobs`: 30
- After `filter`: 30 (0 duplicates, 0 far away, 0 too senior, 0 over the `RANK_MAX_JOBS` limit)
- Posting text (`text_source`): 20 parser, 9 api, 0 page, 1 none. So 29 of 30 read OK; 1 fell
  back to card text (the generic page reader failed: the Playwright browser is not installed
  on this machine, see Bugs).
- Ranked and returned (`MAX_JOBS`): 12

### Seniority check

- The filter's `user_years` was **None**: the saved background states dates, not "N years",
  so the code-side too-senior filter never ran (0 dropped). Seniority was left to the ranker.
- No job in the top 12 asks for more than 2 years, and none is a new-grad programme for a
  later graduation year. The 30-job pool held no clearly senior roles to test against (the
  ranker only returns the top 12, so lower-scored jobs are not visible).
- Closest cases: "Software Engineer II, Support AI" asks 2+ years and scored **66**
  (rank 6; the reason says "you have less than that"). The three "1+ year" Two Sigma / Capital
  One jobs scored 64-70, which is right for a user with about one year.
- Verdict: no violation of the "far above experience scores 40 or less" rule, but the test
  was weak because no senior postings reached the ranker. A 2+ years job at 66 is the one to
  watch. Re-test with a search whose pool includes 4-5+ year and 2027 new-grad postings.

### Top 12

| Rank | Company | Title | Score | years_required |
|---|---|---|---|---|
| 1 | Runpod | Software Engineer (Full-Stack) - Multiple Levels | 80 | - |
| 2 | Affirm | Software Engineer I, Backend (Streaming Infra) | 78 | - |
| 3 | Two Sigma | Software Engineer, Modeling Engineering | 70 | 1+ year |
| 4 | Two Sigma | Quantitative Software Engineer: Fast Engineering | 68 | 1+ year |
| 5 | Notion | Software Engineer, Web Infrastructure | 66 | - |
| 6 | Toast | Software Engineer II, Support AI | 66 | 2+ years |
| 7 | Two Sigma | Quantitative Software Engineer: Quantitative Components | 64 | 1+ year |
| 8 | Capital One | AI Engineer 3 | 64 | 1+ year |
| 9 | Multi Media, LLC | Software Engineer | 62 | - |
| 10 | Makai Labs | AI Engineer @ Makai Labs | 62 | - |
| 11 | Percepta | Applied AI Engineer @ Percepta | 60 | - |
| 12 | Sequence | AI Engineer - NYC @ Sequence | 58 | - |

### Comparison

| | Baseline | Plan target | Run 1 |
|---|---|---|---|
| LLM cost per search | $0.0063 | $0.04-0.05 | **$0.0653** |
| Rank input | 3.5-8.4k tok (Haiku) | 8-10k (Sonnet) | 12.1k in / 3.4k out (Sonnet) |
| Added read time | 0-25 s | 10-20 s | 7.8 s (filter node, includes completion) |
| Step time | 80-100 s | | 88 s total |
| compile | $0.0043, about 40 s | smaller | $0.0061, 33 s (not smaller) |

### Gate

- Cost <= $0.08: **pass** ($0.0653), but **above the plan's $0.04-0.05 target** (about 10x
  the baseline). `rank_jobs` is $0.0586 of it: 12.1k input (cards are heavier than the 250
  tokens assumed) and 3.4k output (about 290 tokens per ranked job; the estimate was 2k).
- Total time <= 2x baseline (about 200 s): **pass** (88 s, in line with the baseline).

### Bugs and gaps found

- `filter.user_years` returns None for a background that gives dates instead of "N years",
  so the code-side seniority filter is inert for this user. Not fixed here.
- The generic page reader needs a Playwright browser (`playwright install`); without it one
  posting fell back to `text_source = none`. Environment issue, not a pipeline bug.
- `compile` input/output did not shrink after the ranker took over job alignment (15k in,
  9k out); worth checking in phase 4.

## Phase 4: compile slimmed

Code, not the compile call, now builds `SearchResults`: companies, jobs (rank, score, reason,
years, alignment), URLs and the summary come from the ranker's output and the gathered data.
The compile call returns `CompileNotes`: per company a one-sentence description (only when
the BuiltInNYC listing gave none) and the people's alignment notes and connect messages.
It is sent `name`, `describe`, up to 3 job titles, `people_searched` and the current
employees found, only for companies that need a description or have people, and is skipped
when none does. Company `alignment` is now the best job's reason (code); the summary is
built in code (one line: counts, roles, top match).

Compile input on a synthetic fixture (8 companies, 16 jobs with 1,200-character
requirements, 3 companies with 3 people): 28.2k characters before, 3.5k after. The output no
longer carries job lists or job alignments, so the 9k output tokens of Run 1 should drop to
the people notes (about 200 tokens per person) plus descriptions. The `rank_jobs` output is
trimmed too: alignment only for the top `MAX_JOBS`, reasons of at most 15 words. Re-measure
with a real run.

Also in this phase: `filter.user_years` reads dated work ranges ("Nov 2025 - present") and
new-grad wording; a search that finds only BuiltInNYC company listings ends with empty results
and a summary rather than an error; the order-dependent assertion in
`test_filter_node_reads_only_the_survivors_and_records_counts` (parallel reads) is fixed.

## Run 2: final (2026-11-27)

The same script ([`research/job_ranking_e2e/run.py`](../../research/job_ranking_e2e/run.py),
unchanged: the graph's inputs and node names did not change), the `TEST_USER` account's newest
saved search, real boards and models, usage in a scratch CSV, nothing saved to `database/`.
It was run twice. The first run had no Playwright browser installed (the generic page reader
failed); the browser was then installed and the search repeated. Both are listed; "Run 2" below
is the second.

### LLM cost per step

| Step | Calls | Input tok | Output tok | Cost | Latency |
|---|---|---|---|---|---|
| plan | 1 | 4,920 | 321 | $0.0007 | 3.3 s |
| rank_jobs (Sonnet 5.5) | 1 | 7,712 | 2,120 | $0.0366 | 13.8 s |
| compile (CompileNotes: people notes + descriptions) | 1 | 5,804 | 6,364 | $0.0038 | 23.0 s |
| **Total** | 3 | 18,436 | 8,805 | **$0.0410** | |

First run: $0.0376 total (rank 6.1k in / 2.1k out, $0.0335; compile 5.4k in / 5.7k out, $0.0034).

### Wall time per node (seconds)

plan 3.5, find_jobs 9.4, filter 8.1, rank_jobs 13.9, find_people 7.6, compile 23.0.
**Total 110.1 s** (first run 112.5 s).

### Job counts

- Found: 30. After `filter`: 30 (0 duplicates, 0 far away, 0 over the limit, **0 dropped by
  the years filter**). First run: 23 found, 20 after filter (3 duplicates).
- `user_years` was still **None**: the saved background has only a bare "2025" mention and no
  dated work range or "N years", so the new derivation has nothing to read. The years filter
  therefore did not act, for this user.
- `text_source`: 3 parser, 27 none (first run: 4 parser, 16 none). Cards, not postings, were
  ranked for most jobs (see Bugs and gaps).
- Ranked and returned: 12.

### Seniority check

- Run 2: no job in the top 12 is a senior title or asks for 3+ years. Top 12: Toast Software
  Engineer II, Support AI 90; Whatnot AI Tooling Engineer 88; Affirm SWE I 78; Runpod 77;
  Percepta 76; Ramp 72; Sequence 70; Aegis AI 68; Multi Media 68; Netic 66; Navan 62; Notion 60.
  No later-year new-grad programme appeared. `years_required` was empty for all 12 (the text
  was mostly not read).
- First run: **three Mastercard "Lead" roles ranked 7, 8 and 11 with scores 78, 75 and 66**
  for a user with about one year of experience. With no posting text (`none`) and
  `user_years` None, neither the filter nor the ranker caught the title. This breaks the
  "clearly too senior scores 40 or less" expectation.
- Verdict: **not fully met.** The ranker can score a "Lead" title high when it has only card
  text.

### Comparison

| | Baseline | Plan target | Run 1 | Run 2 |
|---|---|---|---|---|
| LLM cost per search | $0.0063 | $0.04-0.05 | $0.0653 | **$0.0410** |
| rank_jobs | 3.5-8.4k in (Haiku) | 8-10k in (Sonnet) | 12.1k in / 3.4k out, $0.0586 | 7.7k in / 2.1k out, $0.0366 |
| compile | $0.0043, ~40 s | smaller | $0.0061, 33.4 s, 15.1k in / 9.1k out | $0.0038, 23.0 s, 5.8k in / 6.4k out |
| Added read time (filter node) | 0-25 s | 10-20 s | 7.8 s | 8.1 s (capped by the 8 s batch timeout) |
| Total time | 80-100 s | | 88.0 s | 110.1 s |
| Postings read | | | 29 of 30 | 3 of 30 |
| Years filter dropped | | | 0 (user_years None) | 0 (user_years None) |

### Gate

- Cost <= $0.08: **pass** ($0.0410, inside the plan's $0.04-0.05).
- Time <= ~200 s: **pass** (110 s; 10-20 s above the baseline mostly from slower find_jobs
  and compile).

### Bugs and gaps found

- **Most postings were not read.** The 8 s batch timeout (`READ_TIMEOUT_S`) with 3 reads per
  host at about 2.4 s each (BuiltInNYC was slower than in Run 1, about 1.2 s) fits roughly 9
  reads; the rest time out and fall back to card text. Raising the timeout, or the per-host
  reads, would trade time for text. Not changed here.
- The ranker gives high scores to "Lead" titles when no posting text was read (first run).
  A prompt rule (title seniority vs. the user's experience applies even without years) is the
  likely fix. Not changed here.
- `user_years` stays None for backgrounds with no dated work range or "N years".

## Run 3: after read/years fixes (2026-11-27)

The same script and account as Run 2, real boards and models, usage in a scratch CSV, nothing
saved to `database/`. Two fixes went in first:

- **Reads** (`fix(read)`): `complete_jobs` waited `READ_TIMEOUT_S` = 8 s for the whole batch
  with 3 reads per host, so about 9 BuiltInNYC reads (2.4 s each) fit. The batch now has its
  own budget, `READ_BUDGET_S` = 20 s (all reads start at once; the old 8 s stays for
  `read_pages`), with `READ_HOST_CONCURRENCY` = 5 reads per host (the shared page pool has 6
  workers, so it is not the bottleneck; BuiltIn/Workable parsers and the board APIs are plain
  `requests` calls, with no lock or Playwright involved) and one retry after
  `READ_RETRY_BACKOFF_S` = 1.5 s on HTTP 429 when the budget has room. Failures still keep the
  card text. 5 per host rather than 6+ because measure.md's 6-parallel burst was the one that
  later drew 429s; 30 reads at 5-parallel and about 2.4 s each is about 14 s.
- **Years** (`fix(background)`): "Software Engineer since November 2025" (and "since Nov
  2025") is an open-ended range counted up to today unless the words before "since" are
  student wording. `user_years` for the TEST_USER background is now **1** (was None).

### LLM cost per step

| Step | Calls | Input tok | Output tok | Cost | Latency |
|---|---|---|---|---|---|
| plan | 1 | 4,920 | 970 | $0.0010 | 6.2 s |
| rank_jobs (Sonnet 5.5) | 1 | 7,849 | 2,062 | $0.0363 | 14.5 s |
| compile | 1 | 4,841 | 5,696 | $0.0033 | 21.7 s |
| **Total** | 3 | 17,610 | 8,728 | **$0.0406** | |

### Wall time per node (seconds)

plan 6.4, find_jobs 11.6, filter 20.3, rank_jobs 14.5, find_people 17.9, compile 21.7.
**Total 140.3 s.**

### Job counts

- Found: 23. After `filter`: 20 (3 duplicates, 0 far away, 0 over the limit).
- `user_years` = 1. **Years filter dropped 0** (`too_senior` 0 before and after the read): no
  found job asked for far more than one year.
- `text_source`: **17 parser, 3 none** (Run 2: 3 parser, 27 none). Postings read: 17 of 20.
- Ranked and returned: 12. The `filter` node took 20.3 s (it ran into the 20 s budget; the
  3 unread jobs kept card text), about 12 s more than Run 2.

### Seniority check

- No "Lead" or "Senior" title in the top 12. Jobs asking for more than about 1 year: DeepIntent
  Applied AI Engineer (2+ years) rank 5, **74**; Cloudflare SWE Data Primitives (2+ years) rank
  10, 55; T-Mobile T-Ads SWE React (2+ years) rank 11, 50; Snap SWE Full Stack Level 4 (1+
  year) rank 12, 48. Two Sigma (1+ year) rank 4, 80.
- Verdict: no "Lead"/"Senior" violation, but the 2+ years DeepIntent job at 74 is the one to
  watch (a 2-year ask for a user with 1 year is a stretch, not clearly senior). The title-only
  "Lead" case of Run 2's first run was not exercised, because no such title was found.

### Comparison

| | Baseline | Plan target | Run 1 | Run 2 | Run 3 |
|---|---|---|---|---|---|
| LLM cost per search | $0.0063 | $0.04-0.05 | $0.0653 | $0.0410 | **$0.0406** |
| rank_jobs | 3.5-8.4k in (Haiku) | 8-10k in (Sonnet) | 12.1k in / 3.4k out, $0.0586 | 7.7k in / 2.1k out, $0.0366 | 7.8k in / 2.1k out, $0.0363 |
| compile | $0.0043, ~40 s | smaller | $0.0061, 33.4 s | $0.0038, 23.0 s | $0.0033, 21.7 s |
| Added read time (filter node) | 0-25 s | 10-20 s | 7.8 s | 8.1 s | 20.3 s |
| Total time | 80-100 s | | 88.0 s | 110.1 s | 140.3 s |
| Postings read | | | 29 of 30 | 3 of 30 | 17 of 20 |
| Years filter dropped | | | 0 (user_years None) | 0 (user_years None) | 0 (user_years 1) |

### Gate

- Cost <= $0.08: **pass** ($0.0406).
- Time <= ~200 s: **pass** (140 s). The added read time (20 s) is at the top of the plan's
  10-20 s range, the cost of reading nearly every posting.
- The 3 unread jobs: see "Verification: unread postings and seniority" below.

## Verification: unread postings and seniority (2026-11-27)

Two gaps left by Run 3: why 3 postings stayed unread, and whether the "much more experience
than the user has scores at most 40" rule holds on real too-senior jobs. Real boards and
models, TEST_USER, usage in scratch CSVs, nothing saved to `database/`.
`research/job_ranking_e2e/run.py` now prints, for every `text_source` "none" posting, its URL
and the read outcome from the trace; `research/job_ranking_e2e/seniority_check.py` is new.

### A. Unread postings

Four full runs back to back (one every few minutes) gave 20, 18, 17 and 17 unread postings of
23-29, against 3 of 20 in Run 3, which ran cold. Causes, by count:

| Host | Cause | Fixed? |
|---|---|---|
| www.builtinnyc.com (12-14 per run) | HTTP 429 from Cloudflare on `builtin_parser`, on the first try and on the retry (about 2.5 s per read). Cloudflare keeps the IP limited for some minutes after a burst of about 20-30 page reads: a single plain GET returned 429 right after a run and 200 about 5-8 min later. No `Retry-After`. Even 2 reads per host (seniority_check) were refused while limited. | No: external rate limit. Run 3's 17 of 20 was a cold start. Repeated runs within minutes are not representative; wait several minutes between runs. |
| www.builtinnyc.com, jobs.ashbyhq.com (Google results), 3-6 per run | "Timeout: not read within 20 s": the read pool has 6 workers, and BuiltIn reads that sleep on a 429 retry hold them, so later jobs never started. The trace said `read_page` even for BuiltIn URLs. | Trace label fixed (`fix(read)`, test added); the starvation is a symptom of the rate limit above. |
| indeed.com, ziprecruiter.com, agentic-engineering-jobs.com (Google results) | The URL is a search or listing page, not a posting: 403, 403, 404. | No: external (Google returns aggregator pages); the ranker only sees the card. |
| jobs.technyc.org (Google result) | Timeout, page read still loading at the 20 s budget. | No: slow external site. |

No parser was missing a page variant and no URL pattern was unrouted. When reads succeed, the
Ashby board pages Google returns (Ultralytics, Mercura, EverAI) come back as `page` text.
Possible follow-up, not done: a lower `READ_HOST_CONCURRENCY` or a per-host pace for
builtinnyc.com; it would trade time against 429s, and cannot be measured while the IP is
still limited.

### B. Seniority rule, live

`seniority_check.py`: TEST_USER request (`user_years` = 1), plan and `filter` as in the
pipeline for the level-appropriate jobs, plus real senior postings (Greenhouse API boards
for text, and BuiltInNYC searches for "senior software engineer", "staff engineer",
"engineering manager", whose page reads were 429-limited so those are title/level only),
mixed and ranked with `rank_jobs_node` and the real `RANK_MODEL` (Sonnet 5.5). **No prompt
change was needed.** Final run with `--score-all` (asks the ranker to return and score every
job; without it the ranker simply left every too-senior job out in two of the four runs,
which also satisfies the rule):

| Job | years_required | Score |
|---|---|---|
| Cloudflare, Customer Engineering Manager (x2) | 1+ year | 8, 6 |
| Twilio, Principal Engineer, Cloud Security | 12+ years | 4 |
| Twilio, Principal Engineer (L5) | 12+ years | 3 |
| Robinhood, Engineering Manager, AI Platform & Agentic Apps | 10+ years | 15 |
| MongoDB, Senior Software Engineer (title only, text 429) | - | 32 |
| CrowdStrike, Sr. Software Engineer - SDMF (title only) | - | 30 |
| T-Mobile, T-Ads Senior Software Engineer, Platform (title only) | - | 30 |

Across the four runs (different mixes), every Senior/Staff/Principal/Manager job scored
between 3 and 40 (Zocdoc Senior SWE was 40 in the first run) or was left out. **Pass**: all
flagged jobs scored <= 40. Level-appropriate jobs scored 42-90 (Entry level / "I" titles
72-90), so the rule does not flatten the range.

2+ years jobs (partial credit): Toast SWE II (2+ years) 60, Cloudflare SWE Data Primitives
(2+ years) 72, Clark SWE AI (2-5 years) 66, Aegis AI (2-10 years) 68. The Run 3 DeepIntent
2+ years job at 74 is in line with these; most land at 60-72, a little above the 50-65 hoped
for but consistent with the prompt's "2-5 years suits someone with 2 years". Not changed:
tightening it risks the near-level partial credit.

### Cost of the checks

A: four runs at $0.049-0.051 each, $0.20. B: four runs at $0.023-0.035 each, $0.12. Total
about $0.32.

### Commits

- `fix(read)`: timed-out reads name the waiting reader in the trace.
- `test(research)`: per-read errors in `run.py`, `seniority_check.py`.

## Verification 2: seniority with full posting text, retry fix (2026-11-27)

### Retry fix (`fix(read)`)

A 429 retry no longer sleeps inside a page-pool worker: the retry is a new pool task started
by a timer after `READ_RETRY_BACKOFF_S`. Once a host answers 429, the batch sends it no new
first reads; they fall back to the card text at once (`text_source` "none", trace
`args.outcome` "rate_limited"). Each read trace step records `args.outcome` (ok, error,
rate_limited, timeout). `READ_BUDGET_S` stays the overall deadline. Tests: host A always 429,
host B fine (all B reads complete, A falls back, no timeouts, outcomes recorded), and more
429s than workers with a long backoff (B reads finish well before the backoff ends).

### Seniority check with full text

Run after more than 10 minutes without a BuiltIn request. `seniority_check.py` now takes its
too-senior postings from Greenhouse, Lever and Ashby boards (text from their APIs, no 429)
and only tops up from BuiltInNYC when short; `--score-all --senior 10`, user_years 1.
First attempt (4 Greenhouse boards plus BuiltIn top-up) gave only 4 of 10 with text, because
the pipeline's own filter reads had already rate-limited BuiltIn; hence the change.

| Company | Title | text_source | years_required | Score |
|---|---|---|---|---|
| Cloudflare | Customer Engineering Manager | api | 1+ year | 8 |
| Cloudflare | Customer Engineering Manager | api | 1+ year | 6 |
| Twilio | Principal Engineer, Cloud Security | api | 12+ years | 4 |
| Twilio | Principal Engineer (L5) | api | 12+ years | 3 |
| Robinhood | Engineering Manager, AI Platform & Agentic Apps | api | 10+ years | 10 |
| Robinhood | Senior AI Operations Engineer, Enterprise Tech | api | 5+ years | 20 |
| Palantir | Senior Backend Software Engineer - Application Development | api | 6+ years | 22 |
| Palantir | Senior Backend Software Engineer - Application Development | api | 6+ years | 12 |
| Ramp | Senior Engineer, Backend, Vendor Management | api | - | 30 |
| Ramp | Senior Software Engineer, Product Foundations | api | - | 27 |

Level-appropriate jobs in the same run: Two Sigma Quant SWE (1+ year, parser) 86, Palantir
SWE Applied AI (entry level, parser) 90, three Google-result Ashby pages (page) 15-45.
**Pass**: 10 of 10 too-senior jobs have text (all `api`), scores 3-30 (max 30, limit 40).
Earlier run with the same code and 4 BuiltIn title-only jobs: scores 2-40, also pass. No
prompt change needed. Cost $0.030 and $0.037.

### run.py after the fix

BuiltIn was still rate limited from the checks above (the IP had no 10-minute rest), which
shows the new behaviour: 71.2 s wall, $0.0428 (plan 0.0007, rank 0.0389, compile 0.0033);
filter 6.4 s. text_source: api 7, page 1, none 20. Per host outcomes: www.builtinnyc.com
20 rate_limited (6 real 429 reads, about 1.0-1.3 s each, and 14 skipped in 0 ms); all other
hosts ok. No timeouts: before, a 429 burst held all 6 workers and non-BuiltIn reads timed
out at 20 s. The text-read gain on BuiltIn itself could not be measured while the IP was
limited.
