# Google SERP speed — findings

Goal: speed up Google SERP results without tripping bot detection, while keeping full redirect links.

## Where the time went (before)

Measured on the warm profile, 2 queries 8 s apart, instrumented scratch script.

| Phase | Time |
|---|---|
| Chrome launch | 0.61 s (once) |
| goto → `domcontentloaded` | 0.39–0.46 s |
| `#rso` present | 0.42–0.58 s |
| `load` (previous wait condition) | 0.66–1.17 s |
| `content()` | 0.03–0.06 s |
| BeautifulSoup parse | 0.05–0.23 s |
| **Sequential `/goto` resolution** | **22.2–23.3 s of a 23.7–24.0 s query (~95%)** |
| Close | 0.19 s |

- Per-link times (query 1): 0.13, 0.20, 0.40, 3.10, 0.05, 4.11, 5.10, 9.10, 0.04 s.
- Each `/goto` request itself is ~0.05 s. Google allows ~3 quickly, then serves a meta-refresh interstitial on roughly every other link with growing delays (3, 4, 5, 9/11 s). The allowance refills slowly (query 2 showed the same pattern).
- No sleeps/jitter in our code; no consent page appeared.
- Page weight: ~23 scripts (1.6 MB), 3 fonts, 6–8 images, mostly served from the profile cache; none delay `#rso`.
- The `ping` attribute carries the same opaque token, not the destination URL.
- Destination URLs appeared in raw HTML for 3/3 results on one page and 0/3 on another — not reliable to parse.

## After (live, through tools.py)

| Call | Before | After |
|---|---|---|
| `google_search` n=5 | 23.7 s (resolved all 10) | **5.3 s** incl. 0.6 s launch |
| `find_people` n=5 (1 LinkedIn hit) | 24.0 s | **0.6 s** |
| Repeat query within 15 min | ~24 s | **0.001 s** (cache) |
| `fetch_html` | 0.70–1.23 s | 0.52–0.56 s |
| `google_search` n=10 | ~23 s | ~23 s (bounded by Google's throttle) |

## Changes implemented

- `google_serp/session.py`: `fetch_html` waits for `domcontentloaded` then `#search, #rso` instead of full `load`. New `resolve_results(results)` resolves in place (skips unresolved/already-resolved; failures keep the `/goto` URL). New `search(..., resolve_limit=None)` — default unchanged (resolve all).
- `tools.py`: `_GoogleWorker.search(query, resolve_urls, pick=None)` fetches without resolving, lets `pick` choose the results the tool will return, and resolves only those. Per-query page cache (15 min TTL, 64 entries, empty pages not cached); previously resolved links stay resolved. Restart-once-on-failure kept. `google_search` resolves only `results[:n]`; `find_people` resolves only the first n LinkedIn-looking results (pre-filtered by URL/breadcrumb/site name/title, re-filtered after resolving). Tool docstrings say "2-25 seconds (larger n is slower)".
- `config.py`: `GOOGLE_CACHE_TTL_S` (default 900; 0 disables).
- Tests: `tests/google_serp/test_session.py`, `tests/test_google_worker.py`, updated fakes in `tests/test_tools.py`.

**Redirect links preserved:** `resolve_url` is unchanged — `url` is still the 302 `Location` used verbatim after honouring any meta-refresh hop, and `google_url` keeps the `/goto` link. Live before/after comparison gave identical hosts and lengths; no returned URL still pointed at `/goto`. Results the tool doesn't return are no longer resolved (the agent never saw them anyway).

## Considered, not implemented

| Idea | Verdict |
|---|---|
| Skip/shorten meta-refresh delay | Rejected — ignoring Google's delay is a classic bot signal, likely `/sorry/` CAPTCHAs. |
| Parallel resolution / multiple browsers or profiles | Rejected — throttle is per session with escalating delays; bursts hit it sooner. Profile is single-process. |
| Block images/fonts via `page.route` | Saves ≤0.1–0.3 s; asset-less page looks less human. Not worth it. |
| Single `page.evaluate` extraction | Saves ~0.1–0.3 s but loses offline fixture-tested parser. Not worth it. |
| `num=` parameter | Unsupported by Google since 2025; unusual params are a signal. |
| Parse destination URLs from HTML | Unreliable (see above). |
| Reduce jitter | None exists. If CAPTCHAs appear, add 1–3 s random gaps between searches. |
| Lower default `google_search` n from 10 to 5 | ~5 s instead of ~22 s for the common call — product decision, left as is. |

## Verification

- pytest 167 passed; ruff check and format clean.
- No CAPTCHA, `/sorry/`, or 429 encountered. Total live usage: 8 SERP loads and ~45 `/goto` requests, ≥8 s apart.

## Caveats

- Cache is in-memory, per process. Cached-but-unresolved `/goto` tokens may expire; a failed later resolve keeps the `/goto` link.
- `site:linkedin.com/in "Company" ...` people queries returned mostly job boards (1 LinkedIn profile), before and after — needs a separate look.
- Pre-existing: after `tools.shutdown()` the atexit hook calls `_GoogleWorker.close()` again and logs a harmless `RuntimeError: cannot schedule new futures after shutdown`.
