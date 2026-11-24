"""server.mount_frontend: the built frontend is served at `/`, after the API routes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

import server


def _app_with_api() -> FastAPI:
    app = FastAPI()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_serves_index_and_assets_and_keeps_api_routes(tmp_path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><p>app</p>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    app = _app_with_api()

    assert server.mount_frontend(app, tmp_path) is True
    client = TestClient(app)
    assert "app" in client.get("/").text
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/missing.js").status_code == 404


def test_without_a_build_nothing_is_mounted(tmp_path) -> None:
    app = _app_with_api()
    assert server.mount_frontend(app, tmp_path) is False
    assert TestClient(app).get("/").status_code == 404
