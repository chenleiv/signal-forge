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
