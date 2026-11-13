import json

import pytest

from schemas import StatusUpdate
from userdata import statuses


def test_set_and_get_round_trip(isolated_database) -> None:
    assert statuses.get_statuses("TEST_USER") == {"job": {}, "person": {}}
    statuses.set_status("TEST_USER", StatusUpdate(kind="job", key="job:url:a.com/1", active=True))
    statuses.set_status(
        "TEST_USER", StatusUpdate(kind="person", key="person:linkedin:jane", active=True)
    )
    statuses.set_status("TEST_USER", StatusUpdate(kind="job", key="job:url:a.com/2", active=True))
    stored = statuses.set_status(
        "TEST_USER", StatusUpdate(kind="job", key="job:url:a.com/2", active=False)
    )
    assert stored.active is False

    assert statuses.get_statuses("TEST_USER") == {
        "job": {"job:url:a.com/1": True, "job:url:a.com/2": False},
        "person": {"person:linkedin:jane": True},
    }
    path = isolated_database / "users" / "TEST_USER" / "statuses.json"
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["job"]["job:url:a.com/1"]["active"] is True
    assert "updated_at" in on_disk["job"]["job:url:a.com/1"]
    # Statuses are scoped per user.
    assert statuses.get_statuses("OTHER_USER") == {"job": {}, "person": {}}


def test_rejects_key_of_another_kind() -> None:
    with pytest.raises(statuses.InvalidStatusKey):
        statuses.set_status("TEST_USER", StatusUpdate(kind="job", key="person:x", active=True))


def test_corrupt_file_is_treated_as_empty(isolated_database) -> None:
    folder = isolated_database / "users" / "TEST_USER"
    folder.mkdir(parents=True)
    (folder / "statuses.json").write_text("{not json", encoding="utf-8")
    assert statuses.get_statuses("TEST_USER") == {"job": {}, "person": {}}
    statuses.set_status("TEST_USER", StatusUpdate(kind="job", key="job:x", active=True))
    assert statuses.get_statuses("TEST_USER")["job"] == {"job:x": True}
