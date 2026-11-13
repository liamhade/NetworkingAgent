"""Search Google from Python by driving a real Chrome browser.

import google_serp

response = google_serp.search("python requests library")
for result in response.results:
    print(result.position, result.title, result.url)

# Several searches in one browser
with google_serp.GoogleSerpSession() as serp:
    for q in ["python requests", "playwright python"]:
        print(len(serp.search(q).results))
"""

from .errors import CaptchaTimeoutError, GoogleSerpError
from .models import SearchMetadata, SearchResponse, SearchResult
from .parser import parse_results_page
from .session import GoogleSerpSession, default_profile_dir, search

__version__ = "0.1.0"

__all__ = [
    "search",
    "GoogleSerpSession",
    "SearchResponse",
    "SearchResult",
    "SearchMetadata",
    "GoogleSerpError",
    "CaptchaTimeoutError",
    "parse_results_page",
    "default_profile_dir",
    "__version__",
]
