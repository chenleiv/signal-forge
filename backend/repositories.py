"""Storage for incidents, rules and behavioral settings.

With a database (DATABASE_URL) they are read and written there, otherwise in
memory. Routers get the right one from incidents(db) / rules(db) /
behavioral(db) and never branch on it. Rules and behavioral settings keep an
in-memory copy in both modes, because the live detector (store.py) reads it.

Both implementations of each store must behave the same:
tests/test_storage_parity.py and the permission matrix run in both modes.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

import store as _store
from constants import BEHAVIORAL_DEFAULTS
from db_ops import (
    StaleIncident,
    db_add_note, db_create_incident, db_create_rule, db_delete_rule, db_find_open_incident_by_ip,
    db_get_behavioral_settings, db_get_incident, db_get_incidents, db_get_rules, db_patch_incident,
    db_update_behavioral_settings, db_update_rule, db_update_tasks,
)

RULE_FIELDS = ("name", "enabled", "conditions", "logic", "actions")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db(db: Optional[AsyncSession]) -> Optional[AsyncSession]:
    return db if _store.USE_DB and db is not None else None


# ── Incidents ─────────────────────────────────────────────────

class MemoryIncidents:
    async def list(self) -> list[dict]:
        return list(_store.incidents_store)

    async def get(self, incident_id: str) -> dict | None:
        return _store._find_incident(incident_id)

    async def open_case_for_ip(self, ip: str) -> dict | None:
        return next((i for i in _store.incidents_store if i.get("source_ip") == ip and i["status"] != "closed"), None)

    async def add(self, incident: dict) -> dict:
        _store.incidents_store.appendleft(incident)
        return incident

    async def patch(self, incident_id: str, patch: dict, *, expected_assignee: str | None) -> dict | None:
        inc = await self.get(incident_id)
        if inc is None:
            return None
        if inc.get("assigned_to") != expected_assignee:
            raise StaleIncident(incident_id)
        inc.update(patch)
        inc["updated_at"] = _now()
        return inc

    async def set_tasks(self, incident_id: str, tasks: list[int]) -> list[int] | None:
        inc = await self.get(incident_id)
        if inc is None:
            return None
        inc["completed_tasks"] = tasks
        inc["updated_at"] = _now()
        return tasks

    async def add_note(self, incident_id: str, text: str, author: str) -> dict | None:
        inc = await self.get(incident_id)
        if inc is None:
            return None
        note = {"id": str(uuid4()), "text": text, "author": author, "at": _now()}
        inc["notes"].append(note)
        inc["updated_at"] = note["at"]
        return note


class DbIncidents:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self) -> list[dict]:
        return await db_get_incidents(self.db)

    async def get(self, incident_id: str) -> dict | None:
        return await db_get_incident(self.db, incident_id)

    async def open_case_for_ip(self, ip: str) -> dict | None:
        return await db_find_open_incident_by_ip(self.db, ip)

    async def add(self, incident: dict) -> dict:
        return await db_create_incident(self.db, incident)

    async def patch(self, incident_id: str, patch: dict, *, expected_assignee: str | None) -> dict | None:
        return await db_patch_incident(self.db, incident_id, patch, expected_assignee=expected_assignee)

    async def set_tasks(self, incident_id: str, tasks: list[int]) -> list[int] | None:
        return await db_update_tasks(self.db, incident_id, tasks)

    async def add_note(self, incident_id: str, text: str, author: str) -> dict | None:
        if await self.get(incident_id) is None:
            return None
        return await db_add_note(self.db, incident_id, text=text, author=author)


def incidents(db: Optional[AsyncSession]) -> MemoryIncidents | DbIncidents:
    session = _db(db)
    return DbIncidents(session) if session else MemoryIncidents()


# ── Detection rules ───────────────────────────────────────────

def _cached_rule(rule_id: str) -> dict | None:
    return next((r for r in _store._rules if r["id"] == rule_id), None)


class MemoryRules:
    async def list(self) -> list[dict]:
        return _store._rules

    async def create(self, rule: dict) -> dict:
        _store._rules.append(rule)
        return rule

    async def update(self, rule_id: str, fields: dict) -> dict | None:
        rule = _cached_rule(rule_id)
        if rule is not None:
            rule.update(fields)
        return rule

    async def delete(self, rule_id: str) -> None:
        _store._rules[:] = [r for r in _store._rules if r["id"] != rule_id]


class DbRules(MemoryRules):
    """The database is the source of truth; the in-memory copy follows it."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self) -> list[dict]:
        return await db_get_rules(self.db)

    async def create(self, rule: dict) -> dict:
        return await super().create(await db_create_rule(self.db, rule))

    async def update(self, rule_id: str, fields: dict) -> dict | None:
        updated = await db_update_rule(self.db, rule_id, fields)
        if updated is not None:
            await super().update(rule_id, fields)
        return updated

    async def delete(self, rule_id: str) -> None:
        await super().delete(rule_id)
        await db_delete_rule(self.db, rule_id)


def rules(db: Optional[AsyncSession]) -> MemoryRules:
    session = _db(db)
    return DbRules(session) if session else MemoryRules()


# ── Behavioral detection settings ─────────────────────────────

class MemoryBehavioral:
    async def get(self) -> dict:
        return _store._behavioral_config

    async def update(self, patch: dict) -> dict:
        _store._behavioral_config.update(patch)
        return _store._behavioral_config


class DbBehavioral:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self) -> dict:
        return await db_get_behavioral_settings(self.db)

    async def update(self, patch: dict) -> dict:
        result = await db_update_behavioral_settings(self.db, patch)
        _store._behavioral_config.update({k: result[k] for k in BEHAVIORAL_DEFAULTS})
        return result


def behavioral(db: Optional[AsyncSession]) -> MemoryBehavioral | DbBehavioral:
    session = _db(db)
    return DbBehavioral(session) if session else MemoryBehavioral()
