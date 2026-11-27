# Rank jobs, not companies

## Why

Fit scores come from short listings: a title, a 160-character summary and a regex guess at
experience. The ranker scores **companies**, and jobs only inside them. Users apply to jobs,
and the bad fits came from missing information (a "2-5 years" job at 78, a 2027 new-grad
programme offered to a 2025 graduate), not from a weak model. See
[experience-fit/experiment.md](../experience-fit/experiment.md): Sonnet on full postings
fixed both.

## New pipeline

```
plan → find_jobs (fetch + parse) → filter → rank_jobs → find_people → compile
```

1. **plan** (unchanged, `LLM_MODEL`): profile → role titles and board queries. It decides
   recall: a job that isn't found can't be ranked.
2. **find_jobs**: board searches as today, then each job is completed into a `JobPosting`
   (below). Boards whose API returns the description use it; the rest get their posting
   page read with `read_pages` (parallel, `READ_TIMEOUT_S`). A board parser fills the fields
   when the site is known; other pages fall back to the generic `read_page` text plus
   `experience.years_required` and `posting_excerpt`.
3. **filter** (code, no LLM): drop duplicates (same URL, or same company + title), jobs far
   outside the user's location, and jobs whose `years_required` is far above the user's
   experience. Keep at most `RANK_MAX_JOBS` (default 30), the most recent / best matched
   first.
4. **rank_jobs** (`RANK_MODEL`, default Sonnet 5.5): one call over compact job cards
   (about 250 tokens each: title, company, location, pay, `years_required`, `level`,
   requirements excerpt). It returns, per job: score 0-100, a one-sentence reason, an
   alignment note, and people-search keywords for its company. Seniority stays a hard
   limit, as in today's `RANK_PROMPT`. Output: the top `MAX_JOBS` jobs (default 12).
5. **find_people**: people at the companies of the top jobs, in job order, for the first
   `PEOPLE_AUTO_COMPANIES` distinct companies (as today). Keywords come from the ranker.
6. **compile** (`LLM_MODEL`): people alignment notes, LinkedIn connection messages and the
   one-sentence company descriptions. Job alignment already comes from the ranker, so this
   call gets smaller.

Removed: `rank_companies`, `rescore_jobs` (and `RESCORE_*`, `RESCORE_PROMPT`), and the
separate `read_postings` step, since postings are read in step 2.

## `JobPosting`

| Field | Source |
|---|---|
| `id`, `source`, `url` | board search |
| `company`, `title`, `location`, `salary` | board API or parser |
| `description` | full text, kept for the record, never sent to the LLM whole |
| `requirements` | `posting_excerpt(description)` (the requirements section, about 1,200 chars) |
| `years_required`, `level` | parser field, else `experience.years_required` |
| `posted_at` | when the board gives it |
| `text_source` | `api`, `parser`, `page` or `none`, so missing text is visible in the trace |

No LLM-written "one-line summary": `requirements` plus the title carries the same signal
at no cost. If the cards turn out too thin, a batched Haiku summary pass is the fallback.

Where the full text comes from:

| Board | Full text |
|---|---|
| Lever, Ashby, USAJOBS | in the API response (already parsed) |
| Greenhouse | `?content=true` (about 12× larger response; fetch per job instead of per board) |
| Workable | not in the list API: read the posting page |
| BuiltInNYC | card text only: read the job page (parser for its job page) |
| Conservation Job Board | experience field in the listing; read the page for the rest |
| Google results | arbitrary sites: generic `read_page` |

## Results data

Keep `SearchResults.companies[]` with `jobs[]` and `people[]` inside. People, pins, applied /
connected marks, entity keys and the entity pages all hang off this shape. Changes:

- `JobResult` gains `rank` (the ranker's order), `years_required` and `reason`.
- `CompanyResult.score` becomes the best job score at that company (kept for old code
  paths and the entity pages).
- Old saved searches have no `rank`: the UI orders their jobs by `score`, then by company
  order, so they still open.

## UI: a ranked list of jobs

The results page shows **one job per card, in rank order**, not company panels.

- **Job card**: rank, title (links to the posting), company, location, pay,
  `years_required`, fit meter (job score), the ranker's reason, and an expandable
  alignment note. Actions: Applied, Pin, open posting.
- **Contacts on the card**: "3 contacts at Ro" expands the company's people (name, title,
  Connect / message drawer, Connected). If people weren't searched for that company, the
  card shows the existing "Find people" button. When a company has several jobs, its
  people are the same on each card; the count line says so, and they are fetched once.
- **Company** is a tag on the card. Clicking it filters the list to that company's jobs
  (the company's description and score show in the filter chip's tooltip).
- **Filters** (rail): Strong fit 75+ (job score), Has contacts, Not applied, Pinned, and a
  company list with counts as a multi-select filter. This replaces the rail's company
  outline and its scroll spy.
- **Sorts**: Best fit (rank), Pinned first, Least experience required, Company A-Z.
- **Stats strip**: jobs, companies, contacts, applied, connected, pinned (same items, jobs
  first).
- **Removed**: the company / type view toggle, company panels, Expand all / Collapse all.
  The cross-search Companies page (entities) still lists companies.

## Cost and time targets

From `backend/logs/llm_usage.csv`, ranking sees about 40-60 listings today.

| | Today | Target |
|---|---|---|
| LLM cost per search | ≈$0.006 (≈$0.033 with Sonnet rescore) | ≈$0.04-0.05 |
| Rank input | 3.5-8.4k tokens (Haiku) | ≈8-10k tokens (Sonnet, 30 cards) |
| Added read time | 0-25 s | 10-20 s (parallel, 8 s timeout per batch) |

## Phases

Each phase is its own commit and leaves the app working.

1. **Measure.** Script in `research/`: for recent searches, jobs found per board, how many
   have full text from the API, and read times for the rest. Confirms `RANK_MAX_JOBS` and
   the cost estimate.
2. **`JobPosting` and completion.** Model, board parsers (Greenhouse per-job content,
   BuiltIn and Workable job pages), page-read fallback, `text_source` in the trace. Split
   `pipeline/steps.py` (1,247 lines) into a `pipeline/steps/` package as part of this.
3. **filter + rank_jobs.** New prompt and node, `RANK_MODEL`, `RANK_MAX_JOBS`, `MAX_JOBS`;
   results built in job order; remove `rank_companies`, `rescore_jobs`, `read_postings`.
4. **compile slimmed** to people notes, messages and company descriptions.
5. **UI**: job cards, contacts on the card, company filter, new sorts and stats; old
   searches still open.
6. **Docs and settings**: README settings table, `.env.example`, `pipeline/AGENTS.md`.

## Open questions

- `MAX_JOBS` default: 12 jobs is about the same reading as 6 companies × 2 jobs today.
- Should a company with many strong jobs be capped (e.g. at most 3 cards per company), so one
  employer doesn't fill the list?
