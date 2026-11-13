"""Fixtures for the read_page tests. No test may touch the network."""

import pytest
from rp_fakes import FakeWeb

import read_page
from read_page import browser, methods, registry
from read_page import fetch as fetch_mod


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch) -> FakeWeb:
    fake = FakeWeb()
    monkeypatch.setattr(fetch_mod, "fetch", fake.fetch)
    monkeypatch.setattr(fetch_mod, "get_json", fake.get_json)
    monkeypatch.setattr(browser, "render", fake.render)
    return fake


@pytest.fixture(autouse=True)
def clean_state(monkeypatch: pytest.MonkeyPatch):
    """Every test starts with empty caches, only the built-in rules, and no network."""

    def no_network(*args, **kwargs):
        raise AssertionError(f"Network access in a test: {args}")

    monkeypatch.setattr(fetch_mod.requests, "get", no_network)
    read_page.clear_cache()
    methods._ashby_cache.clear()
    registry.unregister_all()
    yield
    read_page.clear_cache()
    methods._ashby_cache.clear()
    registry.unregister_all()
