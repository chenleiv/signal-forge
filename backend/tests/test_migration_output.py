"""A failed migration prints one short line, not Alembic's whole traceback,
and still stops startup."""
from __future__ import annotations
from types import SimpleNamespace

import pytest

import main

TRACEBACK = """\
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
Traceback (most recent call last):
  File "/app/venv/lib/python3.13/site-packages/sqlalchemy/engine/base.py", line 1967, in _exec_single_context
    self.dialect.do_execute(
asyncpg.exceptions.UndefinedColumnError: column "secret_col" does not exist

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/app/backend/alembic/versions/009_x.py", line 12, in upgrade
sqlalchemy.exc.ProgrammingError: (asyncpg.exceptions.UndefinedColumnError) column "secret_col" does not exist
[SQL: UPDATE users SET password_hash = $1 WHERE username = $2]
[parameters: ('$2b$12$abcdefghijklmnopqrstuv', 'admin')]
(Background on this error at: https://sqlalche.me/e/20/f405)
"""


def test_the_summary_is_the_last_exception_line():
    assert main._migration_error_summary(TRACEBACK) == (
        'sqlalchemy.exc.ProgrammingError: (asyncpg.exceptions.UndefinedColumnError) column "secret_col" does not exist'
    )


@pytest.mark.parametrize("stderr, expected", [
    ("", "no error output"),
    ("\n  \n", "no error output"),
    ("just one line\n", "just one line"),
    ("first\nlast line, no exception name\n", "last line, no exception name"),
])
def test_the_summary_falls_back_to_the_last_line(stderr, expected):
    assert main._migration_error_summary(stderr) == expected


def test_the_summary_is_capped():
    summary = main._migration_error_summary("RuntimeError: " + "x" * 5000)
    assert len(summary) == main.MIGRATION_ERROR_MAX_CHARS + 3
    assert summary.endswith("...")


def test_url_credentials_are_masked():
    line = "sqlalchemy.exc.OperationalError: cannot reach postgresql+asyncpg://sf_user:hunter2-pw@db.internal:5432/sf"
    summary = main._migration_error_summary(line)
    assert "hunter2-pw" not in summary and "sf_user" not in summary
    assert "postgresql+asyncpg://***@db.internal:5432/sf" in summary


def test_a_failed_migration_prints_one_short_line_and_stops(monkeypatch, capsys):
    monkeypatch.setattr(main.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=1, stderr=TRACEBACK))
    with pytest.raises(RuntimeError, match="migration failed"):
        main._run_migrations()
    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert out.startswith("[Alembic] Migration failed: sqlalchemy.exc.ProgrammingError:")
    for leaked in ("Traceback", "[SQL:", "[parameters:", "$2b$12$", "/app/"):
        assert leaked not in out
