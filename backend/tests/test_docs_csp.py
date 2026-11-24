"""The CSP is skipped only for the exact API docs paths, and only while the
docs are served (ENABLE_API_DOCS=true). With the docs off those paths fall
through to the SPA and must get its CSP like any other page."""
from __future__ import annotations
import os
import pathlib
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

import main
from security_headers import SPA_CSP, SecurityHeadersMiddleware

BACKEND = pathlib.Path(__file__).resolve().parents[1]
DOCS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})


@pytest.mark.parametrize("path", ["/docs", "/docs/oauth2-redirect", "/redoc", "/docsx", "/redoc/x", "/docs/"])
def test_docs_paths_get_the_spa_csp_when_docs_are_off(path):
    r = TestClient(main.app).get(path)
    assert r.headers["Content-Security-Policy"] == SPA_CSP


def _app(docs_paths: frozenset[str]) -> TestClient:
    async def page(request):
        return PlainTextResponse("page")
    inner = Starlette(routes=[Route("/{path:path}", page)])
    return TestClient(SecurityHeadersMiddleware(inner, docs_paths=docs_paths))


@pytest.mark.parametrize("path", sorted(DOCS))
def test_exact_docs_paths_skip_the_csp_when_docs_are_on(path):
    assert "Content-Security-Policy" not in _app(DOCS).get(path).headers


@pytest.mark.parametrize("path", ["/docsx", "/docs/", "/docs/other", "/redoc/x", "/redocx", "/openapi.json"])
def test_other_paths_keep_the_csp_when_docs_are_on(path):
    assert _app(DOCS).get(path).headers["Content-Security-Policy"] == SPA_CSP


def test_no_docs_paths_means_no_path_skips_the_csp():
    for path in sorted(DOCS):
        assert _app(frozenset()).get(path).headers["Content-Security-Policy"] == SPA_CSP


def _wired_docs_paths(value: str) -> list[str]:
    env = {**os.environ, "ENABLE_API_DOCS": value, "PYTHONPATH": str(BACKEND)}
    probe = (
        "import main\n"
        "from security_headers import SecurityHeadersMiddleware\n"
        "m = [m for m in main.app.user_middleware if m.cls is SecurityHeadersMiddleware][0]\n"
        "print(','.join(sorted(m.kwargs['docs_paths'])) or '-')\n"
    )
    r = subprocess.run([sys.executable, "-c", probe], cwd=BACKEND / "tests", env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1].split(",")


def test_main_passes_the_exact_docs_paths_only_when_docs_are_on():
    assert _wired_docs_paths("true") == ["/docs", "/docs/oauth2-redirect", "/redoc"]
    assert _wired_docs_paths("") == ["-"]
