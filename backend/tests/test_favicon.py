"""Icons are served as images, never as the SPA's index.html.

main.spa_response sets the media type of .ico, .png and .svg explicitly (the
system mime database on Linux can name .ico differently), and answers a
missing .ico, .png or .svg outside the API prefixes with 404. Everything
else (client-side routes, API paths, other missing files) is unchanged.

The first group runs on a small fake build in a temp directory, so it runs in
CI's backend job too. The second group needs the real frontend build in
backend/static, like test_og_preview.py, and skips without one; the e2e job
checks the same over HTTP (frontend/e2e/favicon.e2e.ts)."""
from __future__ import annotations

import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import main
from security_headers import API_CSP, COMMON_HEADERS, SPA_CSP, SecurityHeadersMiddleware

INDEX = b"<!doctype html><html><body><app-root></app-root></body></html>"
ICO = b"\x00\x00\x01\x00\x01\x00" + b"\x00" * 16
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"></svg>'
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
GET_HEAD = ("GET", "HEAD")


@pytest.fixture
def fake_build(tmp_path: pathlib.Path) -> TestClient:
    (tmp_path / "index.html").write_bytes(INDEX)
    (tmp_path / "favicon.ico").write_bytes(ICO)
    (tmp_path / "favicon.svg").write_bytes(SVG)
    (tmp_path / "apple-touch-icon.png").write_bytes(PNG)
    (tmp_path / "main.js").write_bytes(b"console.log(1)")

    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def spa(full_path: str):
        return main.spa_response(tmp_path, full_path)

    return TestClient(app)


def _assert_spa_headers(r) -> None:
    for name, value in COMMON_HEADERS.items():
        assert r.headers.get(name) == value, name
    assert r.headers["Content-Security-Policy"] == SPA_CSP
    assert "no-store" not in r.headers.get("Cache-Control", "")


@pytest.mark.parametrize("method", GET_HEAD)
@pytest.mark.parametrize("path, media_type, body", [
    ("/favicon.ico", "image/x-icon", ICO),
    ("/favicon.svg", "image/svg+xml", SVG),
    ("/apple-touch-icon.png", "image/png", PNG),
])
def test_icon_has_its_image_type(fake_build, method, path, media_type, body):
    r = fake_build.request(method, path)
    assert r.status_code == 200
    assert r.headers["content-type"] == media_type
    assert int(r.headers["content-length"]) == len(body)
    if method == "GET":
        assert r.content == body
    _assert_spa_headers(r)


@pytest.mark.parametrize("method", GET_HEAD)
@pytest.mark.parametrize("path", [
    "/apple-touch-icon-precomposed.png",
    "/missing.ico",
    "/assets/MISSING.SVG",
])
def test_missing_icon_is_404_not_the_spa(fake_build, method, path):
    r = fake_build.request(method, path)
    assert r.status_code == 404
    assert not r.headers.get("content-type", "").startswith("text/html")
    assert b"<html" not in r.content
    _assert_spa_headers(r)


@pytest.mark.parametrize("path", ["/", "/dashboard", "/incidents/INC-1/tasks/deep/route"])
def test_spa_routes_still_get_index(fake_build, path):
    r = fake_build.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.content == INDEX
    _assert_spa_headers(r)


@pytest.mark.parametrize("path", [
    "/missing.js",              # only image types get 404
    "/api/missing.png",         # API prefixes keep the old behavior
    "/auth/missing.ico",
])
def test_other_missing_paths_are_unchanged(fake_build, path):
    r = fake_build.get(path)
    assert r.status_code == 200
    assert r.content == INDEX


def test_traversal_falls_back_to_index_as_before(tmp_path):
    # Called directly: HTTP clients normalize "/../" before sending.
    root = tmp_path / "static"
    root.mkdir()
    (root / "index.html").write_bytes(INDEX)
    (tmp_path / "secret.png").write_bytes(PNG)
    for path in ("../secret.png", "../missing.ico"):
        r = main.spa_response(root, path)
        assert pathlib.Path(r.path) == (root / "index.html").resolve()


def test_other_files_keep_the_guessed_type(fake_build):
    r = fake_build.get("/main.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"]


# The real app: unknown API paths behave as before this change (the SPA when
# a build exists, FastAPI's JSON 404 without one), with the API headers.

@pytest.mark.parametrize("path", ["/api/does-not-exist", "/api/does-not-exist.png"])
def test_unknown_api_path_is_unchanged(path):
    r = TestClient(main.app).get(path)
    if main._static.exists():
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
    else:
        assert r.status_code == 404
        assert r.json() == {"detail": "Not Found"}
    assert r.headers["Content-Security-Policy"] == API_CSP
    assert r.headers["Cache-Control"] == "no-store"


built = pytest.mark.skipif(
    not (main._static / "index.html").is_file(), reason="no frontend build in backend/static"
)


@built
@pytest.mark.parametrize("method", GET_HEAD)
@pytest.mark.parametrize("path, media_type, magic", [
    ("/favicon.ico", "image/x-icon", b"\x00\x00\x01\x00"),
    ("/favicon.svg", "image/svg+xml", b"<svg"),
    ("/apple-touch-icon.png", "image/png", b"\x89PNG\r\n\x1a\n"),
])
def test_built_icons_are_served_as_images(method, path, media_type, magic):
    if not (main._static / path.lstrip("/")).is_file():
        pytest.skip(f"build in backend/static predates {path}")
    client = TestClient(main.app)
    r = client.request(method, path)
    assert r.status_code == 200
    assert r.headers["content-type"] == media_type
    _assert_spa_headers(r)
    if method == "GET":
        assert r.content.startswith(magic)
        assert b"<html" not in r.content.lower()


@built
def test_built_deep_spa_route_is_unchanged():
    r = TestClient(main.app).get("/incidents/INC-1/tasks/deep/route")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "<app-root>" in r.text
    _assert_spa_headers(r)


@built
def test_built_missing_touch_icon_is_404():
    r = TestClient(main.app).get("/apple-touch-icon-precomposed.png")
    assert r.status_code == 404
    _assert_spa_headers(r)
