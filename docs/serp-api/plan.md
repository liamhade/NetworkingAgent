# Google results through a SERP API

**Date:** 2026-11-24

## Why the Chrome path stopped working

A full pipeline run sends ~12 Google searches plus ~30 `/goto` link resolutions in a few
minutes from one IP. Google first degrades the results (it drops `site:linkedin.com/in`
and serves job boards, which `linkedin_people` reports as "Google returned job listings
instead of LinkedIn profiles (asked twice)"), then serves `/sorry/` CAPTCHA pages to
every query. Once flagged, `GoogleSerpSession.search` waits 3 minutes for a person and
raises `CaptchaTimeoutError`. Unattended scraping of google.com from one machine can't
avoid this; working around it (proxy rotation, fingerprint spoofing) would be evading
Google's bot protection, so we don't.

## Change

Get the same results from a licensed SERP API that runs the searches on its side:

- `google_serp/api.py`: `SerperClient` (serper.dev, `POST /search`) and `SerpApiClient`
  (serpapi.com, `GET /search.json?engine=google`), both returning the existing
  `SearchResponse` / `SearchResult`. Results carry **direct URLs** (no `/goto`
  resolution, which was the slowest step and a CAPTCHA trigger), titles, snippets,
  display URL, site name, plus new `position` and `date` metadata. `client_from_env()`
  picks one from `SERPER_API_KEY` or `SERPAPI_API_KEY`; none -> `None`.
- `tools._GoogleWorker`: uses the API client when one is configured, else Chrome as
  before. It only starts Chrome to resolve links when a result still has a `/goto` URL.
- `python -m google_serp "query"`: prints a page of results and the time it took.
- Offline tests with recorded-shape JSON fixtures.

Target: one page (10 results) in under 5 s. Serper typically answers in 1-2 s.
