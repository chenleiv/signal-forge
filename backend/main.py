from __future__ import annotations
import os
import httpx
import asyncio
import json
import random
from collections import defaultdict, deque
from typing import Any
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

ABUSEIPDB_API_KEY = os.environ.get("ABUSEIPDB_API_KEY", "")
_abuse_cache: dict[str, dict] = {}

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
_ai_summary_cache: dict[str, str] = {}

_blocked_ips: set[str] = set()
SECRET_KEY = os.environ.get("JWT_SECRET", "threatwatcher-dev-secret")


app = FastAPI(title="SignalForge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
_incident_counter: int = 0

# ── Simulation data ───────────────────────────────────────────

THREAT_IPS = [
    "185.220.101.47",
    "45.33.32.156",
    "104.21.33.14",
    "77.88.8.8",
    "198.51.100.23",
    "192.0.2.88",
    "203.0.113.5",
    "91.108.4.1",
    "185.159.82.45",
    "51.15.193.47",
    "167.99.247.3",
    "64.225.32.100",
]

ATTACK_TYPES = ["SQLi", "DDoS", "BruteForce", "PortScan", "Malware"]

REGIONS = ["US", "EU", "RU", "CN", "IL", "BR"]

MITRE_MAP: dict[str, list[str]] = {
    "SQLi": ["T1190", "T1059"],
    "DDoS": ["T1498", "T1499"],
    "BruteForce": ["T1110"],
    "PortScan": ["T1046"],
    "Malware": ["T1059", "T1204"],
}

INCIDENT_TITLES = {
    "SQLi": "SQL Injection campaign detected",
    "DDoS": "Distributed Denial of Service attack",
    "BruteForce": "Brute Force authentication attack",
    "PortScan": "Reconnaissance port scan detected",
    "Malware": "Malware execution detected",
}


ANALYSTS = ["Alice Chen", "Bob Martinez", "Sarah Kim", "James Liu", None]


# ── In-memory store ───────────────────────────────────────────

# ip -> deque of events (max 200 per IP)
ip_store: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))

# Rolling per-minute buckets for EPM chart: list of {"minute": str, "count": int}
minute_buckets: deque = deque(maxlen=15)
_current_minute: str = ""
_current_bucket_count: int = 0
incidents_store: deque = deque(maxlen=50)
_event_counter: int = 0
_next_incident_at: int = random.randint(8, 12)


def _current_minute_str() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M")


def _create_incident(trigger: dict) -> None:
    global _incident_counter
    _incident_counter += 1
    attack_type = trigger["attack_type"]
    now = datetime.now(timezone.utc).isoformat()
    incidents_store.appendleft(
        {
            "id": f"INC-{1000 + _incident_counter:04d}",
            "title": INCIDENT_TITLES.get(attack_type, "Unknown attack"),
            "severity": trigger["threat_level"],
            "status": random.choices(
                ["open", "investigating", "contained", "closed"],
                weights=[50, 30, 15, 5],
            )[0],
            "attack_type": attack_type,
            "source_region": trigger["region"],
            "event_count": random.randint(5, 50),
            "assigned_to": random.choice(ANALYSTS),
            "created_at": now,
            "updated_at": now,
            "mitre_tags": MITRE_MAP.get(attack_type, []),
        }
    )


def _record_event(event: dict) -> None:
    global _event_counter, _next_incident_at
    _event_counter += 1
    if _event_counter >= _next_incident_at:
        _event_counter = 0
        _next_incident_at = random.randint(8, 12)
        _create_incident(event)

    """Write event into ip_store and update minute_buckets."""
    global _current_minute, _current_bucket_count

    ip_store[event["ip"]].append(event)

    minute = _current_minute_str()
    if minute != _current_minute:
        if _current_minute:
            minute_buckets.append(
                {"minute": _current_minute, "count": _current_bucket_count}
            )
        _current_minute = minute
        _current_bucket_count = 1
    else:
        _current_bucket_count += 1


# ── Threat simulation ─────────────────────────────────────────


def generate_threat() -> dict:
    ip = random.choice(THREAT_IPS)
    score = random.randint(5, 99)
    attack_type = random.choice(ATTACK_TYPES)
    region = random.choice(REGIONS)

    if score >= 80:
        level = "critical"
    elif score >= 60:
        level = "high"
    elif score >= 40:
        level = "medium"
    else:
        level = "low"

    return {
        "ip": ip,
        "score": score,
        "threat_level": level,
        "attack_type": attack_type,
        "region": region,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── REST: authentication ──────────────────────────────────────


@app.post("/auth/login")
async def login(body: dict):
    if body.get("username") == "analyst" and body.get("password") == "threatwatcher":
        from jose import jwt

        token = jwt.encode(
            {"sub": "analyst", "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
            SECRET_KEY,
            algorithm="HS256",
        )
        return {"access_token": token}
    from fastapi import HTTPException

    raise HTTPException(status_code=401, detail="Invalid credentials")


# ── WebSocket endpoint ────────────────────────────────────────


@app.websocket("/ws/threats")
async def threats_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            threat = generate_threat()
            _record_event(threat)
            await ws.send_text(json.dumps(threat))
            await asyncio.sleep(random.uniform(0.5, 1.5))
    except WebSocketDisconnect:
        pass


# ── REST: aggregated stats ────────────────────────────────────


@app.get("/api/stats")
def get_stats():
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    attack_types = {"SQLi": 0, "DDoS": 0, "BruteForce": 0, "PortScan": 0, "Malware": 0}
    ip_counts: dict[str, int] = {}
    ip_scores: dict[str, float] = {}

    for ip, events in ip_store.items():
        ip_counts[ip] = len(events)
        ip_scores[ip] = max(e["score"] for e in events)
        for e in events:
            level = e.get("threat_level", "low")
            if level in severity_counts:
                severity_counts[level] += 1
            atype = e.get("attack_type", "SQLi")
            if atype in attack_types:
                attack_types[atype] += 1

    top_ips = sorted(
        [
            {"ip": ip, "count": ip_counts[ip], "score": int(ip_scores[ip])}
            for ip in ip_counts
        ],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    buckets = list(minute_buckets)
    if _current_minute:
        buckets.append({"minute": _current_minute, "count": _current_bucket_count})

    return {
        "severity_counts": severity_counts,
        "attack_types": attack_types,
        "events_per_min": buckets,
        "top_ips": top_ips,
    }


# ── REST: per-IP history ──────────────────────────────────────


async def enrich_ip(ip: str) -> dict | None:
    if ip in _abuse_cache:
        return _abuse_cache[ip]
    if not ABUSEIPDB_API_KEY:
        return None
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.abuseipdb.com/api/v2/check",
                params={"ipAddress": ip, "maxAgeInDays": 90},
                headers={"Key": ABUSEIPDB_API_KEY, "Accept": "application/json"},
                timeout=5.0,
            )
            data = r.json().get("data", {})
            result = {
                "abuse_confidence": data.get("abuseConfidenceScore"),
                "country_code": data.get("countryCode"),
                "isp": data.get("isp"),
                "total_reports": data.get("totalReports"),
            }
            _abuse_cache[ip] = result
            return result
    except Exception:
        return None


@app.get("/api/ip/{ip}/history")
async def get_ip_history(ip: str):
    events = list(ip_store.get(ip, []))
    if not events:
        return {
            "ip": ip,
            "score": 0,
            "threat_level": "low",
            "events": [],
            "regions": [],
            "mitre_tags": [],
        }

    score = max(e["score"] for e in events)
    level = max(events, key=lambda e: e["score"])["threat_level"]
    regions = list({e.get("region", "US") for e in events})
    mitre_tags = list(
        {tag for e in events for tag in MITRE_MAP.get(e.get("attack_type", ""), [])}
    )

    enrichment = await enrich_ip(ip) or {}

    return {
        "ip": ip,
        "score": score,
        "threat_level": level,
        "events": list(reversed(events))[:50],
        "regions": regions,
        "mitre_tags": mitre_tags,
        **enrichment,
    }


# ── REST: LLM analysis ────────────────────────────────────────
@app.get("/api/ip/{ip}/ai-summary")
async def get_ip_ai_summary(ip: str):
    if ip in _ai_summary_cache:
        return {"summary": _ai_summary_cache[ip]}
    if not GROQ_API_KEY:
        return {"summary": None}

    from groq import Groq

    events = list(ip_store.get(ip, []))
    context = {
        "ip": ip,
        "total_events": len(events),
        "max_score": max((e["score"] for e in events), default=0),
        "attack_types": list({e["attack_type"] for e in events}),
        "regions": list({e["region"] for e in events}),
        "mitre_tags": list(
            {t for e in events for t in MITRE_MAP.get(e["attack_type"], [])}
        ),
    }

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": f"You are a SOC analyst. Write a 2-sentence threat intelligence summary for this IP activity: {json.dumps(context)}. Be specific and technical.",
            }
        ],
    )
    summary = response.choices[0].message.content
    _ai_summary_cache[ip] = summary
    return {"summary": summary}


# ── REST: command interface ────────────────────────────────────


@app.post("/api/command")
async def run_command(body: dict):
    cmd = body.get("command", "").strip().lower()

    if cmd == "help":
        return {
            "output": "Commands: help | status | block ip <ip> | unblock ip <ip> | scan <ip> | clear"
        }
    elif cmd == "status":
        total = sum(len(v) for v in ip_store.values())
        return {
            "output": f"Tracked IPs: {len(ip_store)} | Blocked: {len(_blocked_ips)} | Total Events: {total}"
        }
    elif cmd.startswith("block ip "):
        ip = cmd.split("block ip ")[1].strip()
        _blocked_ips.add(ip)
        return {"output": f"[BLOCKED] {ip} added to blocklist"}
    elif cmd.startswith("unblock ip "):
        ip = cmd.split("unblock ip ")[1].strip()
        _blocked_ips.discard(ip)
        return {"output": f"[OK] {ip} removed from blocklist"}
    elif cmd.startswith("scan "):
        ip = cmd.split("scan ")[1].strip()
        events = ip_store.get(ip, deque())
        blocked = "BLOCKED" if ip in _blocked_ips else "active"
        score = max((e["score"] for e in events), default=0)
        return {
            "output": f"{ip} | {len(events)} events | max score: {score} | status: {blocked}"
        }
    elif cmd == "clear":
        return {"output": "__clear__"}
    else:
        return {
            "output": f"Unknown command: '{cmd}'. Type 'help' for available commands."
        }


# ── REST: incidents ────────────────────────────────────────────


@app.get("/api/incidents")
def get_incidents():
    return list(incidents_store)


# ── Health check ──────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok"}
