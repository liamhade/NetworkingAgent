"""Google search through a real Chrome browser, for the agent's Google tools.

session = GoogleSerpSession().start()
response = session.search("python requests library")  # links are Google /goto redirects
session.resolve_results(response.results[:3])          # follow only the ones you need
session.close()
"""

from .models import SearchResponse, SearchResult
from .session import CaptchaTimeoutError, GoogleSerpSession

__all__ = ["CaptchaTimeoutError", "GoogleSerpSession", "SearchResponse", "SearchResult"]
