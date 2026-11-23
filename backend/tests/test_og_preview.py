"""Link-preview crawlers (LinkedIn, Slack, X) fetch / and /og-image.png
without running JavaScript, without cookies, and many times from one address.
These checks need a frontend build in backend/static, like the built-index
checks in test_security_headers.py; they skip without one."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
from security_headers import COMMON_HEADERS, SPA_CSP

CRAWLER_UA = "LinkedInBot/1.0 (compatible; Mozilla/5.0; Apache-HttpClient +http://www.linkedin.com)"

pytestmark = pytest.mark.skipif(
    not (main._static / "index.html").is_file(), reason="no frontend build in backend/static"
)


@pytest.fixture
def client():
    return TestClient(main.app, headers={"User-Agent": CRAWLER_UA})


def test_root_has_the_preview_tags(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    for key in ("og:title", "og:description", "og:image", "og:url", "twitter:card", "twitter:image"):
        assert key in r.text, key


def test_head_root_is_allowed(client):
    r = client.head("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_image_is_served_as_png_not_the_spa(client):
    if not (main._static / "og-image.png").is_file():
        pytest.skip("build in backend/static predates og-image.png")
    for method in (client.get, client.head):
        r = method("/og-image.png")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        # nosniff is fine as long as the type is right; the headers stay on.
        for name, value in COMMON_HEADERS.items():
            assert r.headers.get(name) == value, name
        assert r.headers["Content-Security-Policy"] == SPA_CSP
    assert client.get("/og-image.png").content[:8] == b"\x89PNG\r\n\x1a\n"


def test_repeated_crawler_fetches_are_not_rate_limited(client):
    # Per-IP limits are keyed on the client address; the SPA and its static
    # files carry no limit, so one crawler address can fetch them repeatedly.
    headers = {"X-Forwarded-For": "203.0.113.50"}
    for _ in range(60):
        assert client.get("/", headers=headers).status_code == 200
    for _ in range(60):
        assert client.get("/og-image.png", headers=headers).status_code == 200
