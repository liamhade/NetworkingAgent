# Experiment: read postings before ranking, then rescore

## What was built

An optional `rescore_jobs` node between `rank_companies` and `find_people`, **off by
default** (`RESCORE_POSTINGS=0`).

- `RESCORE_POSTINGS=N`: read the top N postings of every chosen company in full (6 at a
  time; `read_page` is plain HTTP for most boards), then one LLM call (`RESCORE_PROMPT`,
  usage purpose `rescore_jobs`) returns new job scores, `years_required` and company scores.
  Companies and their jobs are re-sorted before the people search, so people are searched
  at the companies that still rank highest.
- `RESCORE_POSTING_MAX_CHARS` (default 2500): characters of each posting sent. The excerpt
  keeps the opening and jumps to the "Requirements / Qualifications / What you'll need"
  section when there is one (`steps.posting_excerpt`).
- `read_postings` reuses postings that `rescore_jobs` already read, and still passes only
  its `READ_POSTINGS` postings to compile, so the compile step costs the same as before.

## How it was measured

`research/rescore_experiment/run.py` rebuilds the ranked companies of each saved search
(the 2 searches in `database/`, both "Software engineering roles · New York, NY", 6
companies each) and runs the node with the real model (`claude-haiku-5-5`) and `read_page`.
Usage was logged to a scratch CSV, not the app's log.

## Results (2026-11-27)

| | Search A | Search B |
|---|---|---|
| Postings read (top 2 per company) | 8 of 9 | 8 of 8 |
| Read time (parallel, slowest page) | 16.2 s* | 2.3 s |
| LLM call | 9.3 s, 9,010 in / 1,317 out tokens | 6.7 s, 8,922 in / 1,304 out |
| LLM cost | $0.00156 | $0.00154 |
| Total added time | 25.5 s* | 9.7 s |

\* One Ashby page fell back to headless Chromium, which isn't installed on this machine, so
the read failed after 16 s. Where the browser is installed, that read succeeds but is still
the slowest.

With top 4 per company, the saved searches had only 9-10 postings (most companies listed
1-2 jobs), so the numbers barely moved: ≈9,900 in / 1,450 out tokens, $0.0017, 9-11 s.
In a live search a company can have up to 4 jobs. 6 × 4 = 24 postings is about 16k input
tokens, so about **$0.003** and around 10-12 s.

### What it changed

- Search A was ranked before the seniority fix. Rescoring pushed "Senior Software Engineer"
  jobs at Ro down from 50 and 45 to 30 and 25, and a "Mid-Level" AI role down to 70. A
  Palantir new-grad job was marked "0 years (new grad)".
- Search B: Clark's "Software Engineer, AI" dropped from 78 to 35 once the posting showed
  "2-5 years". Its company score dropped from 78 to 35 (it fell from 3rd to last), so it would
  no longer get an automatic people search.
- Most other scores moved by 0 to 12 points.

## Cost in context

Baseline LLM cost per search, from `backend/logs/llm_usage.csv` (8 searches): plan $0.0007
+ rank $0.0013 + compile $0.0043 ≈ **$0.0063**. Baseline time: about 80-100 s of step
time (compile alone is about 40 s).

| Setting | Added LLM cost | Added time | Cost per search |
|---|---|---|---|
| Off (default) | 0 | 0 | ≈$0.0063 |
| `RESCORE_POSTINGS=2` | ≈$0.0015 (+25%) | ≈10 s (+10%); up to ≈25 s with a slow page | ≈$0.0078 |
| `RESCORE_POSTINGS=4` | ≈$0.003 (+50%, estimate) | ≈10-12 s | ≈$0.009 |

That is under a cent per search, or about $1.50 per 1,000 searches at 2 per company. Time is
the bigger cost: one slow page (JS-only boards that need the browser) holds up the whole
step, because every read must finish before the LLM call.

## Possible next steps

- Turn it on with `RESCORE_POSTINGS=2`. The time cost is small next to compile's 40 s.
- Cap each read at a few seconds, or skip boards known to need the browser, so one slow
  page can't add 15 s or more.
- Running the people search for the first companies while rescoring finishes would hide
  the added time, but the people search should follow the new order.
