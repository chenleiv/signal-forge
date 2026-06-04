from __future__ import annotations
import asyncio
import ipaddress
import os
import random
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from constants import INCIDENT_TITLES, MITRE_MAP, ANALYSTS
from database import AsyncSessionLocal, get_db
from db_ops import db_update_rule

SECRET_KEY = os.environ.get("JWT_SECRET", "threatwatcher-dev-secret")
security = HTTPBearer()

USE_DB: bool = False  # set by main after engine check

# ── Mutable state ─────────────────────────────────────────────

ip_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))

minute_buckets: deque = deque(maxlen=15)
_current_minute: str = ""
_current_bucket_count: int = 0

incidents_store: deque = deque(maxlen=50)
_incident_counter: int = 0

alerts_store: deque = deque(maxlen=100)
_alert_counter: int = 0

_blocked_ips: set[str] = set()
_ip_coords: dict[str, tuple[float, float]] = {}

_behavioral_flagged: dict[str, dict] = {}
_behavioral_config: dict = {
    "cooldown_min": 30,
    "repeated_threshold": 8,
    "escalation_delta": 20,
}

_rules: list[dict] = []
_saved_hunts: list[dict] = []


# ── Auth helpers ──────────────────────────────────────────────

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def validate_ip(ip: str) -> str:
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid IP address format")
    if parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_reserved or parsed.is_multicast:
        raise HTTPException(status_code=422, detail="Private or reserved IP not allowed")
    return str(parsed)


# ── Pure helpers ──────────────────────────────────────────────

def _score_to_level(avg: float) -> str:
    if avg >= 80: return "critical"
    if avg >= 60: return "high"
    if avg >= 40: return "medium"
    return "low"


def _current_minute_str() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M")


def _find_incident(incident_id: str) -> dict | None:
    return next((inc for inc in incidents_store if inc["id"] == incident_id), None)


def _find_alert(alert_id: str) -> dict | None:
    return next((a for a in alerts_store if a["id"] == alert_id), None)


# ── Creators ──────────────────────────────────────────────────

def _create_alert(source: str, type: str, severity: str, ip: str | None, message: str) -> dict:
    global _alert_counter
    _alert_counter += 1
    now = datetime.now(timezone.utc).isoformat()
    alert = {
        "id": f"ALT-{_alert_counter:04d}",
        "source": source,
        "type": type,
        "severity": severity,
        "ip": ip,
        "message": message,
        "status": "new",
        "created_at": now,
        "acknowledged_at": None,
    }
    alerts_store.appendleft(alert)
    return alert


def _create_incident(trigger: dict) -> None:
    global _incident_counter
    _incident_counter += 1
    attack_type = trigger["attack_type"]
    now = datetime.now(timezone.utc).isoformat()
    incidents_store.appendleft({
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
    })


# ── Rule evaluation ───────────────────────────────────────────

def _eval_condition(cond: dict, event: dict) -> bool:
    field = cond.get("field", "")
    op    = cond.get("operator", "=")
    val   = cond.get("value", "")
    ev    = event.get(field)
    if ev is None:
        return False
    if op in (">", "<"):
        try:
            a, b = float(ev), float(val)
            return a > b if op == ">" else a < b
        except (ValueError, TypeError):
            return False
    if op == "=":
        return str(ev).lower() == str(val).lower()
    if op == "contains":
        return str(val).lower() in str(ev).lower()
    return False


def _execute_actions(rule: dict, event: dict) -> None:
    if "incident" in rule["actions"]:
        _create_incident(event)
    if "alert" in rule["actions"]:
        _create_alert(
            source="rule",
            type=rule["name"],
            severity=event.get("threat_level", "medium"),
            ip=event.get("ip"),
            message=f"Rule '{rule['name']}' matched on {event.get('ip', 'unknown')}",
        )
    if "block" in rule["actions"]:
        _blocked_ips.add(event["ip"])


def _evaluate_rules(event: dict) -> None:
    for rule in _rules:
        if not rule["enabled"]:
            continue
        results = [_eval_condition(c, event) for c in rule["conditions"]]
        if not results:
            continue
        matched = all(results) if rule["logic"] == "AND" else any(results)
        if matched:
            rule["match_count"] += 1
            _execute_actions(rule, event)
            if USE_DB and AsyncSessionLocal is not None:
                async def _bump(rid: str = rule["id"], count: int = rule["match_count"]):
                    try:
                        async with AsyncSessionLocal() as session:
                            await db_update_rule(session, rid, {"match_count": count})
                    except Exception:
                        pass
                asyncio.create_task(_bump())


# ── Event recording ───────────────────────────────────────────

def _record_event(event: dict) -> None:
    global _current_minute, _current_bucket_count
    ip_store[event["ip"]].append(event)
    _evaluate_rules(event)
    minute = _current_minute_str()
    if minute != _current_minute:
        if _current_minute:
            minute_buckets.append({"minute": _current_minute, "count": _current_bucket_count})
        _current_minute = minute
        _current_bucket_count = 1
    else:
        _current_bucket_count += 1
