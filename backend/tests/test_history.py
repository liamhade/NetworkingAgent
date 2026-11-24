import json
from datetime import timedelta

import pytest

from schemas import CompanyResult, SearchRequest, SearchResults
from userdata import accounts, history


def _request(looking_for: str, location: str = "") -> SearchRequest:
    return SearchRequest(background="Analyst", location=location, looking_for=looking_for)


def test_make_title_strips_filler_and_adds_location() -> None:
    title = history.make_title(_request("I'm looking for data analyst roles. Remote ok.", "NYC"))
    assert title == "Data analyst roles · NYC"


def test_make_title_truncates_on_word_boundary() -> None:
    title = history.make_title(
        _request("Senior machine learning engineering positions at climate tech startups")
    )
    assert title.endswith("…")
    assert len(title) <= history.TITLE_MAX_CHARS + 1
    assert title.startswith("Senior machine learning")


def test_make_title_falls_back_when_only_filler() -> None:
    assert history.make_title(_request("looking for")) == "Search"


def test_save_list_and_get_round_trip(isolated_database) -> None:
    results = SearchResults(
        summary="s",
        companies=[
            CompanyResult(name="Acme", url="u", description="d", alignment="a", jobs=[], people=[])
        ],
    )
    first = history.save_search("TEST_USER", _request("Data roles"), results)
    second = history.save_search("TEST_USER", _request("PM roles"), results)

    path = isolated_database / "users" / "TEST_USER" / "searches" / f"{first.id}.json"
    assert json.loads(path.read_text(encoding="utf-8"))["title"] == "Data roles"

    # Force a deterministic order: make `first` the newer one.
    newer = first.model_copy(update={"created_at": second.created_at + timedelta(seconds=5)})
    path.write_text(newer.model_dump_json(), encoding="utf-8")

    listed = history.list_searches("TEST_USER")
    assert [summary.id for summary in listed] == [first.id, second.id]
    assert history.get_search("TEST_USER", second.id) == second
    # Searches are scoped per user.
    assert history.list_searches("OTHER_USER") == []
    assert history.get_search("OTHER_USER", second.id) is None


def test_list_skips_corrupt_files_and_missing_dir(isolated_database) -> None:
    assert history.list_searches("TEST_USER") == []
    folder = isolated_database / "users" / "TEST_USER" / "searches"
    folder.mkdir(parents=True)
    (folder / "broken.json").write_text("{not json", encoding="utf-8")
    assert history.list_searches("TEST_USER") == []


def test_get_search_rejects_bad_ids() -> None:
    assert history.get_search("TEST_USER", "../../etc/passwd") is None
    assert history.get_search("TEST_USER", "f" * 32) is None


def test_get_current_user_seeds_test_user(isolated_database) -> None:
    user = accounts.get_current_user()
    assert user.id == "TEST_USER"
    assert user.display_name == "Test User"
    assert (isolated_database / "users" / "TEST_USER" / "user.json").is_file()
    assert accounts.get_current_user() == user  # Created once, then reused.


def test_user_dir_rejects_path_traversal() -> None:
    with pytest.raises(ValueError):
        accounts.user_dir("../evil")
