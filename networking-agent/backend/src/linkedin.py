"""Find LinkedIn profiles through Google: query building, profile filtering and parsing.

Pure functions (no browser), used by the `linkedin_people` tool in `tools.py`.

What Google returns for `site:linkedin.com/in "<company>" <keywords>` (Nov 2026):

- Profile results have the site label `LinkedIn · <Name>`, a title
  `<Name> - <Headline>` (no `| LinkedIn` suffix), no breadcrumb (the `<cite>` holds
  "1.2K+ followers"), and a snippet `<Location> · <Current title> · <Company> ...`.
- Sometimes Google silently ignores the `site:` operator and serves a generic
  job-board page (Glassdoor, ZipRecruiter, LinkedIn job listings, ~60 results). The
  same query a little later returns profiles again. See
  `docs/linkedin-people/findings.md`.
"""

import re
from urllib.parse import urlparse

from google_serp import SearchResult
from google_serp.parser import is_google_redirect

SITE = "site:linkedin.com/in"

_PROFILE_URL = re.compile(r"^https?://([a-z0-9-]+\.)?linkedin\.com/in/[^/?#]+", re.IGNORECASE)
_NAMED_SITE = re.compile(r"^LinkedIn\s*[·•]\s*(?P<name>\S.*)$")
_TITLE_SUFFIX = re.compile(r"\s*[|·]\s*LinkedIn\s*$", re.IGNORECASE)
_NAME_SEPARATOR = re.compile(r"\s[-–—]\s")
"""Between name and headline: a hyphen, or an en/em dash on some profiles."""
_NOT_PROFILE_TITLE = re.compile(r"(?:'s|’s)? Post$| on LinkedIn: |\bjobs in\b", re.IGNORECASE)
_LOCATION_COUNTRIES = {
    "united states",
    "united kingdom",
    "canada",
    "india",
    "germany",
    "france",
    "australia",
    "ireland",
    "netherlands",
    "singapore",
}
_HEADLINE_COMPANY = re.compile(r"(?:\bat\b|@)\s*([^|·,()]+)", re.IGNORECASE)
_EXPERIENCE = re.compile(r"\bExperience:\s*([^·]+?)\s*(?:·|$)")


def _clean_company(company: str) -> str:
    return " ".join(company.replace('"', " ").split())


def build_query(company: str, keywords: str, location: str = "") -> str:
    """The people query: `site:linkedin.com/in "Company" keywords location`.

    The operator works as well at the end as at the start, and both beat no operator.
    An unquoted company name matches the word anywhere (e.g. "ramp" in a job title).
    """
    parts = [SITE, f'"{_clean_company(company)}"', keywords.strip(), location.strip()]
    return " ".join(p for p in parts if p)


def retry_query(company: str, keywords: str, location: str = "") -> str:
    """Same search with the operator at the end, used when Google ignored the first one."""
    parts = [f'"{_clean_company(company)}"', keywords.strip(), location.strip(), SITE]
    return " ".join(p for p in parts if p)


def is_profile_url(url: str) -> bool:
    """True for a LinkedIn member profile URL (any country subdomain)."""
    return bool(_PROFILE_URL.match(url))


def is_linkedin_result(result: SearchResult) -> bool:
    """True for any LinkedIn result (profile, post, job, company page...)."""
    host = urlparse(result.url).netloc.lower()
    return (
        host.endswith("linkedin.com")
        or "linkedin.com" in result.display_url.lower()
        or result.site_name.replace("\xa0", " ").startswith("LinkedIn")
    )


def looks_like_profile(result: SearchResult) -> bool:
    """True for a LinkedIn profile result.

    A resolved link is checked strictly (`linkedin.com/in/...`). An unresolved Google
    redirect link is judged from the site label, breadcrumb and title instead.
    """
    if result.url and not is_google_redirect(result.url):
        return is_profile_url(result.url)
    if not is_linkedin_result(result):
        return False
    crumbs = [c.strip().lower() for c in result.display_url.split("›")[1:]]
    # Breadcrumbs: "linkedin.com › in › slug" for profiles, "› jobs ›", "› posts ›"... for
    # the rest; "› ..." when elided (country subdomains), where "jobs" may still show later.
    if crumbs and (crumbs[0] not in ("in", "...") or any("jobs" in c for c in crumbs)):
        return False
    title = _TITLE_SUFFIX.sub("", result.title).strip()
    if _NOT_PROFILE_TITLE.search(title):
        return False
    named = _NAMED_SITE.match(result.site_name.replace("\xa0", " "))
    # Profiles are titled "Name - Headline" (or just "Name"); posts and articles aren't.
    return bool(_NAME_SEPARATOR.search(title)) or bool(
        named and named.group("name").strip() == title
    )


def operator_ignored(results: list[SearchResult]) -> bool:
    """True if Google ignored `site:linkedin.com/in`: most results aren't on LinkedIn."""
    if not results:
        return False
    on_linkedin = sum(is_linkedin_result(r) for r in results)
    return on_linkedin * 2 < len(results)


def parse_linkedin_title(title: str) -> tuple[str, str]:
    """Split a LinkedIn result title into (name, headline).

    `"Jane Doe - Data Scientist - Acme | LinkedIn"` -> `("Jane Doe", "Data Scientist - Acme")`.
    """
    title = _TITLE_SUFFIX.sub("", title).strip()
    parts = _NAME_SEPARATOR.split(title, maxsplit=1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _mentions(text: str, company: str) -> bool:
    """`company` appears in `text` as whole words, case-insensitively."""
    target = _norm(company)
    return bool(target) and f" {target} " in f" {_norm(text)} "


def _is_location(segment: str) -> bool:
    s = segment.strip()
    return "," in s or s.endswith(" Area") or s.lower() in _LOCATION_COUNTRIES


def parse_profile(result: SearchResult, company: str) -> dict:
    """Name, headline, current title/company, location and whether they're at `company`.

    `company` and `title` come from the snippet's `<Location> · <Title> · <Company> ...`
    pattern when present, else from "Experience: X" or "<role> at/@ X" in the headline.
    `at_company` is True when their current company (or headline) names `company` and
    they aren't marked as having left ("Ex-Ramp", "former").
    """
    name, headline = parse_linkedin_title(result.title)
    named = _NAMED_SITE.match(result.site_name.replace("\xa0", " "))
    if named:
        name = named.group("name").strip()
    headline = re.sub(r"\s*(?:\.\.\.|…)$", "…", headline)

    snippet = result.snippet.replace("\xa0", " ")
    segments = [s.strip() for s in snippet.split(" · ")]
    location = title = current = ""
    if len(segments) >= 3 and _is_location(segments[0]):
        location, title, current = segments[0], segments[1], segments[2]
        if ":" in title:  # e.g. "Datadog Experience: Datadog": no title shown
            title = ""

    found = ""
    # The snippet runs the current company into the about text ("Ramp Data at Ramp ..."),
    # so only the target company can be recognised there.
    if current and _norm(company) and f"{_norm(current)} ".startswith(f"{_norm(company)} "):
        found = current[: len(_clean_company(company))]
    if not found:
        match = _EXPERIENCE.search(snippet)
        if match:
            found = match.group(1).strip()
    if not found:
        match = _HEADLINE_COMPANY.search(headline)
        if match:
            found = match.group(1).strip(" …")

    left = re.search(rf"\b(?:ex|former(?:ly)?)[\s-]+{re.escape(_norm(company))}\b", _norm(headline))
    at_company = not left and (
        _mentions(found, company) or (not found and _mentions(headline, company))
    )
    return {
        "name": name,
        "headline": headline,
        "title": title,
        "company": found,
        "at_company": at_company,
        "location": location,
        "url": result.url,
    }
