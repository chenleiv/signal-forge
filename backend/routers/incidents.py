from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from constants import INCIDENT_TITLES, MITRE_MAP, RESPONSE_TASKS, MAX_NOTE_LENGTH
from database import get_db
from db_ops import StaleIncident
from repositories import incidents
from store import ip_store, _score_to_level, validate_ip, verify_token
import store as _store
from rate_limit import CASES_PER_USER
from authz import check_incident_patch, check_work_on_incident
from users import CurrentUser

router = APIRouter()


async def _load_incident(incident_id: str, db) -> dict:
    """Current state of an incident, for permission checks. 404 if missing."""
    inc = await incidents(db).get(incident_id)
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


def _validate_note_text(body: dict) -> str:
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=422, detail="Note text is required")
    text = text.strip()
    if len(text) > MAX_NOTE_LENGTH:
        raise HTTPException(status_code=422, detail=f"Note text is limited to {MAX_NOTE_LENGTH} characters")
    return text


def _validate_completed_tasks(body: dict, incident: dict) -> list[int]:
    """A list of unique task indexes within the incident's playbook."""
    tasks = body.get("completed_tasks")
    n = len(RESPONSE_TASKS.get(incident.get("attack_type"), []))
    if (
        not isinstance(tasks, list)
        # bool is a subclass of int: reject True/False explicitly
        or not all(isinstance(t, int) and not isinstance(t, bool) and 0 <= t < n for t in tasks)
        or len(set(tasks)) != len(tasks)
    ):
        raise HTTPException(
            status_code=422,
            detail=f"completed_tasks must be unique task indexes between 0 and {n - 1}" if n
            else "This incident has no response tasks",
        )
    return tasks


async def build_incident_for_ip(ip: str, db, creator: CurrentUser) -> dict:
    """Open case for `ip`: the existing open one (unchanged), or a new one
    assigned to its creator. Creating a new case counts toward the creator's
    CASES_PER_USER limit (429 when exceeded)."""
    existing = await incidents(db).open_case_for_ip(ip)
    if existing:
        return {**existing, "existing": True}

    if CASES_PER_USER.exceeded(creator.username):
        raise HTTPException(status_code=429, detail="Too many new cases, try again later")
    CASES_PER_USER.hit(creator.username)

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
        "assigned_to": creator.username,
        "created_at": now,
        "updated_at": now,
        "mitre_tags": list({t for e in events for t in MITRE_MAP.get(e["attack_type"], [])}),
        "notes": [],
        "completed_tasks": [],
    }
    saved = await incidents(db).add(incident)
    return {**saved, "existing": False}


@router.get("/api/incidents")
async def get_incidents(db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)):
    return await incidents(db).list()


@router.patch("/api/incidents/{incident_id}")
async def patch_incident(
    incident_id: str, body: dict,
    db: Optional[AsyncSession] = Depends(get_db), user: CurrentUser = Depends(verify_token)
):
    inc = await _load_incident(incident_id, db)
    patch = check_incident_patch(user, inc, body)
    try:
        # Written only if the assignee is still the one the check saw.
        result = await incidents(db).patch(incident_id, patch, expected_assignee=inc["assigned_to"])
    except StaleIncident:
        raise HTTPException(status_code=409, detail="Incident was reassigned meanwhile, reload and retry") from None
    if result is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return result


@router.get("/api/ip/{ip}/case")
async def get_ip_case(
    ip: str = Depends(validate_ip),
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    inc = await incidents(db).open_case_for_ip(ip)
    return {"case_id": inc["id"] if inc else None}


@router.post("/api/incidents/from-ip")
async def create_incident_from_ip(
    body: dict,
    db: Optional[AsyncSession] = Depends(get_db), user: CurrentUser = Depends(verify_token)
):
    ip = body.get("ip")
    if not isinstance(ip, str):  # ipaddress would also accept an int
        raise HTTPException(status_code=422, detail="Invalid IP address format")
    return await build_incident_for_ip(validate_ip(ip), db, user)


@router.patch("/api/incidents/{incident_id}/tasks")
async def update_tasks(
    incident_id: str, body: dict,
    db: Optional[AsyncSession] = Depends(get_db), user: CurrentUser = Depends(verify_token)
):
    inc = await _load_incident(incident_id, db)
    check_work_on_incident(user, inc)
    completed = _validate_completed_tasks(body, inc)
    result = await incidents(db).set_tasks(incident_id, completed)
    if result is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"completed_tasks": result}


@router.post("/api/incidents/{incident_id}/notes")
async def add_note(
    incident_id: str, body: dict,
    db: Optional[AsyncSession] = Depends(get_db), user: CurrentUser = Depends(verify_token)
):
    text   = _validate_note_text(body)
    author = user.username  # from the verified session, never from the request body
    inc = await _load_incident(incident_id, db)
    check_work_on_incident(user, inc)
    note = await incidents(db).add_note(incident_id, text, author)
    if note is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return note
