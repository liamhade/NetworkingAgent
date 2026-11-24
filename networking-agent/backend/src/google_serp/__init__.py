"""Google search for the agent's Google tools: a SERP API when a key is set, else Chrome.

client = client_from_env()                             # SERPER_API_KEY / SERPAPI_API_KEY
response = client.search("python requests library")    # direct URLs, ~1-2 s

session = GoogleSerpSession().start()                  # fallback: real Chrome
response = session.search("python requests library")  # links are Google /goto redirects
session.resolve_results(response.results[:3])          # follow only the ones you need
session.close()
"""

from .api import SerpApiClient, SerpApiError, SerpClient, SerperClient, client_from_env
from .models import SearchResponse, SearchResult
from .session import CaptchaTimeoutError, GoogleSerpSession

__all__ = [
    "CaptchaTimeoutError",
    "GoogleSerpSession",
    "SearchResponse",
    "SearchResult",
    "SerpApiClient",
    "SerpApiError",
    "SerpClient",
    "SerperClient",
    "client_from_env",
]
