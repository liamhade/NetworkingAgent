"""Page-reading helpers shared by the posting steps."""

import config
from pipeline import steps


def test_posting_excerpt_jumps_to_requirements() -> None:
    text = "About us. " * 200 + "\n## Requirements\n- 4+ years of Go\n"
    excerpt = steps.posting_excerpt(text, 600)
    assert len(excerpt) <= 600
    assert "4+ years of Go" in excerpt
    assert excerpt.startswith("About us.")


def test_read_pages_skips_pages_slower_than_the_timeout(monkeypatch) -> None:
    import threading

    from read_page import PageResult

    release = threading.Event()

    def fake_read(url: str, max_chars: int = 0) -> PageResult:
        if "slow" in url:
            release.wait(5)
        return PageResult(url=url, final_url=url, method="static", markdown=f"Text {url}")

    monkeypatch.setattr(config, "READ_TIMEOUT_S", 0.3)
    monkeypatch.setattr(steps.tools, "read_page", fake_read)
    try:
        pages, trace = steps.read_pages("read_postings", ["https://a/fast", "https://a/slow"], 100)
    finally:
        release.set()
    assert pages == {"https://a/fast": "Text https://a/fast"}
    slow = next(t for t in trace if t.args["url"] == "https://a/slow")
    assert slow.error.startswith("Timeout")
