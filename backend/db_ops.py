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
