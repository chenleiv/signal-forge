"""The temporary X-Forwarded-For probe logs only a count, never addresses,
and is off unless XFF_COUNT_PROBE=1."""
import os
import pathlib
import subprocess
import sys

from fastapi.testclient import TestClient

import main

SECRET_IPS = ["198.51.100.23", "203.0.113.7"]
HEADERS = {"X-Forwarded-For": ", ".join(SECRET_IPS)}


def test_probe_is_off_by_default(capsys, monkeypatch):
    monkeypatch.setattr(main, "_XFF_PROBE_LEFT", 0)
    TestClient(main.app).get("/health", headers=HEADERS)
    assert "xff-probe" not in capsys.readouterr().out


def test_probe_logs_only_the_count(capsys, monkeypatch):
    monkeypatch.setattr(main, "_XFF_PROBE_LEFT", 5)
    TestClient(main.app).get("/health", headers=HEADERS)
    out = capsys.readouterr().out
    assert "X-Forwarded-For entries: 2" in out
    assert not any(ip in out for ip in SECRET_IPS)


def test_probe_stops_after_a_few_requests(capsys, monkeypatch):
    monkeypatch.setattr(main, "_XFF_PROBE_LEFT", 2)
    client = TestClient(main.app)
    for _ in range(4):
        client.get("/health", headers=HEADERS)
    assert capsys.readouterr().out.count("xff-probe") == 2


def test_probe_is_off_when_the_variable_is_unset_or_empty():
    backend = pathlib.Path(__file__).resolve().parents[1]
    for value in (None, "", "0", "true"):
        env = {k: v for k, v in os.environ.items() if k != "XFF_COUNT_PROBE"}
        env.update({"JWT_SECRET": "x", "DATABASE_URL": "", "DEMO_MODE": "true"})
        if value is not None:
            env["XFF_COUNT_PROBE"] = value
        r = subprocess.run([sys.executable, "-c", "import main; print(main._XFF_PROBE_LEFT)"],
                           cwd=backend, env=env, capture_output=True, text=True, timeout=60)
        assert r.stdout.strip().splitlines()[-1] == "0", (value, r.stderr[-500:])
