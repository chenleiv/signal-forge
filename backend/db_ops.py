from __future__ import annotations
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Incident, Note, IncidentTask, Rule, BehavioralSettings


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
        "created_at": inc.created_at.isoformat()
        if isinstance(inc.created_at, datetime)
        else inc.created_at,
        "updated_at": inc.updated_at.isoformat()
        if isinstance(inc.updated_at, datetime)
        else inc.updated_at,
        "notes": [
            {
                "id": n.id,
                "text": n.text,
                "author": n.author,
                "at": n.created_at.isoformat()
                if isinstance(n.created_at, datetime)
                else n.created_at,
            }
            for n in inc.notes
        ],
        "completed_tasks": [t.task_index for t in inc.tasks],
    }


async def db_get_incidents(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(Incident)
        .options(selectinload(Incident.notes), selectinload(Incident.tasks))
        .order_by(Incident.created_at.desc())
        .limit(200)
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


async def db_patch_incident(
    session: AsyncSession, incident_id: str, patch: dict
) -> dict | None:
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


async def db_add_note(
    session: AsyncSession, incident_id: str, text: str, author: str
) -> dict:
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
    return {
        "id": note.id,
        "text": note.text,
        "author": note.author,
        "at": now.isoformat(),
    }


async def db_update_tasks(
    session: AsyncSession, incident_id: str, task_indices: list[int]
) -> list[int] | None:
    result = await session.execute(select(Incident).where(Incident.id == incident_id))
    inc = result.scalar_one_or_none()
    if inc is None:
        return None
    await session.execute(
        delete(IncidentTask).where(IncidentTask.incident_id == incident_id)
    )
    for idx in task_indices:
        session.add(IncidentTask(incident_id=incident_id, task_index=idx))
    inc.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return task_indices


async def db_find_open_incident_by_ip(session: AsyncSession, ip: str) -> dict | None:
    result = await session.execute(
        select(Incident)
        .options(selectinload(Incident.notes), selectinload(Incident.tasks))
        .where(Incident.source_ip == ip, Incident.status != "closed")
        .order_by(Incident.created_at.desc())
        .limit(1)
    )
    inc = result.scalars().first()
    return _incident_to_dict(inc) if inc else None


# ── Rules CRUD ────────────────────────────────────────────────


def _rule_to_dict(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "enabled": rule.enabled,
        "conditions": json.loads(rule.conditions),
        "logic": rule.logic,
        "actions": json.loads(rule.actions),
        "match_count": rule.match_count,
        "created_at": rule.created_at.isoformat()
        if isinstance(rule.created_at, datetime)
        else rule.created_at,
    }


async def db_get_rules(session: AsyncSession) -> list[dict]:
    result = await session.execute(select(Rule).order_by(Rule.created_at))
    return [_rule_to_dict(r) for r in result.scalars()]


async def db_create_rule(session: AsyncSession, data: dict) -> dict:
    rule = Rule(
        id=data["id"],
        name=data["name"],
        enabled=data.get("enabled", True),
        conditions=json.dumps(data.get("conditions", [])),
        logic=data.get("logic", "AND"),
        actions=json.dumps(data.get("actions", ["alert"])),
        match_count=0,
        created_at=datetime.fromisoformat(data["created_at"])
        if isinstance(data["created_at"], str)
        else data["created_at"],
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return _rule_to_dict(rule)


async def db_update_rule(
    session: AsyncSession, rule_id: str, patch: dict
) -> dict | None:
    result = await session.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        return None
    if "name" in patch:
        rule.name = patch["name"]
    if "enabled" in patch:
        rule.enabled = patch["enabled"]
    if "conditions" in patch:
        rule.conditions = json.dumps(patch["conditions"])
    if "logic" in patch:
        rule.logic = patch["logic"]
    if "actions" in patch:
        rule.actions = json.dumps(patch["actions"])
    if "match_count" in patch:
        rule.match_count = patch["match_count"]
    await session.commit()
    await session.refresh(rule)
    return _rule_to_dict(rule)


async def db_delete_rule(session: AsyncSession, rule_id: str) -> None:
    await session.execute(delete(Rule).where(Rule.id == rule_id))
    await session.commit()


# ── Behavioral Settings ───────────────────────────────────────


def _behavioral_settings_to_dict(bs: BehavioralSettings) -> dict:
    return {
        "repeated_threshold": bs.repeated_threshold,
        "escalation_delta": bs.escalation_delta,
        "cooldown_min": bs.cooldown_min,
        "updated_at": bs.updated_at.isoformat()
        if isinstance(bs.updated_at, datetime)
        else bs.updated_at,
    }


async def db_get_behavioral_settings(session: AsyncSession) -> dict:
    result = await session.execute(select(BehavioralSettings).limit(1))
    bs = result.scalar_one_or_none()
    if bs is None:
        # Create defaults if not exists
        now = datetime.now(timezone.utc)
        bs = BehavioralSettings(
            repeated_threshold=8,
            escalation_delta=20,
            cooldown_min=30,
            created_at=now,
            updated_at=now,
        )
        session.add(bs)
        await session.commit()
        await session.refresh(bs)
    return _behavioral_settings_to_dict(bs)


async def db_update_behavioral_settings(session: AsyncSession, patch: dict) -> dict:
    result = await session.execute(select(BehavioralSettings).limit(1))
    bs = result.scalar_one_or_none()
    if bs is None:
        # Create with patches applied
        now = datetime.now(timezone.utc)
        bs = BehavioralSettings(
            repeated_threshold=patch.get("repeated_threshold", 15),
            escalation_delta=patch.get("escalation_delta", 20),
            cooldown_min=patch.get("cooldown_min", 30),
            created_at=now,
            updated_at=now,
        )
        session.add(bs)
    else:
        if "repeated_threshold" in patch:
            bs.repeated_threshold = patch["repeated_threshold"]
        if "escalation_delta" in patch:
            bs.escalation_delta = patch["escalation_delta"]
        if "cooldown_min" in patch:
            bs.cooldown_min = patch["cooldown_min"]
        bs.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(bs)
    return _behavioral_settings_to_dict(bs)
