"""Deterministic identity keys for jobs, people and companies.

Every search is a fresh agent run, so the same job or person comes back as a brand-new
object. Anything that must survive across searches (APPLIED / CONNECTED toggles, the
cross-search Companies/Jobs/People lists) is keyed by the strings built here.

Key format: `<kind>:<scheme>:<value>`, e.g. `job:url:linkedin.com/jobs/view/3812345678`.

- Job: `job:url:<normalized posting url>`, else `job:name:<company>|<title>`.
- Person: `person:linkedin:<profile slug>`, else `person:url:<normalized url>`, else
  `person:name:<name>|<company>`.
- Company: `company:name:<company name>` (names are stabler than the URLs the agent picks).

See `docs/applied-connected/plan.md` for the reasoning.
"""

import re
import unicodedata
from typing import Literal
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit

from schemas import CompanyResult, JobResult, PersonResult, SearchResults

EntityKind = Literal["job", "person", "company"]

_TRACKING_PARAMS = frozenset(
    {
        "gclid",
        "gclsrc",
        "dclid",
        "fbclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "igshid",
        "_hsenc",
        "_hsmi",
        "ref",
        "refid",
        "ref_src",
        "referrer",
        "src",
        "source",
        "trk",
        "trkinfo",
        "trackingid",
        "tracking_id",
        "lipi",
        "originalsubdomain",
        "gh_src",
        "si",
        "from",
        "position",
        "pagenum",
        "searchid",
    }
)
_TRACKING_PREFIXES = ("utm_", "lever-", "trk_", "hs_")
_LEGAL_SUFFIXES = frozenset(
    {"inc", "incorporated", "llc", "llp", "ltd", "limited", "corp", "corporation", "co", "plc"}
)
_LINKEDIN_JOB_ID = re.compile(r"^/jobs/view/(?:[^/]*?-)?(\d+)$")
_LINKEDIN_PROFILE = re.compile(r"^/(?:in|pub)/([^/]+)")


def normalize_text(text: str) -> str:
    """Accent-free, case-folded, punctuation-free, single-spaced text."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w]+", " ", stripped.casefold()).replace("_", " ").split())


def normalize_company_name(name: str) -> str:
    words = normalize_text(name).split()
    while len(words) > 1 and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def _host(netloc_host: str) -> str:
    host = netloc_host.lower().rstrip(".")
    for prefix in ("www.", "m."):
        host = host.removeprefix(prefix)
    if host.endswith(".linkedin.com"):
        host = "linkedin.com"  # Country subdomains (uk., de., ...) are the same site.
    return host


def _is_tracking(param: str) -> bool:
    name = param.lower()
    return name in _TRACKING_PARAMS or name.startswith(_TRACKING_PREFIXES)


def normalize_url(url: str) -> str | None:
    """Canonical `host/path?query` for an http(s) URL, or None if it isn't one.

    Drops the scheme, `www.`, default ports, the fragment, trailing slashes and tracking
    parameters; sorts the remaining parameters. LinkedIn and Indeed URLs are reduced to the
    part that identifies the posting/profile.
    """
    try:
        parts = urlsplit(url.strip())
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not hostname:
        return None
    host = _host(hostname)
    if port and port not in (80, 443):
        host = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/")
    params = parse_qsl(parts.query, keep_blank_values=True)

    if host == "linkedin.com":
        path = unquote(path).lower()
        job_id = next((value for key, value in params if key == "currentJobId"), None)
        match = _LINKEDIN_JOB_ID.match(path)
        if match:
            job_id = match.group(1)
        if job_id and job_id.isdigit():
            return f"linkedin.com/jobs/view/{job_id}"
        return f"{host}{path}"

    if host.endswith("indeed.com"):
        job_id = next((value for key, value in params if key in ("jk", "vjk")), None)
        if job_id:
            return f"indeed.com/viewjob?jk={job_id.lower()}"

    kept = sorted((key, value) for key, value in params if not _is_tracking(key))
    query = f"?{urlencode(kept)}" if kept else ""
    return f"{host}{path}{query}"


def linkedin_profile_slug(url: str) -> str | None:
    """`jane-doe-123` for `https://uk.linkedin.com/in/Jane-Doe-123/?trk=x`, else None."""
    normalized = normalize_url(url)
    if not normalized or not normalized.startswith("linkedin.com/"):
        return None
    match = _LINKEDIN_PROFILE.match(normalized.removeprefix("linkedin.com"))
    return match.group(1) if match else None


def company_key(company_name: str) -> str:
    return f"company:name:{normalize_company_name(company_name)}"


def job_key(job: JobResult, company_name: str) -> str:
    url = normalize_url(job.url)
    if url:
        return f"job:url:{url}"
    return f"job:name:{normalize_company_name(company_name)}|{normalize_text(job.title)}"


def person_key(person: PersonResult, company_name: str) -> str:
    slug = linkedin_profile_slug(person.profile_url)
    if slug:
        return f"person:linkedin:{slug}"
    url = normalize_url(person.profile_url)
    if url:
        return f"person:url:{url}"
    return f"person:name:{normalize_text(person.name)}|{normalize_company_name(company_name)}"


def _annotate_company(company: CompanyResult) -> CompanyResult:
    return company.model_copy(
        update={
            "key": company_key(company.name),
            "jobs": [
                job.model_copy(update={"key": job_key(job, company.name)}) for job in company.jobs
            ],
            "people": [
                person.model_copy(update={"key": person_key(person, company.name)})
                for person in company.people
            ],
        }
    )


def annotate(results: SearchResults) -> SearchResults:
    """A copy of `results` with `key` filled in on every company, job and person."""
    return results.model_copy(
        update={"companies": [_annotate_company(company) for company in results.companies]}
    )
