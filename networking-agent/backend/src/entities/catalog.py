"""Everything a user has encountered across their searches, de-duplicated by entity key.

Backs the Companies / Jobs / People pages. Pure functions over saved searches (no storage):
the server loads the user's searches and calls `companies`, `jobs` or `people`.

Merge rules (see `docs/entity-pages/plan.md`):

- Entities are identified by `entities.keys` (re-derived here with the current rules, so
  old saved searches and normalization changes are handled the same way as on reopen).
- The most recent sighting wins; a field that is blank there is filled from the newest older
  sighting that has it.
- `first_seen` / `last_seen` are the creation times of the oldest / newest search the entity
  was in; `searches` lists those searches, most recent first, without duplicates.
- Lists are ordered by `last_seen` (newest first), then by position in that search.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from entities import keys
from schemas import (
    CompanyEntity,
    JobEntity,
    PersonEntity,
    SavedSearch,
    SearchSummary,
)


@dataclass
class _Entry:
    fields: dict[str, Any]
    first_seen: datetime
    last_seen: datetime
    searches: list[SearchSummary]
    job_keys: set[str] = field(default_factory=set)
    person_keys: set[str] = field(default_factory=set)


class _Collector:
    """Accumulates sightings; must be fed searches newest first."""

    def __init__(self) -> None:
        self.entries: dict[str, _Entry] = {}  # Insertion order == display order.

    def add(self, key: str, values: dict[str, Any], search: SavedSearch) -> _Entry:
        entry = self.entries.get(key)
        if entry is None:
            entry = _Entry(
                fields=dict(values),
                first_seen=search.created_at,
                last_seen=search.created_at,
                searches=[],
            )
            self.entries[key] = entry
        else:
            # Older (or same-search duplicate) sighting: only fill blanks.
            for name, value in values.items():
                if not entry.fields.get(name) and value:
                    entry.fields[name] = value
            entry.first_seen = min(entry.first_seen, search.created_at)
            entry.last_seen = max(entry.last_seen, search.created_at)
        if all(seen.id != search.id for seen in entry.searches):
            entry.searches.append(
                SearchSummary(id=search.id, title=search.title, created_at=search.created_at)
            )
        return entry

    def sighting(self, key: str, entry: _Entry) -> dict[str, Any]:
        return {
            "key": key,
            "first_seen": entry.first_seen,
            "last_seen": entry.last_seen,
            "searches": entry.searches,
        }


@dataclass
class _Catalog:
    companies: _Collector = field(default_factory=_Collector)
    jobs: _Collector = field(default_factory=_Collector)
    people: _Collector = field(default_factory=_Collector)


def _newest_first(searches: Iterable[SavedSearch]) -> list[SavedSearch]:
    return sorted(searches, key=lambda search: search.created_at, reverse=True)


def _collect(searches: Iterable[SavedSearch]) -> _Catalog:
    catalog = _Catalog()
    for search in _newest_first(searches):
        for company in search.results.companies:
            company_key = keys.company_key(company.name)
            company_entry = catalog.companies.add(
                company_key,
                {
                    "name": company.name,
                    "url": company.url,
                    "description": company.description,
                    "alignment": company.alignment,
                },
                search,
            )
            for job in company.jobs:
                job_key = keys.job_key(job, company.name)
                company_entry.job_keys.add(job_key)
                catalog.jobs.add(
                    job_key,
                    {
                        "title": job.title,
                        "url": job.url,
                        "location": job.location,
                        "salary": job.salary,
                        "alignment": job.alignment,
                        "company": company.name,
                        "company_key": company_key,
                    },
                    search,
                )
            for person in company.people:
                person_key = keys.person_key(person, company.name)
                company_entry.person_keys.add(person_key)
                catalog.people.add(
                    person_key,
                    {
                        "name": person.name,
                        "title": person.title,
                        "profile_url": person.profile_url,
                        "alignment": person.alignment,
                        "connect_message": person.connect_message,
                        "company": company.name,
                        "company_key": company_key,
                    },
                    search,
                )
    return catalog


def companies(searches: Iterable[SavedSearch]) -> list[CompanyEntity]:
    collector = _collect(searches).companies
    return [
        CompanyEntity(
            **collector.sighting(key, entry),
            **entry.fields,
            job_count=len(entry.job_keys),
            person_count=len(entry.person_keys),
        )
        for key, entry in collector.entries.items()
    ]


def jobs(searches: Iterable[SavedSearch]) -> list[JobEntity]:
    collector = _collect(searches).jobs
    return [
        JobEntity(**collector.sighting(key, entry), **entry.fields)
        for key, entry in collector.entries.items()
    ]


def people(searches: Iterable[SavedSearch]) -> list[PersonEntity]:
    collector = _collect(searches).people
    return [
        PersonEntity(**collector.sighting(key, entry), **entry.fields)
        for key, entry in collector.entries.items()
    ]
