"""The `find_people` node and the people-search fallback ladder."""

import logging
from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel

import config
import linkedin
import tools
from pipeline.state import (
    Person,
    PipelineState,
)
from pipeline.steps.common import call, clean_schools, plural, status, url_key
from schemas import (
    TraceStep,
)

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ----------------------------------------------------------------------- find_people


def ladder(keywords: Iterable[str], location: str) -> list[tuple[str, str]]:
    """The people-search fallback ladder: planned keywords, then "recruiter", then the
    company name only (no keywords, no location)."""
    rungs = [(k.strip(), location) for k in keywords if k.strip()]
    rungs += [("recruiter", location), ("", "")]
    unique: list[tuple[str, str]] = []
    for rung in rungs:
        if (rung[0].lower(), rung[1].lower()) not in {
            (k.lower(), loc.lower()) for k, loc in unique
        }:
            unique.append(rung)
    return unique


def similar_ladder(
    keywords: Iterable[str], location: str, max_queries: int
) -> list[tuple[str, str]]:
    """The similar-background relaxation ladder, at most `max_queries` rungs, each one
    also requiring the user's school: the first planned keywords and the location, then
    the company and location only, then the company only (no keywords, no location)."""
    first = next((k.strip() for k in keywords if k.strip()), "")
    rungs: list[tuple[str, str]] = []
    for rung in [(first, location), ("", location), ("", "")]:
        if rung not in rungs:
            rungs.append(rung)
    return rungs[: max(0, max_queries)]


def search_similar_people(
    company: str,
    education: Iterable[str],
    keywords: Iterable[str],
    location: str,
    step: str,
    people: list[Person],
    seen: set[str],
) -> list[TraceStep]:
    """Find people at `company` who share the user's school, merging them into `people`.

    Searches for the user's first school only, climbing `similar_ladder` until
    `PEOPLE_SIMILAR_PER_COMPANY` people with a visible shared school were found, and never
    running more than `PEOPLE_SIMILAR_MAX_QUERIES` Google searches. A person already in
    `people` (by profile URL) is not added again, but is marked if the result shows the
    school. Skipped (no query) when the user has no school or the knob is 0.
    """
    schools = clean_schools(education)
    rungs = similar_ladder(keywords, location, config.PEOPLE_SIMILAR_MAX_QUERIES)
    if not schools or not rungs:
        return []
    school = schools[0]
    label = f"Same school: {school}"
    by_key = {url_key(p.url): p for p in people}
    trace: list[TraceStep] = []
    for words, where in rungs:
        status(f"Looking for {school} alumni at {company}")
        args = {"company": company, "keywords": words, "location": where, "school": school}
        found, rung = call(
            step,
            "linkedin_people",
            args,
            lambda w=words, loc=where: tools.linkedin_people(
                company, w, loc, n=config.PEOPLE_SEARCH_N, school=school
            ),
        )
        trace.append(rung)
        for raw in found or []:
            if not raw.get("url"):
                continue
            key = url_key(raw["url"])
            shared = bool(raw.get("at_company")) and linkedin.mentions_school(raw, school)
            person = by_key.get(key)
            if person is None and key in seen:
                continue  # already known (e.g. saved earlier): don't add it again
            if person is None:
                person = Person.model_validate({**raw, "keywords": words})
                by_key[key] = person
                seen.add(key)
                people.append(person)
            if shared and not person.shared_background:
                person.shared_background = label
        shared_count = sum(bool(p.shared_background) for p in people)
        rung.note = f"similar background: {shared_count} people with a shared school so far"
        if shared_count >= config.PEOPLE_SIMILAR_PER_COMPANY:
            break
    return trace


def search_people(
    company: str,
    keywords: Iterable[str],
    location: str,
    step: str = "find_people",
    known_urls: Iterable[str] = (),
    education: Iterable[str] = (),
) -> tuple[list[Person], list[TraceStep]]:
    """Climb the ladder until `PEOPLE_PER_COMPANY` new current employees are found, then
    search for people with the user's school (`education`), if they have one.

    Every rung is a trace step; an error on one rung is recorded and the next one runs.
    People already in `known_urls` (or found by an earlier rung) are skipped.
    """
    keywords = list(keywords)
    seen = {url_key(u) for u in known_urls}
    people: list[Person] = []
    trace: list[TraceStep] = []
    for words, where in ladder(keywords, location):
        status(f"Looking for {words or 'anyone'} at {company}")
        args = {"company": company, "keywords": words, "location": where}
        found, rung = call(
            step,
            "linkedin_people",
            args,
            lambda w=words, loc=where: tools.linkedin_people(
                company, w, loc, n=config.PEOPLE_SEARCH_N
            ),
        )
        trace.append(rung)
        for raw in found or []:
            key = url_key(raw.get("url") or "")
            if not raw.get("url") or key in seen:
                continue
            seen.add(key)
            people.append(Person.model_validate({**raw, "keywords": words}))
        current = sum(p.at_company for p in people)
        rung.note = f"{current} current employees so far"
        if current >= config.PEOPLE_PER_COMPANY:
            break
    trace += search_similar_people(company, education, keywords, location, step, people, seen)
    return people, trace


QUERY_MAX_SEARCHES = 3
"""Most Google searches for one `search_people_by_query` call."""


def search_people_by_query(
    company: str,
    keywords: Iterable[str],
    location: str,
    school: str,
    step: str,
    known_urls: Iterable[str] = (),
) -> tuple[list[Person], list[TraceStep]]:
    """People at `company` for given search terms (the people pane's "only people from my
    school" search).

    One search per keyword phrase (or one with no keywords), then, while fewer than
    `PEOPLE_PER_COMPANY` current employees were found, the first one again without the
    location. At most `QUERY_MAX_SEARCHES` searches. With `school`, people whose result
    shows it are marked `shared_background`. Profiles in `known_urls` are skipped.
    """
    phrases = [k.strip() for k in keywords if k.strip()] or [""]
    rungs = [(words, location) for words in phrases]
    if location:
        rungs.append((phrases[0], ""))
    rungs = list(dict.fromkeys(rungs))[:QUERY_MAX_SEARCHES]
    label = f"Same school: {school}" if school else ""
    seen = {url_key(u) for u in known_urls}
    people: list[Person] = []
    trace: list[TraceStep] = []
    for i, (words, where) in enumerate(rungs):
        if i >= len(phrases) and sum(p.at_company for p in people) >= config.PEOPLE_PER_COMPANY:
            break  # the relaxed (no location) rung only runs when too few were found
        status(f"Looking for {words or 'people'}{f' from {school}' if school else ''} at {company}")
        args = {"company": company, "keywords": words, "location": where}
        if school:
            args["school"] = school
        found, rung = call(
            step,
            "linkedin_people",
            args,
            lambda w=words, loc=where: tools.linkedin_people(
                company, w, loc, n=config.PEOPLE_SEARCH_N, school=school
            ),
        )
        trace.append(rung)
        for raw in found or []:
            key = url_key(raw.get("url") or "")
            if not raw.get("url") or key in seen:
                continue
            seen.add(key)
            person = Person.model_validate({**raw, "keywords": words})
            if school and person.at_company and linkedin.mentions_school(raw, school):
                person.shared_background = label
            people.append(person)
        rung.note = f"{sum(p.at_company for p in people)} current employees so far"
    return people, trace


def find_people_node(state: PipelineState) -> dict:
    """People search for every one of the top `PEOPLE_AUTO_COMPANIES` companies."""
    location = state["plan"].people_location
    people: dict[str, list[Person]] = {}
    trace: list[TraceStep] = []
    for company in state["chosen"][: config.PEOPLE_AUTO_COMPANIES]:
        found, steps = search_people(
            company.name,
            company.people_keywords,
            location,
            education=state["request"].education,
        )
        people[company.name] = found
        trace += steps
        current = sum(p.at_company for p in found)
        similar = sum(bool(p.shared_background) for p in found)
        extra = f" ({similar} with a shared school)" if similar else ""
        status(f"{company.name}: {plural(current, 'current employee')} found{extra}")
    return {"people": people, "trace": trace}
