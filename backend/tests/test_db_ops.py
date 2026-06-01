import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    from database import Base
    # Import models to register them with Base metadata
    import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_db_session_connects(db_session):
    assert db_session is not None


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
