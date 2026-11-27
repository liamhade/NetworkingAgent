"""On-demand people search for one company of a saved search ("Find People To Connect With").

Runs the same fallback ladder as the `find_people` node (a job's title becomes the first
keyword set), writes alignment and connection notes for the people found in one small LLM
call, and merges them into the saved search under a per-search lock.

Concurrency: requests run in parallel (FastAPI threadpool). Google searches are queued in
the single shared Chrome worker (`tools._GoogleWorker`); the LLM calls run in parallel.
Only the final read-modify-write of the saved-search file is serialized, per search.
"""

import logging

from langchain_core.language_models import BaseChatModel

import prompts
from entities import keys
from llm import get_llm
from pipeline import steps
from pipeline.state import PeopleNotes, Person
from schemas import CompanyResult, JobResult, PersonResult, SavedSearch, TraceStep
from userdata import history

log = logging.getLogger(__name__)

STEP = "find_people_on_demand"
SCHOOL_STEP = "find_people_same_school"


class NotFound(LookupError):
    """The search, company or job doesn't exist (for this user)."""


def _company(record: SavedSearch, company_key: str) -> CompanyResult:
    for company in keys.annotate(record.results).companies:
        if company.key == company_key:
            return company
    raise NotFound("Company not found in this search.")


def _job(company: CompanyResult, job_key: str | None) -> JobResult | None:
    if not job_key:
        return None
    for job in company.jobs:
        if job.key == job_key:
            return job
    raise NotFound("Job not found at this company.")


def _city(location: str) -> str:
    """ "New York, NY" -> "New York" (people searches work best with just a city)."""
    return location.split(",")[0].strip()


class NoSchool(ValueError):
    """`same_school` was asked for, but the search's profile has no school."""


def _notes(
    llm: BaseChatModel,
    record: SavedSearch,
    company: CompanyResult,
    job: JobResult | None,
    found: list[Person],
) -> tuple[list[PersonResult], TraceStep]:
    """Alignment and connection notes for `found`, restricted to them. Falls back to
    current employees without notes if the LLM call fails."""
    data = {
        "company": {"name": company.name, "description": company.description},
        "job": job.model_dump(include={"title", "url", "location", "salary"}) if job else None,
        "people": [steps.person_data(p) for p in found],
    }
    human = f"{steps.format_profile(record.request)}\n\n<research>\n{steps.dump(data)}\n</research>"
    notes, trace = steps.call(
        STEP,
        "llm",
        {"people": len(found)},
        lambda: steps.structured(llm, PeopleNotes, prompts.people_notes_prompt(), human, STEP),
    )
    if notes is not None:
        return steps.match_people(notes.people, found), trace
    fallback = [
        PersonResult(
            name=p.name,
            title=p.title or p.headline,
            profile_url=p.url,
            alignment="",
            shared_background=p.shared_background,
        )
        for p in found
        if p.at_company
    ]
    return fallback, trace


def _merge(
    record: SavedSearch, company_key: str, people: list[PersonResult], trace: list[TraceStep]
) -> SavedSearch:
    """`record` with `people` added to the company (deduped by person key), the company
    marked as searched, and `trace` appended."""
    results = keys.annotate(record.results)
    companies = []
    for company in results.companies:
        if company.key == company_key:
            known = {p.key for p in company.people}
            added = []
            for person in people:
                key = keys.person_key(person, company.name)
                if key not in known:
                    known.add(key)
                    added.append(person.model_copy(update={"key": key}))
            company = company.model_copy(
                update={"people": [*company.people, *added], "people_searched": True}
            )
        companies.append(company)
    return record.model_copy(
        update={
            "results": results.model_copy(update={"companies": companies}),
            "trace": [*(record.trace or []), *trace],
        }
    )


def find_people(
    user_id: str,
    search_id: str,
    company_key: str,
    job_key: str | None = None,
    llm: BaseChatModel | None = None,
    same_school: bool = False,
) -> CompanyResult:
    """Find people at one company of a saved search, save them, return the updated company.

    With `same_school`, only people from the user's first school are searched for
    (`steps.search_people_by_query`), instead of the usual ladder.
    """
    record = history.get_search(user_id, search_id)
    if record is None:
        raise NotFound("Search not found.")
    company = _company(record, company_key)
    job = _job(company, job_key)

    known_urls = [p.profile_url for p in company.people]
    city = _city(record.request.location)
    keywords = [job.title] if job else []
    if same_school:
        schools = steps.clean_schools(record.request.education)
        if not schools:
            raise NoSchool("Add your school on the Search page to find people from it.")
        found, trace = steps.search_people_by_query(
            company.name, keywords, city, schools[0], SCHOOL_STEP, known_urls
        )
    else:
        keywords += company.people_keywords
        found, trace = steps.search_people(
            company.name,
            keywords,
            city,
            STEP,
            known_urls,
            education=record.request.education,
        )
    people: list[PersonResult] = []
    if found:
        people, notes_trace = _notes(llm or get_llm(), record, company, job, found)
        trace.append(notes_trace)

    updated = history.update_search(
        user_id, search_id, lambda current: _merge(current, company_key, people, trace)
    )
    if updated is None:
        raise NotFound("Search not found.")
    return _company(updated, company_key)
