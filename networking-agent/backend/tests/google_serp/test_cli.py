import json

from google_serp import cli
from google_serp.models import SearchMetadata, SearchResponse, SearchResult


class FakeSession:
    """Stands in for GoogleSerpSession so the CLI can be tested without Chrome."""

    instances = []

    def __init__(self, profile_dir=None, hidden=True):
        self.kwargs = {"profile_dir": profile_dir, "hidden": hidden}
        self.calls = []
        FakeSession.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def search(self, query, resolve_urls=True, page=1):
        self.calls.append((query, resolve_urls, page))
        return SearchResponse(
            results=[SearchResult(title="T", url="https://x.org", position=1)],
            metadata=SearchMetadata(query=query, results_count="About 1 result", page=page),
        )


def test_json_output(monkeypatch, capsys):
    FakeSession.instances.clear()
    monkeypatch.setattr(cli, "GoogleSerpSession", FakeSession)
    assert cli.main(["a b", "c", "--json", "--no-resolve", "--show-window"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert [d["metadata"]["query"] for d in data] == ["a b", "c"]
    session = FakeSession.instances[0]
    assert session.calls == [("a b", False, 1), ("c", False, 1)]
    assert session.kwargs["hidden"] is False


def test_pagination(monkeypatch, capsys):
    FakeSession.instances.clear()
    monkeypatch.setattr(cli, "GoogleSerpSession", FakeSession)
    assert cli.main(["q", "--json", "--page", "2", "--pages", "3"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert [d["metadata"]["page"] for d in data] == [2, 3, 4]
    assert [c[2] for c in FakeSession.instances[0].calls] == [2, 3, 4]


def test_invalid_page(monkeypatch):
    monkeypatch.setattr(cli, "GoogleSerpSession", FakeSession)
    import pytest

    with pytest.raises(SystemExit):
        cli.main(["q", "--page", "0"])


def test_text_output(monkeypatch, capsys):
    monkeypatch.setattr(cli, "GoogleSerpSession", FakeSession)
    assert cli.main(["q"]) == 0
    out = capsys.readouterr().out
    assert "1. T" in out and "https://x.org" in out
