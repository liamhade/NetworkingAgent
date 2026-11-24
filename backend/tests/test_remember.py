"""Saved resume + saved search parameters (temp DB, no LLM, no network)."""

import gzip

import pytest
from fastapi.testclient import TestClient
from pdf_utils import make_pdf

import pipeline
import resume
import server
from boards import default_config
from schemas import ResultEvent, ResumeProfile, SearchResults, StatusEvent

client = TestClient(server.app)
PROFILE = ResumeProfile(background="I am an analyst.", location="NYC", looking_for="Data roles")


@pytest.fixture(autouse=True)
def fake_parse(monkeypatch: pytest.MonkeyPatch):
    calls: list[int] = []

    def parse(data: bytes) -> ResumeProfile:
        calls.append(len(data))
        return PROFILE

    monkeypatch.setattr(resume, "parse_resume", parse)
    return calls


def upload(name: str, data: bytes):
    return client.post("/api/resume", files={"file": (name, data, "application/pdf")})


def test_no_saved_resume_by_default() -> None:
    assert client.get("/api/resume/saved").json() is None
    assert client.get("/api/resume/saved/file").status_code == 404
    assert client.delete("/api/resume/saved").status_code == 204


def test_upload_saves_compressed_and_round_trips(isolated_database, fake_parse) -> None:
    pdf = make_pdf([f"Line {i} of a long resume about analytics and SQL" for i in range(200)])
    assert upload("My CV.pdf", pdf).status_code == 200

    saved = client.get("/api/resume/saved").json()
    assert saved["filename"] == "My CV.pdf"
    assert saved["size"] == len(pdf)
    assert saved["stored_size"] < len(pdf)
    assert saved["uploaded_at"]
    assert saved["profile"] == PROFILE.model_dump()
    assert len(fake_parse) == 1  # Reading it back does not re-parse.

    on_disk = isolated_database / "users" / "TEST_USER" / "resume" / "resume.pdf.gz"
    assert on_disk.stat().st_size == saved["stored_size"]
    assert gzip.decompress(on_disk.read_bytes()) == pdf

    download = client.get("/api/resume/saved/file")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert 'filename="My CV.pdf"' in download.headers["content-disposition"]
    assert download.content == pdf  # Byte-identical.


def test_replace_keeps_only_latest(isolated_database) -> None:
    first, second = make_pdf(["first"]), make_pdf(["second", "resume"])
    upload("a.pdf", first)
    upload("b.pdf", second)
    assert client.get("/api/resume/saved").json()["filename"] == "b.pdf"
    assert client.get("/api/resume/saved/file").content == second
    folder = isolated_database / "users" / "TEST_USER" / "resume"
    assert sorted(p.name for p in folder.iterdir()) == ["resume.json", "resume.pdf.gz"]


def test_delete_removes_files(isolated_database) -> None:
    upload("a.pdf", make_pdf(["x"]))
    assert client.delete("/api/resume/saved").status_code == 204
    assert client.get("/api/resume/saved").json() is None
    assert client.get("/api/resume/saved/file").status_code == 404
    assert list((isolated_database / "users" / "TEST_USER" / "resume").iterdir()) == []


def test_non_pdf_and_unreadable_are_not_saved() -> None:
    assert (
        client.post("/api/resume", files={"file": ("a.txt", b"hi", "text/plain")}).status_code
        == 415
    )

    def bad(data: bytes):
        raise resume.ResumeError("unreadable")

    resume_parse = resume.parse_resume
    resume.parse_resume = bad
    try:
        assert upload("a.pdf", b"garbage").status_code == 422
    finally:
        resume.parse_resume = resume_parse
    assert client.get("/api/resume/saved").json() is None


def test_corrupt_saved_files_read_as_missing(isolated_database) -> None:
    upload("a.pdf", make_pdf(["x"]))
    folder = isolated_database / "users" / "TEST_USER" / "resume"
    (folder / "resume.json").write_text("{nope", encoding="utf-8")
    assert client.get("/api/resume/saved").json() is None
    assert client.get("/api/resume/saved/file").status_code == 404


def test_params_default_null_and_round_trip(isolated_database) -> None:
    assert client.get("/api/search/params").json() is None
    body = {
        "background": "Analyst",
        "location": "NYC",
        "looking_for": "Data roles",
        "boards": {"greenhouse": {"enabled": False, "max_jobs": 3}},
    }
    put = client.put("/api/search/params", json=body)
    assert put.status_code == 200
    got = client.get("/api/search/params").json()
    assert got == put.json()
    assert got["background"] == "Analyst"
    assert got["boards"]["greenhouse"] == {"enabled": False, "max_jobs": 3}
    assert set(got["boards"]) == set(default_config())  # Normalized to every board.
    assert (isolated_database / "users" / "TEST_USER" / "search_params.json").is_file()


def test_params_normalize_boards_and_allow_drafts() -> None:
    body = {
        "boards": {"nope": {"enabled": True}, "greenhouse": {"enabled": True, "max_jobs": 10**6}}
    }
    got = client.put("/api/search/params", json=body).json()
    assert got["background"] == "" and got["looking_for"] == ""
    assert "nope" not in got["boards"]
    assert got["boards"]["greenhouse"]["max_jobs"] < 10**6


def test_params_validation() -> None:
    assert client.put("/api/search/params", json={"location": "x" * 201}).status_code == 422
    assert client.put("/api/search/params", json={"background": "x" * 20_001}).status_code == 422


def test_corrupt_params_read_as_none(isolated_database) -> None:
    client.put("/api/search/params", json={"background": "a"})
    path = isolated_database / "users" / "TEST_USER" / "search_params.json"
    path.write_text("[1", encoding="utf-8")
    assert client.get("/api/search/params").json() is None


def test_search_submit_saves_params(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_search(request):
        yield StatusEvent(message="Working")
        yield ResultEvent(data=SearchResults(summary="ok", companies=[]))

    monkeypatch.setattr(pipeline, "run_search", fake_run_search)
    body = {"background": "Analyst", "location": "NYC", "looking_for": "Data roles"}
    with client.stream("POST", "/api/search", json=body) as response:
        list(response.iter_lines())
    got = client.get("/api/search/params").json()
    assert {k: got[k] for k in body} == body
    assert got["boards"] == {k: v.model_dump() for k, v in default_config().items()}
