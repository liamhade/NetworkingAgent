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
- The 3 unread jobs were not traced to a cause (budget, 429 or other); the script prints no per-read errors.
