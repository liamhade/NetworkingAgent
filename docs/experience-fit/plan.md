# Experience-aware fit scores

## Problem

Job "best fit" scores come from the `rank_companies` LLM step (`RANK_PROMPT`). It saw each
job's title, company, location, salary and a 160-character summary, so a requirement like
"4-5 years of experience" was almost never in front of it. People with no experience got
mid-level jobs as their best fits.

## Changes

1. **Hard seniority rule in `RANK_PROMPT`.** A job that needs much more experience than the
   user has (e.g. 3+ years for someone with none) scores at most 40, however well the role
   matches; a company whose relevant jobs are all like that scores at most 50. The model is
   told to read `years_required`, `level` and seniority words in the title.
2. **`years_required` and `level` on every job, before ranking.**
   - `backend/src/experience.py`: `years_required(*texts)` finds "5+ years", "3-5 years",
     "minimum of two years", "4 years of ... experience" and returns the smallest minimum
     ("" if none). Company ages ("for 40 years") and programme lengths are ignored.
   - Sources: BuiltInNYC (card description + title; `experience_level` becomes `level`),
     Conservation Job Board (its "0 - 1 year" field), USAJOBS (summary), Lever (description,
     lists, closing text), Ashby (`descriptionPlain`), Google results (title + snippet).
     Greenhouse (no description without `?content=true`) and Workable (no description) rely
     on the title.
   - `pipeline.state.Job` gains `level` and `years_required`; `_jobs_table` sends both.

## Experiment: read postings before ranking

See [experiment.md](experiment.md) for the cost and latency of rescoring the top jobs with
their full posting text.
