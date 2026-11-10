"""Startup with a database: it must never destroy stored data, and it must not
serve requests after a failed migration."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import main
import store
from database import Base
from models import Incident, Note


class StartupDb:
    """A real SQLite database wired into main.lifespan, with the side effects
    that reach outside this test (user sync, threat feed) replaced."""

    def __init__(self, make_session):
        self.make_session = make_session
        self.migration_exit_code = 0
        self.migration_commands: list[list[str]] = []
        self.user_syncs = 0

    def run(self, fn):
        async def wrapper():
            async with self.make_session() as session:
                return await fn(session)
        return asyncio.run(wrapper())

    def seed(self, incident_ids: list[str]) -> None:
        async def insert(session: AsyncSession) -> None:
            now = datetime.now(timezone.utc)
            for incident_id in incident_ids:
                session.add(Incident(
                    id=incident_id, title="Analyst case", status="open", severity="high",
                    attack_type="SQLi", event_count=1, mitre_tags="[]", created_at=now, updated_at=now,
                ))
            await session.flush()
            session.add(Note(id="note-1", incident_id=incident_ids[0], text="keep me", author="alice", created_at=now))
            await session.commit()
        self.run(insert)

    def count(self, model) -> int:
        async def query(session: AsyncSession) -> int:
            return (await session.execute(select(func.count()).select_from(model))).scalar_one()
        return self.run(query)


@pytest.fixture
def startup_db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'startup.db'}")
    make_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(create())

    db = StartupDb(make_session)

    def fake_subprocess_run(command, **_):
        db.migration_commands.append(command)
        return SimpleNamespace(returncode=db.migration_exit_code, stderr="migration error")

    async def fake_sync_users(*_) -> None:
        db.user_syncs += 1

    async def noop(*_, **__) -> None:
        return None

    monkeypatch.setattr(main, "USE_DB", True)
    monkeypatch.setattr(main, "AsyncSessionLocal", make_session)
    monkeypatch.setattr(main.subprocess, "run", fake_subprocess_run)
    monkeypatch.setattr(main, "sync_users_with_db", fake_sync_users)
    monkeypatch.setattr(main, "load_revoked_sessions", noop)
    monkeypatch.setattr(main, "refresh_threat_ips", noop)
    # Startup overwrites these in place; give it copies so other tests are unaffected.
    monkeypatch.setattr(store, "_rules", list(store._rules))
    monkeypatch.setattr(store, "_behavioral_config", dict(store._behavioral_config))
    monkeypatch.setattr(store, "_incident_counter", store._incident_counter)

    yield db
    asyncio.run(engine.dispose())


@pytest.mark.parametrize("demo_mode", [False, True])
def test_startup_keeps_every_incident_and_note(startup_db, monkeypatch, demo_mode):
    monkeypatch.setattr(main, "DEMO_MODE", demo_mode)
    startup_db.seed([f"INC-{1000 + n}" for n in range(1, 61)])

    with TestClient(main.app):
        pass

    assert startup_db.count(Incident) == 60
    assert startup_db.count(Note) == 1


def test_failed_migration_stops_startup_before_any_database_work(startup_db):
    startup_db.seed(["INC-1001"])
    startup_db.migration_exit_code = 1

    with pytest.raises(RuntimeError, match="migration failed"):
        with TestClient(main.app):
            pass

    assert startup_db.user_syncs == 0
    assert startup_db.count(Incident) == 1


def test_successful_migration_starts_and_seeds_the_incident_counter(startup_db):
    startup_db.seed(["INC-1003", "INC-1007"])

    with TestClient(main.app):
        assert store._incident_counter == 7

    assert startup_db.migration_commands[0][-3:] == ["alembic", "upgrade", "head"]
    assert startup_db.user_syncs == 1
