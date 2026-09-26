"""backend/.env.example must list every variable the backend reads, and a
copy of it with only JWT_SECRET filled in must start the app with sane
defaults (empty values mean "unset", never a crash or an empty setting)."""
from __future__ import annotations
import json
import os
import pathlib
import re
import subprocess
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = BACKEND / ".env.example"


def _example_vars() -> dict[str, str]:
    pairs = (line.split("=", 1) for line in EXAMPLE.read_text().splitlines()
             if line and not line.startswith("#"))
    return {k.strip(): v.strip() for k, v in pairs}


def test_every_variable_read_by_the_backend_is_in_the_example():
    sources = [*BACKEND.glob("*.py"), *BACKEND.glob("routers/*.py")]
    used = set()
    for path in sources:
        used |= set(re.findall(r'os\.(?:environ\.get|getenv)\(\s*"([A-Z_]+)"', path.read_text()))
    assert used, "found no environment variables: the pattern is wrong"
    assert used <= set(_example_vars()), f"missing from .env.example: {sorted(used - set(_example_vars()))}"


def test_example_values_are_empty():
    """No real or default secrets in a committed file."""
    assert all(v == "" for v in _example_vars().values())


def test_app_starts_from_the_example_with_only_jwt_secret():
    env = {k: v for k, v in os.environ.items() if k not in _example_vars()}
    env.update(_example_vars())
    env["JWT_SECRET"] = "example-secret"
    probe = (
        "import json, main, rate_limit, store; from routers import ip; "
        "print(json.dumps({'hops': rate_limit.TRUSTED_PROXY_HOPS, 'model': ip.GROQ_MODEL, "
        "'demo': store.DEMO_MODE}))"
    )
    # cwd without a .env file, so load_dotenv adds nothing on top of the example.
    r = subprocess.run([sys.executable, "-c", probe], cwd=BACKEND / "tests", env={**env, "PYTHONPATH": str(BACKEND)},
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-2000:]
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out == {"hops": 1, "model": "openai/gpt-oss-20b", "demo": True}
