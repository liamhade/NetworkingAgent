import json

import pytest

from schemas import PinUpdate, StatusUpdate
from userdata import pins, statuses

EMPTY = {"company": {}, "job": {}, "person": {}}


def test_set_and_get_round_trip(isolated_database) -> None:
    assert pins.get_pins("TEST_USER") == EMPTY
    pins.set_pin("TEST_USER", PinUpdate(kind="company", key="company:name:acme", pinned=True))
    pins.set_pin("TEST_USER", PinUpdate(kind="job", key="job:url:a.com/1", pinned=True))
    pins.set_pin("TEST_USER", PinUpdate(kind="person", key="person:linkedin:jane", pinned=True))
    stored = pins.set_pin("TEST_USER", PinUpdate(kind="job", key="job:url:a.com/1", pinned=False))
    assert stored.pinned is False

    assert pins.get_pins("TEST_USER") == {
        "company": {"company:name:acme": True},
        "job": {"job:url:a.com/1": False},
        "person": {"person:linkedin:jane": True},
    }
    path = isolated_database / "users" / "TEST_USER" / "pins.json"
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["company"]["company:name:acme"]["pinned"] is True
    assert "updated_at" in on_disk["company"]["company:name:acme"]
    # Pins are scoped per user.
    assert pins.get_pins("OTHER_USER") == EMPTY


def test_rejects_key_of_another_kind() -> None:
    with pytest.raises(pins.InvalidPinKey):
        pins.set_pin("TEST_USER", PinUpdate(kind="company", key="job:x", pinned=True))


def test_corrupt_file_is_treated_as_empty(isolated_database) -> None:
    folder = isolated_database / "users" / "TEST_USER"
    folder.mkdir(parents=True)
    (folder / "pins.json").write_text("[1, 2]", encoding="utf-8")
    assert pins.get_pins("TEST_USER") == EMPTY
    pins.set_pin("TEST_USER", PinUpdate(kind="person", key="person:x", pinned=True))
    assert pins.get_pins("TEST_USER")["person"] == {"person:x": True}


def test_pins_and_statuses_are_stored_separately() -> None:
    statuses.set_status("TEST_USER", StatusUpdate(kind="job", key="job:x", active=True))
    pins.set_pin("TEST_USER", PinUpdate(kind="job", key="job:x", pinned=True))
    pins.set_pin("TEST_USER", PinUpdate(kind="job", key="job:x", pinned=False))
    assert statuses.get_statuses("TEST_USER")["job"] == {"job:x": True}
    assert pins.get_pins("TEST_USER")["job"] == {"job:x": False}
