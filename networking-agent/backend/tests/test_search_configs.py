"""Saved search configurations (temp DB, no network)."""

import json

from fastapi.testclient import TestClient

import server
from boards import default_config

client = TestClient(server.app)
PARAMS = {"background": "Analyst", "location": "NYC", "looking_for": "Data roles"}


def create(name: str | None = None, **params):
    body: dict = {"params": {**PARAMS, **params}}
    if name is not None:
        body["name"] = name
    return client.post("/api/search/configs", json=body)


def names() -> list[str]:
    return [c["name"] for c in client.get("/api/search/configs").json()]


def test_empty_by_default() -> None:
    assert client.get("/api/search/configs").json() == []


def test_crud_round_trip(isolated_database) -> None:
    created = create("Fintech").json()
    assert created["name"] == "Fintech"
    assert created["params"]["background"] == "Analyst"
    assert created["created_at"] and created["updated_at"]

    assert client.get("/api/search/configs").json() == [created]
    stored = isolated_database / "users" / "TEST_USER" / "search_configs.json"
    assert json.loads(stored.read_text(encoding="utf-8"))["configs"][0]["id"] == created["id"]

    renamed = client.patch(f"/api/search/configs/{created['id']}", json={"name": "  Climate  "})
    assert renamed.json()["name"] == "Climate"
    assert renamed.json()["params"] == created["params"]

    overwritten = client.patch(
        f"/api/search/configs/{created['id']}",
        json={"params": {**PARAMS, "location": "Boston"}},
    ).json()
    assert overwritten["params"]["location"] == "Boston"
    assert overwritten["name"] == "Climate"
    assert overwritten["created_at"] == created["created_at"]

    assert client.delete(f"/api/search/configs/{created['id']}").status_code == 204
    assert names() == []


def test_default_names_are_never_reused() -> None:
    ids = [create().json()["id"] for _ in range(3)]
    assert names() == [f"Search Configuration #{n}" for n in (1, 2, 3)]
    client.delete(f"/api/search/configs/{ids[1]}")
    assert create().json()["name"] == "Search Configuration #4"
    client.delete(f"/api/search/configs/{ids[2]}")  # Not the highest: #4 remains.
    assert create().json()["name"] == "Search Configuration #5"


def test_highest_deleted_number_is_not_reused() -> None:
    first = create().json()
    second = create().json()
    client.delete(f"/api/search/configs/{second['id']}")
    client.delete(f"/api/search/configs/{first['id']}")
    assert create().json()["name"] == "Search Configuration #3"


def test_custom_names_do_not_affect_numbering_but_renamed_defaults_count() -> None:
    create("Mine")
    assert create().json()["name"] == "Search Configuration #1"
    created = create("Search Configuration #7").json()
    assert create().json()["name"] == "Search Configuration #8"
    client.patch(f"/api/search/configs/{created['id']}", json={"name": "Other"})
    assert create().json()["name"] == "Search Configuration #9"


def test_name_validation() -> None:
    assert create("   ").status_code == 422
    assert create("x" * 81).status_code == 422
    assert create("x" * 80).status_code == 201
    config_id = create("Ok").json()["id"]
    assert client.patch(f"/api/search/configs/{config_id}", json={"name": ""}).status_code == 422
    long = client.patch(f"/api/search/configs/{config_id}", json={"name": "y" * 81})
    assert long.status_code == 422
    assert names()[-1] == "Ok"


def test_blank_name_is_rejected_not_defaulted() -> None:
    assert create("").status_code == 422
    assert names() == []


def test_boards_are_normalized_on_save() -> None:
    saved = create(boards={"greenhouse": {"enabled": True, "max_jobs": 99999}, "bogus": {}}).json()
    boards = saved["params"]["boards"]
    assert "bogus" not in boards
    assert set(boards) == set(default_config())
    assert boards["greenhouse"]["max_jobs"] <= 99999
    assert client.get("/api/search/configs").json()[0]["params"]["boards"] == boards

    missing = create().json()
    assert missing["params"]["boards"] == {
        key: dict(value) for key, value in default_config().items()
    }


def test_empty_text_fields_are_allowed() -> None:
    saved = client.post("/api/search/configs", json={"params": {}})
    assert saved.status_code == 201
    assert saved.json()["params"]["background"] == ""


def test_unknown_ids_are_404() -> None:
    assert client.patch("/api/search/configs/nope", json={"name": "x"}).status_code == 404
    assert client.delete("/api/search/configs/nope").status_code == 404


def test_corrupt_file_reads_as_empty(isolated_database) -> None:
    path = isolated_database / "users" / "TEST_USER" / "search_configs.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    assert client.get("/api/search/configs").json() == []
    assert create().json()["name"] == "Search Configuration #1"
