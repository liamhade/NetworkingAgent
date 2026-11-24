"""config: environment values arrive unquoted whatever set them."""

import os

import pytest

import config


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('"sk-abc"', "sk-abc"),  # docker --env-file keeps dotenv-style quotes
        ("'sk-abc'", "sk-abc"),
        (' "sk-abc" ', "sk-abc"),
        ("sk-abc", "sk-abc"),
        ('"sk-abc', '"sk-abc'),  # unmatched: left alone
        ('a "b" c', 'a "b" c'),
    ],
)
def test_unquote_environment(monkeypatch: pytest.MonkeyPatch, raw: str, expected: str) -> None:
    monkeypatch.setenv("NA_TEST_SECRET", raw)
    config._unquote_environment()
    assert os.environ["NA_TEST_SECRET"] == expected
