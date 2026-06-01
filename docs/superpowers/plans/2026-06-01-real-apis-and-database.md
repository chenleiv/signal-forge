# Real APIs + Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded THREAT_IPS with live AbuseIPDB blacklist data, and persist incidents/notes/tasks to PostgreSQL so data survives server restarts.

**Architecture:** New `database.py` holds the async SQLAlchemy engine; `models.py` defines ORM tables; `db_ops.py` contains all async CRUD functions. `main.py` calls `db_ops` functions from endpoint handlers. When `DATABASE_URL` is not set, the app falls back to the existing in-memory `incidents_store` deque. AbuseIPDB blacklist is fetched at startup and refreshed every 6 hours via a background `asyncio.Task`.

**Tech Stack:** SQLAlchemy 2.0 async, asyncpg, Alembic, pytest, pytest-asyncio, aiosqlite (test only)

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/requirements.txt` | Modify | Add sqlalchemy[asyncio], asyncpg, alembic, aiosqlite, pytest, pytest-asyncio |
| `backend/database.py` | Create | Async engine, session factory, `get_db()` dependency |
| `backend/models.py` | Create | SQLAlchemy ORM: Incident, Note, IncidentTask |
| `backend/db_ops.py` | Create | Async CRUD functions for all incident endpoints |
| `backend/alembic.ini` | Create | Alembic configuration |
| `backend/alembic/env.py` | Create | Alembic migration env |
| `backend/alembic/versions/001_initial_schema.py` | Create | Initial schema migration |
| `backend/main.py` | Modify | Add `_refresh_threat_ips`, update lifespan, wire endpoints to db_ops |
| `backend/tests/test_db_ops.py` | Create | CRUD tests using async SQLite in-memory |
| `backend/tests/test_abuseipdb.py` | Create | `_refresh_threat_ips` tests with mocked httpx |

---

## Task 1: Update dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Replace requirements.txt contents**

```
fastapi
uvicorn[standard]
httpx
python-jose[cryptography]
anthropic
groq
slowapi
sqlalchemy[asyncio]>=2.0
asyncpg
alembic
pytest
pytest-asyncio
aiosqlite
```

- [ ] **Step 2: Install new dependencies**

```bash
cd backend && source venv/bin/activate && pip install sqlalchemy[asyncio] asyncpg alembic pytest pytest-asyncio aiosqlite
```

Expected: All packages install without errors.

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: add sqlalchemy, asyncpg, alembic, pytest, aiosqlite"
```

---

## Task 2: database.py — engine and session factory

**Files:**
- Create: `backend/database.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_db_ops.py` (shell only, to be filled in Task 5)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/__init__.py` (empty).

Create `backend/tests/test_db_ops.py`:

```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    from database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_db_session_connects(db_session):
    assert db_session is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_db_ops.py::test_db_session_connects -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'database'`

- [ ] **Step 3: Create database.py**

```python
from __future__ import annotations
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Render provides postgres:// but SQLAlchemy 2.0 requires postgresql+asyncpg://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


class Base(DeclarativeBase):
    pass


def make_engine():
    if not DATABASE_URL:
        return None
    return create_async_engine(DATABASE_URL, pool_pre_ping=True)


engine = make_engine()

AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = (
    async_sessionmaker(engine, expire_on_commit=False) if engine else None
)


async def get_db():
    if AsyncSessionLocal is None:
        yield None
        return
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_db_ops.py::test_db_session_connects -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/database.py backend/tests/__init__.py backend/tests/test_db_ops.py
git commit -m "feat: async SQLAlchemy database module with in-memory fallback"
```

---

## Task 3: models.py — ORM models

**Files:**
- Create: `backend/models.py`
- Modify: `backend/tests/test_db_ops.py`

- [ ] **Step 1: Add model test**

Append to `backend/tests/test_db_ops.py`:

```python
@pytest.mark.asyncio
async def test_incident_model_roundtrip(db_session):
    from models import Incident
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    inc = Incident(
        id="INC-1001",
        title="Test incident",
        status="open",
        severity="high",
        attack_type="SQLi",
        source_region="US",
        event_count=5,
        mitre_tags='["T1190"]',
        created_at=now,
        updated_at=now,
    )
    db_session.add(inc)
    await db_session.commit()
    await db_session.refresh(inc)
    assert inc.id == "INC-1001"
    assert inc.severity == "high"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_db_ops.py::test_incident_model_roundtrip -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Create models.py**

```python
from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, Text, ForeignKey, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id:            Mapped[str]           = mapped_column(String, primary_key=True)
    title:         Mapped[str]           = mapped_column(Text, nullable=False)
    status:        Mapped[str]           = mapped_column(String(20), nullable=False, default="open")
    severity:      Mapped[str]           = mapped_column(String(20), nullable=False)
    attack_type:   Mapped[str]           = mapped_column(String(50), nullable=False)
    source_ip:     Mapped[str | None]    = mapped_column(String(45), nullable=True)
    source_region: Mapped[str | None]    = mapped_column(String(10), nullable=True)
    event_count:   Mapped[int]           = mapped_column(Integer, nullable=False, default=0)
    mitre_tags:    Mapped[str]           = mapped_column(Text, nullable=False, default="[]")
    assigned_to:   Mapped[str | None]    = mapped_column(String(100), nullable=True)
    created_at:    Mapped[datetime]      = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at:    Mapped[datetime]      = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    notes:  Mapped[list[Note]]          = relationship("Note", back_populates="incident", cascade="all, delete-orphan")
    tasks:  Mapped[list[IncidentTask]]  = relationship("IncidentTask", back_populates="incident", cascade="all, delete-orphan")


class Note(Base):
    __tablename__ = "notes"

    id:          Mapped[str]      = mapped_column(String, primary_key=True)
    incident_id: Mapped[str]      = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    text:        Mapped[str]      = mapped_column(Text, nullable=False)
    author:      Mapped[str]      = mapped_column(String(100), nullable=False)
    created_at:  Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    incident: Mapped[Incident] = relationship("Incident", back_populates="notes")


class IncidentTask(Base):
    __tablename__ = "incident_tasks"

    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True)
    task_index:  Mapped[int] = mapped_column(Integer, primary_key=True)

    incident: Mapped[Incident] = relationship("Incident", back_populates="tasks")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_db_ops.py -v
```

Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/tests/test_db_ops.py
git commit -m "feat: SQLAlchemy ORM models for incidents, notes, tasks"
```

---

## Task 4: Alembic setup + initial migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/001_initial_schema.py`

- [ ] **Step 1: Initialize Alembic**

```bash
cd backend && source venv/bin/activate && alembic init alembic
```

Expected: Creates `alembic.ini` and `alembic/` directory.

- [ ] **Step 2: Edit alembic.ini — set script_location**

In `backend/alembic.ini`, find the line `sqlalchemy.url = driver://user:pass@localhost/dbname` and replace it with:

```ini
sqlalchemy.url =
```

(We set the URL dynamically in env.py, not here.)

- [ ] **Step 3: Replace alembic/env.py**

```python
from __future__ import annotations
import os
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from database import Base
from models import Incident, Note, IncidentTask  # noqa: F401 — registers tables

target_metadata = Base.metadata


def get_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Create the initial migration manually**

Create `backend/alembic/versions/001_initial_schema.py`:

```python
"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'incidents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('attack_type', sa.String(50), nullable=False),
        sa.Column('source_ip', sa.String(45), nullable=True),
        sa.Column('source_region', sa.String(10), nullable=True),
        sa.Column('event_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('mitre_tags', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('assigned_to', sa.String(100), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'notes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('incident_id', sa.String(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('author', sa.String(100), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'incident_tasks',
        sa.Column('incident_id', sa.String(), nullable=False),
        sa.Column('task_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('incident_id', 'task_index'),
    )


def downgrade() -> None:
    op.drop_table('incident_tasks')
    op.drop_table('notes')
    op.drop_table('incidents')
```

- [ ] **Step 5: Commit**

```bash
git add backend/alembic.ini backend/alembic/ backend/alembic/versions/
git commit -m "feat: Alembic migrations setup with initial schema"
```

---

## Task 5: db_ops.py — async CRUD functions

**Files:**
- Create: `backend/db_ops.py`
- Modify: `backend/tests/test_db_ops.py`

- [ ] **Step 1: Add CRUD tests**

Append to `backend/tests/test_db_ops.py`:

```python
@pytest.mark.asyncio
async def test_create_and_get_incident(db_session):
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    from db_ops import db_create_incident, db_get_incidents
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    data = {
        "id": "INC-2001",
        "title": "BruteForce attack",
        "status": "open",
        "severity": "high",
        "attack_type": "BruteForce",
        "source_ip": "1.2.3.4",
        "source_region": "RU",
        "event_count": 10,
        "mitre_tags": ["T1110"],
        "assigned_to": None,
        "created_at": now,
        "updated_at": now,
        "notes": [],
        "completed_tasks": [],
    }
    await db_create_incident(db_session, data)
    results = await db_get_incidents(db_session)
    assert len(results) == 1
    assert results[0]["id"] == "INC-2001"
    assert results[0]["attack_type"] == "BruteForce"


@pytest.mark.asyncio
async def test_add_note(db_session):
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    from db_ops import db_create_incident, db_add_note
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    data = {
        "id": "INC-3001", "title": "X", "status": "open",
        "severity": "low", "attack_type": "PortScan",
        "source_region": "US", "event_count": 1,
        "mitre_tags": [], "assigned_to": None,
        "created_at": now, "updated_at": now,
        "notes": [], "completed_tasks": [],
    }
    await db_create_incident(db_session, data)
    note = await db_add_note(db_session, "INC-3001", text="test note", author="analyst1")
    assert note["text"] == "test note"
    assert note["author"] == "analyst1"
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_db_ops.py -v
```

Expected: Last 2 tests FAIL — `ModuleNotFoundError: No module named 'db_ops'`

- [ ] **Step 3: Create db_ops.py**

```python
from __future__ import annotations
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Incident, Note, IncidentTask


def _incident_to_dict(inc: Incident) -> dict:
    return {
        "id": inc.id,
        "title": inc.title,
        "status": inc.status,
        "severity": inc.severity,
        "attack_type": inc.attack_type,
        "source_ip": inc.source_ip,
        "source_region": inc.source_region,
        "event_count": inc.event_count,
        "mitre_tags": json.loads(inc.mitre_tags),
        "assigned_to": inc.assigned_to,
        "created_at": inc.created_at.isoformat() if isinstance(inc.created_at, datetime) else inc.created_at,
        "updated_at": inc.updated_at.isoformat() if isinstance(inc.updated_at, datetime) else inc.updated_at,
        "notes": [
            {"id": n.id, "text": n.text, "author": n.author,
             "at": n.created_at.isoformat() if isinstance(n.created_at, datetime) else n.created_at}
            for n in inc.notes
        ],
        "completed_tasks": [t.task_index for t in inc.tasks],
    }


async def db_get_incidents(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(Incident)
        .options(selectinload(Incident.notes), selectinload(Incident.tasks))
        .order_by(Incident.created_at.desc())
    )
    return [_incident_to_dict(inc) for inc in result.scalars()]


async def db_get_incident(session: AsyncSession, incident_id: str) -> dict | None:
    result = await session.execute(
        select(Incident)
        .options(selectinload(Incident.notes), selectinload(Incident.tasks))
        .where(Incident.id == incident_id)
    )
    inc = result.scalar_one_or_none()
    return _incident_to_dict(inc) if inc else None


async def db_create_incident(session: AsyncSession, data: dict) -> dict:
    created_at = data["created_at"]
    updated_at = data["updated_at"]
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    if isinstance(updated_at, str):
        updated_at = datetime.fromisoformat(updated_at)

    inc = Incident(
        id=data["id"],
        title=data["title"],
        status=data["status"],
        severity=data["severity"],
        attack_type=data["attack_type"],
        source_ip=data.get("source_ip"),
        source_region=data.get("source_region"),
        event_count=data.get("event_count", 0),
        mitre_tags=json.dumps(data.get("mitre_tags", [])),
        assigned_to=data.get("assigned_to"),
        created_at=created_at,
        updated_at=updated_at,
    )
    session.add(inc)
    await session.commit()
    await session.refresh(inc, ["notes", "tasks"])
    return _incident_to_dict(inc)


async def db_patch_incident(session: AsyncSession, incident_id: str, patch: dict) -> dict | None:
    result = await session.execute(
        select(Incident)
        .options(selectinload(Incident.notes), selectinload(Incident.tasks))
        .where(Incident.id == incident_id)
    )
    inc = result.scalar_one_or_none()
    if inc is None:
        return None
    if "status" in patch:
        inc.status = patch["status"]
    if "assigned_to" in patch:
        inc.assigned_to = patch["assigned_to"]
    inc.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(inc, ["notes", "tasks"])
    return _incident_to_dict(inc)


async def db_add_note(session: AsyncSession, incident_id: str, text: str, author: str) -> dict:
    now = datetime.now(timezone.utc)
    note = Note(
        id=str(uuid4()),
        incident_id=incident_id,
        text=text,
        author=author,
        created_at=now,
    )
    session.add(note)
    # bump incident updated_at
    result = await session.execute(select(Incident).where(Incident.id == incident_id))
    inc = result.scalar_one_or_none()
    if inc:
        inc.updated_at = now
    await session.commit()
    return {"id": note.id, "text": note.text, "author": note.author, "at": now.isoformat()}


async def db_update_tasks(session: AsyncSession, incident_id: str, task_indices: list[int]) -> list[int]:
    await session.execute(delete(IncidentTask).where(IncidentTask.incident_id == incident_id))
    for idx in task_indices:
        session.add(IncidentTask(incident_id=incident_id, task_index=idx))
    result = await session.execute(select(Incident).where(Incident.id == incident_id))
    inc = result.scalar_one_or_none()
    if inc:
        inc.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return task_indices


async def db_find_open_incident_by_ip(session: AsyncSession, ip: str) -> dict | None:
    result = await session.execute(
        select(Incident)
        .options(selectinload(Incident.notes), selectinload(Incident.tasks))
        .where(Incident.source_ip == ip, Incident.status != "closed")
    )
    inc = result.scalar_one_or_none()
    return _incident_to_dict(inc) if inc else None
```

- [ ] **Step 4: Run all tests**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_db_ops.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db_ops.py backend/tests/test_db_ops.py
git commit -m "feat: db_ops async CRUD layer for incidents"
```

---

## Task 6: AbuseIPDB live feed

**Files:**
- Create: `backend/tests/test_abuseipdb.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_abuseipdb.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_refresh_uses_api_when_key_set(monkeypatch):
    import main as m

    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "test-key")
    monkeypatch.setattr(m, "THREAT_IPS", ["0.0.0.0"])

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"ipAddress": "1.1.1.1", "abuseConfidenceScore": 95},
            {"ipAddress": "2.2.2.2", "abuseConfidenceScore": 92},
        ]
    }
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value = mock_client
        await m._refresh_threat_ips()

    assert "1.1.1.1" in m.THREAT_IPS
    assert "2.2.2.2" in m.THREAT_IPS
    assert "0.0.0.0" not in m.THREAT_IPS


@pytest.mark.asyncio
async def test_refresh_keeps_fallback_when_no_key(monkeypatch):
    import main as m

    original = list(m._FALLBACK_THREAT_IPS)
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "")
    monkeypatch.setattr(m, "THREAT_IPS", ["9.9.9.9"])

    await m._refresh_threat_ips()

    assert m.THREAT_IPS == original


@pytest.mark.asyncio
async def test_refresh_keeps_fallback_on_error(monkeypatch):
    import main as m

    original = list(m._FALLBACK_THREAT_IPS)
    monkeypatch.setattr(m, "ABUSEIPDB_API_KEY", "test-key")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__.return_value.get.side_effect = Exception("network error")
        await m._refresh_threat_ips()

    assert m.THREAT_IPS == original
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_abuseipdb.py -v
```

Expected: FAIL — `AttributeError: module 'main' has no attribute '_refresh_threat_ips'`

- [ ] **Step 3: Add `_FALLBACK_THREAT_IPS` and `_refresh_threat_ips` to main.py**

In `backend/main.py`, after the existing `THREAT_IPS` list (around line 126), add:

```python
# Keep original list as fallback
_FALLBACK_THREAT_IPS = list(THREAT_IPS)


async def _refresh_threat_ips() -> None:
    global THREAT_IPS
    if not ABUSEIPDB_API_KEY:
        THREAT_IPS = list(_FALLBACK_THREAT_IPS)
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.abuseipdb.com/api/v2/blacklist",
                headers={"Key": ABUSEIPDB_API_KEY, "Accept": "application/json"},
                params={"confidenceMinimum": 90, "limit": 100},
                timeout=10.0,
            )
            entries = r.json().get("data", [])
            ips = [e["ipAddress"] for e in entries if e.get("ipAddress")]
            if ips:
                THREAT_IPS = ips
                print(f"[AbuseIPDB] Loaded {len(ips)} threat IPs")
            else:
                THREAT_IPS = list(_FALLBACK_THREAT_IPS)
    except Exception as exc:
        print(f"[AbuseIPDB] Refresh failed: {exc} — using fallback")
        THREAT_IPS = list(_FALLBACK_THREAT_IPS)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_abuseipdb.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_abuseipdb.py
git commit -m "feat: AbuseIPDB live blacklist feed with fallback"
```

---

## Task 7: Wire main.py — lifespan + incident endpoints

**Files:**
- Modify: `backend/main.py`

This task replaces all in-memory incident operations with `db_ops` calls.
When `DATABASE_URL` is not set, the code falls back to the existing `incidents_store` deque.

- [ ] **Step 1: Add imports at the top of main.py**

After the existing imports block, add:

```python
from database import AsyncSessionLocal, engine as db_engine, Base
from db_ops import (
    db_get_incidents, db_get_incident, db_create_incident,
    db_patch_incident, db_add_note, db_update_tasks,
    db_find_open_incident_by_ip,
)
USE_DB: bool = db_engine is not None
```

- [ ] **Step 2: Update lifespan to run migrations and refresh IPs**

Replace the existing `lifespan` function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run DB migrations if DB is configured
    if USE_DB:
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, cwd=pathlib.Path(__file__).parent
        )
        if result.returncode != 0:
            print(f"[Alembic] Migration failed:\n{result.stderr}")
        else:
            print("[Alembic] Migrations up to date")

    # Fetch real threat IPs from AbuseIPDB (falls back to hardcoded list if no key)
    await _refresh_threat_ips()

    # Enrich fetched IPs with geo data via IPInfo
    if IPINFO_TOKEN:
        async with httpx.AsyncClient() as client:
            for ip in THREAT_IPS[:20]:  # cap to 20 to avoid startup delay
                data = await _fetch_ipinfo(client, ip)
                if data:
                    _geo_cache[ip] = data
                    if "lat" in data:
                        _ip_coords[ip] = (data["lat"], data["lng"])

    # Start background AbuseIPDB refresh task (every 6 hours)
    async def _refresh_loop():
        while True:
            await asyncio.sleep(6 * 3600)
            await _refresh_threat_ips()

    refresh_task = asyncio.create_task(_refresh_loop())

    yield

    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        pass
```

Add `import pathlib` near the top of main.py if not already present.

- [ ] **Step 3: Update `_create_incident` to also write to DB**

Replace the existing `_create_incident` function:

```python
def _create_incident(trigger: dict) -> None:
    global _incident_counter
    _incident_counter += 1
    attack_type = trigger["attack_type"]
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "id": f"INC-{1000 + _incident_counter:04d}",
        "title": INCIDENT_TITLES.get(attack_type, "Unknown attack"),
        "severity": trigger["threat_level"],
        "status": random.choices(
            ["open", "investigating", "contained", "closed"],
            weights=[50, 30, 15, 5],
        )[0],
        "attack_type": attack_type,
        "source_ip": trigger.get("ip"),
        "source_region": trigger["region"],
        "event_count": random.randint(5, 50),
        "assigned_to": random.choice(ANALYSTS),
        "created_at": now,
        "updated_at": now,
        "mitre_tags": MITRE_MAP.get(attack_type, []),
        "notes": [],
        "completed_tasks": [],
    }
    incidents_store.appendleft(data)

    if USE_DB and AsyncSessionLocal is not None:
        async def _write():
            async with AsyncSessionLocal() as session:
                await db_create_incident(session, data)
        asyncio.create_task(_write())
```

- [ ] **Step 4: Replace `GET /api/incidents` endpoint**

Replace:
```python
@app.get("/api/incidents")
async def get_incidents(_=Depends(verify_token)):
    return list(incidents_store)
```

With:
```python
@app.get("/api/incidents")
async def get_incidents(db: AsyncSession | None = Depends(get_db), _=Depends(verify_token)):
    if USE_DB and db is not None:
        return await db_get_incidents(db)
    return list(incidents_store)
```

Add `from sqlalchemy.ext.asyncio import AsyncSession` to imports, and `from database import get_db`.

- [ ] **Step 5: Replace `PATCH /api/incidents/{incident_id}` endpoint**

Replace:
```python
@app.patch("/api/incidents/{incident_id}")
async def patch_incident(incident_id: str, body: dict, _=Depends(verify_token)):
    inc = _find_incident(incident_id)
    if "status" in body:
        inc["status"] = body["status"]
    if "assigned_to" in body:
        inc["assigned_to"] = body["assigned_to"]
    inc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return inc
```

With:
```python
@app.patch("/api/incidents/{incident_id}")
async def patch_incident(
    incident_id: str, body: dict,
    db: AsyncSession | None = Depends(get_db), _=Depends(verify_token)
):
    if USE_DB and db is not None:
        result = await db_patch_incident(db, incident_id, body)
        if result is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return result
    inc = _find_incident(incident_id)
    if "status" in body:
        inc["status"] = body["status"]
    if "assigned_to" in body:
        inc["assigned_to"] = body["assigned_to"]
    inc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return inc
```

- [ ] **Step 6: Replace `GET /api/ip/{ip}/case` endpoint**

Replace:
```python
@app.get("/api/ip/{ip}/case")
async def get_ip_case(ip: str = Depends(validate_ip), _=Depends(verify_token)):
    for inc in incidents_store:
        if inc.get("source_ip") == ip and inc["status"] != "closed":
            return {"case_id": inc["id"]}
    return {"case_id": None}
```

With:
```python
@app.get("/api/ip/{ip}/case")
async def get_ip_case(
    ip: str = Depends(validate_ip),
    db: AsyncSession | None = Depends(get_db), _=Depends(verify_token)
):
    if USE_DB and db is not None:
        inc = await db_find_open_incident_by_ip(db, ip)
        return {"case_id": inc["id"] if inc else None}
    for inc in incidents_store:
        if inc.get("source_ip") == ip and inc["status"] != "closed":
            return {"case_id": inc["id"]}
    return {"case_id": None}
```

- [ ] **Step 7: Replace `POST /api/incidents/from-ip` endpoint**

Replace the `create_incident_from_ip` function:

```python
@app.post("/api/incidents/from-ip")
async def create_incident_from_ip(
    body: dict,
    db: AsyncSession | None = Depends(get_db), _=Depends(verify_token)
):
    global _incident_counter
    ip = body.get("ip", "unknown")

    if USE_DB and db is not None:
        existing = await db_find_open_incident_by_ip(db, ip)
        if existing:
            return {**existing, "existing": True}
    else:
        for inc in incidents_store:
            if inc.get("source_ip") == ip and inc["status"] != "closed":
                return {**inc, "existing": True}

    events = list(ip_store.get(ip, deque()))
    attack_types = list({e["attack_type"] for e in events})
    attack_type = attack_types[0] if attack_types else "PortScan"
    scores = [e["score"] for e in events]
    avg_score = sum(scores) / len(scores) if scores else 50
    level = _score_to_level(avg_score)
    regions = list({e["region"] for e in events})
    now = datetime.now(timezone.utc).isoformat()
    _incident_counter += 1
    incident = {
        "id": f"INC-{1000 + _incident_counter:04d}",
        "title": f"{INCIDENT_TITLES.get(attack_type, 'Threat')} on {ip}",
        "severity": level,
        "status": "open",
        "attack_type": attack_type,
        "source_ip": ip,
        "source_region": regions[0] if regions else "Unknown",
        "event_count": len(events),
        "assigned_to": None,
        "created_at": now,
        "updated_at": now,
        "mitre_tags": list({t for e in events for t in MITRE_MAP.get(e["attack_type"], [])}),
        "notes": [],
        "completed_tasks": [],
    }

    if USE_DB and db is not None:
        saved = await db_create_incident(db, incident)
        return {**saved, "existing": False}

    incidents_store.appendleft(incident)
    return {**incident, "existing": False}
```

- [ ] **Step 8: Replace `PATCH /api/incidents/{incident_id}/tasks`**

Replace:
```python
@app.patch("/api/incidents/{incident_id}/tasks")
async def update_tasks(incident_id: str, body: dict, _=Depends(verify_token)):
    inc = _find_incident(incident_id)
    inc["completed_tasks"] = body.get("completed_tasks", [])
    inc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"completed_tasks": inc["completed_tasks"]}
```

With:
```python
@app.patch("/api/incidents/{incident_id}/tasks")
async def update_tasks(
    incident_id: str, body: dict,
    db: AsyncSession | None = Depends(get_db), _=Depends(verify_token)
):
    completed = body.get("completed_tasks", [])
    if USE_DB and db is not None:
        result = await db_update_tasks(db, incident_id, completed)
        return {"completed_tasks": result}
    inc = _find_incident(incident_id)
    inc["completed_tasks"] = completed
    inc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"completed_tasks": inc["completed_tasks"]}
```

- [ ] **Step 9: Replace `POST /api/incidents/{incident_id}/notes`**

Replace:
```python
@app.post("/api/incidents/{incident_id}/notes")
async def add_note(incident_id: str, body: dict, _=Depends(verify_token)):
    inc = _find_incident(incident_id)
    note = {
        "author": body.get("author", "analyst1"),
        "text": body.get("text", "").strip(),
        "at": datetime.now(timezone.utc).isoformat(),
    }
    if not note["text"]:
        raise HTTPException(status_code=400, detail="Note text is required")
    inc["notes"].append(note)
    inc["updated_at"] = note["at"]
    return note
```

With:
```python
@app.post("/api/incidents/{incident_id}/notes")
async def add_note(
    incident_id: str, body: dict,
    db: AsyncSession | None = Depends(get_db), _=Depends(verify_token)
):
    text = body.get("text", "").strip()
    author = body.get("author", "analyst1")
    if not text:
        raise HTTPException(status_code=400, detail="Note text is required")
    if USE_DB and db is not None:
        result = await db_get_incident(db, incident_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return await db_add_note(db, incident_id, text=text, author=author)
    inc = _find_incident(incident_id)
    note = {"author": author, "text": text, "at": datetime.now(timezone.utc).isoformat()}
    inc["notes"].append(note)
    inc["updated_at"] = note["at"]
    return note
```

- [ ] **Step 10: Run all tests**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/ -v
```

Expected: All 7 tests PASS

- [ ] **Step 11: Start the backend locally and verify it starts**

```bash
cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000
```

Expected: App starts, logs show `[AbuseIPDB] Loaded N threat IPs` (or fallback message).

- [ ] **Step 12: Commit**

```bash
git add backend/main.py
git commit -m "feat: wire DB and AbuseIPDB feed into main.py endpoints"
```

---

## Task 8: Render deployment

**Files:**
- Modify: `backend/requirements.txt` (verify asyncpg is listed)

- [ ] **Step 1: Add PostgreSQL database on Render**

In the Render dashboard:
1. Click **New** → **PostgreSQL**
2. Name it `threatwatcher-db`, select Free tier
3. Copy the **Internal Database URL** (starts with `postgresql://...`)

- [ ] **Step 2: Add DATABASE_URL env var to the Web Service**

In the Render Web Service → Environment:
1. Add `DATABASE_URL` = the Internal Database URL from Step 1
2. Render auto-converts `postgres://` → the app handles `postgresql://` → `postgresql+asyncpg://`

- [ ] **Step 3: Push to trigger deploy**

```bash
git push origin master
```

Expected: Render deploys, logs show `[Alembic] Migrations up to date` and `[AbuseIPDB] Loaded N threat IPs`.

- [ ] **Step 4: Verify via the app UI**

1. Open the deployed app
2. Create an incident from a threat IP
3. Add a note
4. Restart the Render service (Dashboard → Manual Deploy)
5. Verify the incident and note still exist after restart

---

## Out of scope

- Threat events persistence (ephemeral by design)
- Frontend changes (API contract unchanged)
- User/auth persistence (JWT is stateless)
