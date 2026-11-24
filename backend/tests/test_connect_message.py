"""Example LinkedIn connection note (`PersonResult.connect_message`)."""

from datetime import UTC, datetime, timedelta

import pytest
from anthropic import transform_schema
from pipeline_fakes import COMPANIES, FakeSources, compiled, plan
from pipeline_fakes import DEFAULT_RANKING as RANKING

import config
import pipeline
import prompts
from entities import catalog
from pipeline.state import CompanyRanking, SearchPlan
from schemas import (
    CompanyResult,
    PersonResult,
    SavedSearch,
    SearchRequest,
    SearchResults,
    clamp_message,
)

REQUEST = SearchRequest(background="Data analyst, 3 years SQL.", looking_for="Analyst roles")


def _person(message: str = "", **extra: str) -> PersonResult:
    return PersonResult.model_validate(
        {
            "name": "Jane Doe",
            "title": "Analytics Manager",
            "profile_url": "https://linkedin.com/in/jane",
            "alignment": "You both work in fintech analytics.",
            "connect_message": message,
            **extra,
        }
    )


# --- clamp_message ---------------------------------------------------------------------


def test_clamp_keeps_short_messages() -> None:
    assert clamp_message("  Hi Jane, let's connect!  ", 300) == "Hi Jane, let's connect!"


def test_clamp_cuts_at_last_sentence_that_fits() -> None:
    text = "Hi Jane, I saw your work on payments analytics. Would love to connect. " + "x" * 50
    assert clamp_message(text, 80) == (
        "Hi Jane, I saw your work on payments analytics. Would love to connect."
    )


def test_clamp_cuts_at_word_boundary_with_ellipsis() -> None:
    text = "Hi Jane I am a data analyst who loves fintech and would really like to connect"
    clamped = clamp_message(text, 40)
    assert len(clamped) <= 40
    assert clamped.endswith("…")
    assert text.startswith(clamped[:-1])
    assert not clamped[:-1].endswith(" ")


@pytest.mark.parametrize("limit", [1, 2, 5, 17, 100, 299, 300])
def test_clamp_never_exceeds_limit(limit: int) -> None:
    text = "Hello there. " * 40 + "averyveryverylongwordwithoutspaces" * 5
    for start in range(0, 40, 7):
        assert len(clamp_message(text[start:], limit)) <= limit


def test_clamp_zero_limit() -> None:
    assert clamp_message("anything", 0) == ""


# --- PersonResult ----------------------------------------------------------------------


def test_person_result_clamps_long_messages() -> None:
    person = _person("Hi Jane, " + "word " * 200)
    assert 0 < len(person.connect_message) <= config.LINKEDIN_MESSAGE_MAX_CHARS


def test_person_result_respects_configured_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "LINKEDIN_MESSAGE_MAX_CHARS", 50)
    person = _person("Hi Jane, I would love to connect about your analytics team at Ramp.")
    assert len(person.connect_message) <= 50


def test_old_people_without_a_message_still_load() -> None:
    person = PersonResult.model_validate(
        {"name": "Jane", "title": "", "profile_url": "u", "alignment": "a"}
    )
    assert person.connect_message == ""


def test_llm_schema_requires_message_and_hides_key() -> None:
    schema = transform_schema(SearchResults)
    person = schema["$defs"]["PersonResult"]
    assert "connect_message" in person["properties"]
    assert "connect_message" in person["required"]
    assert "key" not in person["properties"]


# --- prompt and compile step -----------------------------------------------------------


def test_prompt_uses_configured_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "LINKEDIN_MESSAGE_MAX_CHARS", 200)
    text = prompts.linkedin_message_prompt()
    assert "connect_message" in text and "200 characters" in text
    assert "{" not in text
    assert prompts.compile_prompt().startswith(prompts.COMPILE_PROMPT)
    assert prompts.people_notes_prompt().startswith(prompts.PEOPLE_NOTES_PROMPT)
    assert "200 characters" in prompts.people_notes_prompt()


def test_compile_step_sends_linkedin_message_rules(scripted_model, monkeypatch) -> None:
    sources = FakeSources(monkeypatch)
    found = {c: sources.found(c, "data manager") for c in COMPANIES[:3]}
    model = scripted_model(
        structured={
            SearchPlan: plan(),
            CompanyRanking: RANKING,
            SearchResults: compiled(found),
        }
    )
    events = list(pipeline.run_search(REQUEST, llm=model))

    compile_call = model.structured_calls[-1]
    assert compile_call["schema"] is SearchResults
    system = compile_call["input"][0].content
    assert system == prompts.compile_prompt()
    assert f"{config.LINKEDIN_MESSAGE_MAX_CHARS} characters" in system
    assert events[-1].data.companies[0].people[0].connect_message.startswith("Hi Ramp")


# --- People page -----------------------------------------------------------------------


def _search(search_id: str, created_at: datetime, person: PersonResult) -> SavedSearch:
    return SavedSearch(
        id=search_id,
        title=search_id,
        created_at=created_at,
        user_id="TEST_USER",
        request=REQUEST,
        results=SearchResults(
            summary="s",
            companies=[
                CompanyResult(
                    name="Ramp", url="u", description="d", alignment="a", jobs=[], people=[person]
                )
            ],
        ),
    )


def test_people_page_carries_message_and_fills_from_older_search() -> None:
    now = datetime.now(UTC)
    old = _search("old", now - timedelta(days=1), _person("Hi Jane, let's connect."))
    new = _search("new", now, _person(""))  # e.g. the model left it blank this time
    [person] = catalog.people([old, new])
    assert person.connect_message == "Hi Jane, let's connect."


def test_people_page_without_any_message() -> None:
    [person] = catalog.people([_search("one", datetime.now(UTC), _person(""))])
    assert person.connect_message == ""
