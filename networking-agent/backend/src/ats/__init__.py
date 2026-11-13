"""Employer-direct job postings from applicant tracking systems (ATS) such as Greenhouse.

Google `site:` searches find which companies have a board for a role; each board's public
JSON API then lists its open postings, which are matched to the user's keywords and
location. Providers plug in through `registry.PROVIDERS` (see `AGENTS.md`).

```python
from ats import filter_jobs, get_provider

greenhouse = get_provider("greenhouse")
ref = greenhouse.parse_url("https://job-boards.greenhouse.io/discord/jobs/8917177002")
jobs = filter_jobs(greenhouse.list_jobs(ref.slug), "counsel", "San Francisco")
```
"""

from .base import Provider
from .models import AtsJob, Board, BoardRef
from .registry import PROVIDERS, get_provider, parse_url
from .search import (
    board_ref,
    boards_from_results,
    filter_jobs,
    matches_keywords,
    matches_location,
    merge_boards,
    needs_resolving,
    site_query,
)

__all__ = [
    "PROVIDERS",
    "AtsJob",
    "Board",
    "BoardRef",
    "Provider",
    "board_ref",
    "boards_from_results",
    "filter_jobs",
    "get_provider",
    "matches_keywords",
    "matches_location",
    "merge_boards",
    "needs_resolving",
    "parse_url",
    "site_query",
]
