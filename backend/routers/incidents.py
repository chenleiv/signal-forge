from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from constants import INCIDENT_TITLES, MITRE_MAP
from database import get_db
from db_ops import (
    db_get_incidents, db_get_incident, db_create_incident,
    db_patch_incident, db_add_note, db_update_tasks,
    db_find_open_incident_by_ip,
)
from store import (
    ip_store, incidents_store, _incident_counter,
    _score_to_level, _find_incident, validate_ip, verify_token, USE_DB,
)
import store as _store

router = APIRouter()


async def build_incident_for_ip(ip: str, db) -> dict:
    if USE_DB and db is not None:
        existing = await db_find_open_incident_by_ip(db, ip)
        if existing:
            return {**existing, "existing": True}
    else:
        for inc in incidents_store:
            if inc.get("source_ip") == ip and inc["status"] != "closed":
                return {**inc, "existing": True}

    events = list(ip_store.get(ip, deque()))
    attack_types_list = list({e["attack_type"] for e in events})
    attack_type = attack_types_list[0] if attack_types_list else "PortScan"
    scores = [e["score"] for e in events]
    avg_score = sum(scores) / len(scores) if scores else 50
    level = _score_to_level(avg_score)
    regions = list({e["region"] for e in events})
    now = datetime.now(timezone.utc).isoformat()

    _store._incident_counter += 1
    incident = {
        "id": f"INC-{1000 + _store._incident_counter:04d}",
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


@router.get("/api/incidents")
async def get_incidents(db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)):
    if USE_DB and db is not None:
        return await db_get_incidents(db)
    return list(incidents_store)


@router.patch("/api/incidents/{incident_id}")
async def patch_incident(
    incident_id: str, body: dict,
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    if USE_DB and db is not None:
        result = await db_patch_incident(db, incident_id, body)
        if result is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return result
    inc = _find_incident(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if "status" in body:
        inc["status"] = body["status"]
    if "assigned_to" in body:
        inc["assigned_to"] = body["assigned_to"]
    inc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return inc


@router.get("/api/ip/{ip}/case")
async def get_ip_case(
    ip: str = Depends(validate_ip),
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    if USE_DB and db is not None:
        inc = await db_find_open_incident_by_ip(db, ip)
        return {"case_id": inc["id"] if inc else None}
    for inc in incidents_store:
        if inc.get("source_ip") == ip and inc["status"] != "closed":
            return {"case_id": inc["id"]}
    return {"case_id": None}


@router.post("/api/incidents/from-ip")
async def create_incident_from_ip(
    body: dict,
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    return await build_incident_for_ip(body.get("ip", "unknown"), db)


@router.patch("/api/incidents/{incident_id}/tasks")
async def update_tasks(
    incident_id: str, body: dict,
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    completed = body.get("completed_tasks", [])
    if USE_DB and db is not None:
        result = await db_update_tasks(db, incident_id, completed)
        if result is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {"completed_tasks": result}
    inc = _find_incident(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    inc["completed_tasks"] = completed
    inc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"completed_tasks": inc["completed_tasks"]}


@router.post("/api/incidents/{incident_id}/notes")
async def add_note(
    incident_id: str, body: dict,
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    text   = body.get("text", "").strip()
    author = body.get("author", "analyst1")
    if not text:
        raise HTTPException(status_code=400, detail="Note text is required")
    if USE_DB and db is not None:
        if await db_get_incident(db, incident_id) is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        return await db_add_note(db, incident_id, text=text, author=author)
    inc = _find_incident(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    note = {"author": author, "text": text, "at": datetime.now(timezone.utc).isoformat()}
    inc["notes"].append(note)
    inc["updated_at"] = note["at"]
    return note
