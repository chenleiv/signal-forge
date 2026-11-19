"""The WebSocket message size limit comes from uvicorn, not the app: the
start command passes --ws-max-size (Render, e2e/serve.mjs). This runs a real
uvicorn with that flag and checks the behaviour we rely on, so an upgrade or
a change of WebSocket implementation that stops enforcing it fails here.

It does not prove the deployed start command has the flag; see README,
Deployment checklist."""
from __future__ import annotations

import os
import pathlib
import socket
import subprocess
import sys
import time

import httpx
import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

BACKEND = pathlib.Path(__file__).resolve().parent.parent
# Same value as e2e/serve.mjs and the Render start command.
WS_MAX_SIZE = 8192


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server_url(tmp_path_factory):
    port = _free_port()
    env = {
        **os.environ,   # conftest already isolates DATABASE_URL, API keys, DEMO_MODE, JWT_SECRET
        "THREAT_IPS_CACHE": str(tmp_path_factory.mktemp("feed") / "none.json"),
        "ENABLE_API_DOCS": "",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port),
         "--ws-max-size", str(WS_MAX_SIZE), "--log-level", "warning"],
        cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 15
        while True:
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline or proc.poll() is not None:
                pytest.fail("uvicorn did not start")
            time.sleep(0.1)
        yield f"ws://127.0.0.1:{port}/ws/threats"
    finally:
        proc.terminate()
        proc.wait(10)


def _close_code_after_sending(url: str, message: str, compression: str | None) -> int | None:
    with connect(url, compression=compression, max_size=None, open_timeout=5) as ws:
        try:
            ws.send(message)
            ws.recv(timeout=5)
        except ConnectionClosed:
            pass
        except TimeoutError:
            return None
        return ws.protocol.close_code


def test_first_frame_over_the_limit_closes_with_1009(server_url):
    assert _close_code_after_sending(server_url, "x" * (WS_MAX_SIZE * 2), None) == 1009


def test_compressed_frame_is_limited_by_its_decompressed_size(server_url):
    """About 100 bytes on the wire, 2 MiB once inflated: still 1009."""
    assert _close_code_after_sending(server_url, "a" * (2 * 1024 * 1024), "deflate") == 1009


def test_frame_within_the_limit_reaches_the_app(server_url):
    """A ticket-sized (invalid) first message gets the app's own answer."""
    assert _close_code_after_sending(server_url, '{"type": "auth", "ticket": "not-a-jwt"}', None) == 4001
