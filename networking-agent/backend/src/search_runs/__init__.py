"""Searches that run in the background, independent of any HTTP request.

- `start(user_id, request, search_id)`: save a `running` record and run the pipeline in a
  daemon thread. Leaving the page (or closing the stream) never cancels it.
- `attach(user_id, search_id)`: the events of a search, replayed from the start and then
  live until it ends; works for running and finished searches.

Design: `docs/background-searches/plan.md`.
"""

from search_runs.runner import attach, start

__all__ = ["attach", "start"]
