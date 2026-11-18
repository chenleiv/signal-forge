"""Console commands on POST /api/command: only the allowed ones run.

"clear" is handled by the console in the browser and is not a server
command, so the server answers it like any other unknown command."""
from __future__ import annotations

import pytest

from tests.conftest import session_client


@pytest.fixture
def alice():
    return session_client("alice", "analyst")


def _console(client, command: str) -> str:
    r = client.post("/api/command", json={"command": command})
    assert r.status_code == 200
    return r.json()["output"]


@pytest.mark.parametrize("command", ["clear", "CLEAR", "  clear  "])
def test_clear_is_rejected_like_an_unknown_command(alice, command):
    unknown = _console(alice, "frobnicate")
    assert unknown == "Unknown command: 'frobnicate'. Type 'help' for available commands."

    assert _console(alice, command) == "Unknown command: 'clear'. Type 'help' for available commands."


def test_help_still_lists_clear_for_the_console(alice):
    assert _console(alice, "help").endswith("| clear")
