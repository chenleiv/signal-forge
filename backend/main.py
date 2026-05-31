from __future__ import annotations
import ipaddress
import os
import httpx
import asyncio
import json
import random
from collections import defaultdict, deque
from typing import Optional
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request


ABUSEIPDB_API_KEY = os.environ.get("ABUSEIPDB_API_KEY", "")
_abuse_cache: dict[str, dict] = {}

IPINFO_TOKEN = os.environ.get("IPINFO_TOKEN", "")
_geo_cache: dict[str, dict] = {}

COUNTRY_NAMES: dict[str, str] = {
    "US": "United States", "RU": "Russia", "CN": "China",
    "DE": "Germany", "GB": "United Kingdom", "FR": "France",
    "NL": "Netherlands", "IL": "Israel", "BR": "Brazil",
    "JP": "Japan", "KR": "South Korea", "IN": "India",
    "CA": "Canada", "AU": "Australia", "SE": "Sweden",
    "RO": "Romania", "UA": "Ukraine", "IS": "Iceland",
    "SG": "Singapore", "TR": "Turkey", "PL": "Poland",
    "IR": "Iran", "KP": "North Korea", "NG": "Nigeria",
}

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
_ai_summary_cache: dict[str, str] = {}

_blocked_ips: set[str] = set()
_ip_coords: dict[str, tuple[float, float]] = {}

SECRET_KEY = os.environ.get("JWT_SECRET", "threatwatcher-dev-secret")


from contextlib import asynccontextmanager

async def _fetch_ipinfo(client: httpx.AsyncClient, ip: str) -> Optional[dict]:
    try:
        r = await client.get(
            f"https://ipinfo.io/{ip}/json",
            params={"token": IPINFO_TOKEN},
            timeout=5.0,
        )
        d = r.json()
        raw_org = d.get("org", "")
        parts = raw_org.split(" ", 1)
        asn = parts[0] if parts[0].startswith("AS") else "Unknown"
        org = parts[1] if len(parts) > 1 else raw_org or "Unknown"
        country_code = d.get("country", "??")
        loc = d.get("loc", "")
        result = {
            "country": COUNTRY_NAMES.get(country_code, country_code),
            "country_code": country_code,
            "city": d.get("city", "Unknown"),
            "org": org,
            "asn": asn,
            "timezone": d.get("timezone", "UTC"),
        }
        if loc:
            lat, lng = map(float, loc.split(","))
            result["lat"] = lat
            result["lng"] = lng
        return result
    except Exception:
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if IPINFO_TOKEN:
        async with httpx.AsyncClient() as client:
            for ip in THREAT_IPS:
                data = await _fetch_ipinfo(client, ip)
                if data:
                    _geo_cache[ip] = data
                    if "lat" in data:
                        _ip_coords[ip] = (data["lat"], data["lng"])
    yield


app = FastAPI(title="SignalForge API", lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address)

security = HTTPBearer()

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://signal-forge-tane.onrender.com", "http://localhost:4200"],
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
    "80.82.77.139",
    "5.188.206.14",
    "194.165.16.11",
    "91.108.4.1",
    "185.159.82.45",
    "51.15.193.47",
    "167.99.247.3",
    "64.225.32.100",
]

ATTACK_TYPES = ["SQLi", "DDoS", "BruteForce", "PortScan", "Malware"]

REGIONS = ["US", "EU", "RU", "CN", "IL", "BR"]

GEO_DATA: dict[str, dict] = {
    "185.220.101.47": {
        "country": "Germany",
        "country_code": "DE",
        "city": "Frankfurt",
        "org": "Tor Exit Relay",
        "asn": "AS24940",
        "timezone": "Europe/Berlin",
    },
    "45.33.32.156": {
        "country": "USA",
        "country_code": "US",
        "city": "Atlanta",
        "org": "Akamai Technologies",
        "asn": "AS63949",
        "timezone": "America/New_York",
    },
    "104.21.33.14": {
        "country": "USA",
        "country_code": "US",
        "city": "San Jose",
        "org": "Cloudflare Inc",
        "asn": "AS13335",
        "timezone": "America/Los_Angeles",
    },
    "77.88.8.8": {
        "country": "Russia",
        "country_code": "RU",
        "city": "Moscow",
        "org": "Yandex LLC",
        "asn": "AS13238",
        "timezone": "Europe/Moscow",
    },
    "80.82.77.139": {
        "country": "Netherlands",
        "country_code": "NL",
        "city": "Amsterdam",
        "org": "Shodan Monitoring",
        "asn": "AS60557",
        "timezone": "Europe/Amsterdam",
    },
    "5.188.206.14": {
        "country": "Russia",
        "country_code": "RU",
        "city": "Moscow",
        "org": "Inferno Solutions",
        "asn": "AS57523",
        "timezone": "Europe/Moscow",
    },
    "194.165.16.11": {
        "country": "Iceland",
        "country_code": "IS",
        "city": "Reykjavik",
        "org": "1984 ehf",
        "asn": "AS44925",
        "timezone": "Atlantic/Reykjavik",
    },
    "91.108.4.1": {
        "country": "Netherlands",
        "country_code": "NL",
        "city": "Amsterdam",
        "org": "Telegram Messenger",
        "asn": "AS62041",
        "timezone": "Europe/Amsterdam",
    },
    "185.159.82.45": {
        "country": "Romania",
        "country_code": "RO",
        "city": "Bucharest",
        "org": "M247 Europe SRL",
        "asn": "AS49327",
        "timezone": "Europe/Bucharest",
    },
    "51.15.193.47": {
        "country": "France",
        "country_code": "FR",
        "city": "Paris",
        "org": "Online S.A.S.",
        "asn": "AS12876",
        "timezone": "Europe/Paris",
    },
    "167.99.247.3": {
        "country": "Germany",
        "country_code": "DE",
        "city": "Frankfurt",
        "org": "DigitalOcean LLC",
        "asn": "AS14061",
        "timezone": "Europe/Berlin",
    },
    "64.225.32.100": {
        "country": "USA",
        "country_code": "US",
        "city": "New York",
        "org": "DigitalOcean LLC",
        "asn": "AS14061",
        "timezone": "America/New_York",
    },
}

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


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        from jose import jwt

        jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def validate_ip(ip: str) -> str:
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid IP address format")

    if (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_reserved
        or parsed.is_multicast
    ):
        raise HTTPException(
            status_code=422, detail="Private or reserved IP not allowed"
        )

    return str(parsed)


def _current_minute_str() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M")


def _score_to_level(avg: float) -> str:
    if avg >= 80:
        return "critical"
    if avg >= 60:
        return "high"
    if avg >= 40:
        return "medium"
    return "low"


def _find_incident(incident_id: str) -> dict:
    for inc in incidents_store:
        if inc["id"] == incident_id:
            return inc
    raise HTTPException(status_code=404, detail="Incident not found")


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
            "notes": [],
            "completed_tasks": [],
        }
    )


def _eval_condition(cond: dict, event: dict) -> bool:
    field = cond.get("field", "")
    op    = cond.get("operator", "=")
    val   = cond.get("value", "")
    ev    = event.get(field)
    if ev is None:
        return False
    if op == ">":
        try:
            return float(ev) > float(val)
        except (ValueError, TypeError):
            return False
    if op == "<":
        try:
            return float(ev) < float(val)
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


def _record_event(event: dict) -> None:
    global _current_minute, _current_bucket_count

    ip_store[event["ip"]].append(event)
    _evaluate_rules(event)

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

    event: dict = {
        "ip": ip,
        "score": score,
        "threat_level": _score_to_level(score),
        "attack_type": attack_type,
        "region": region,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if ip in _ip_coords:
        lat, lng = _ip_coords[ip]
        event["lat"] = lat
        event["lng"] = lng
    return event


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
async def threats_ws(ws: WebSocket, token: str = ""):
    try:
        from jose import jwt

        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        await ws.close(code=4001)
        return

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
@limiter.limit("50/minute")
async def get_stats(request: Request, _=Depends(verify_token)):
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    attack_types = {"SQLi": 0, "DDoS": 0, "BruteForce": 0, "PortScan": 0, "Malware": 0}
    ip_counts: dict[str, int] = {}
    ip_scores: dict[str, float] = {}
    ip_levels: dict[str, str] = {}

    for ip, events in ip_store.items():
        ip_counts[ip] = len(events)
        avg = sum(e["score"] for e in events) / len(events)
        ip_scores[ip] = avg
        ip_levels[ip] = _score_to_level(avg)
        for e in events:
            level = e.get("threat_level", "low")
            if level in severity_counts:
                severity_counts[level] += 1
            atype = e.get("attack_type", "SQLi")
            if atype in attack_types:
                attack_types[atype] += 1

    top_ips = sorted(
        [
            {
                "ip": ip,
                "count": ip_counts[ip],
                "score": int(ip_scores[ip]),
                "threat_level": ip_levels[ip],
            }
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


async def enrich_ip(ip: str) -> Optional[dict]:
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
@limiter.limit("30/minute")
async def get_ip_history(
    request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)
):
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

    avg = sum(e["score"] for e in events) / len(events)
    score = int(avg)
    level = _score_to_level(avg)
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
@limiter.limit("10/minute")
async def get_ip_ai_summary(
    request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)
):
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
@limiter.limit("20/minute")
async def run_command(request: Request, body: dict, _=Depends(verify_token)):
    cmd = body.get("command", "").strip().lower()

    if len(cmd) > 100:
        return {"output": "Error: command too long"}

    ALLOWED_COMMANDS = {"help", "status", "clear"}
    ALLOWED_PREFIXES = ("block ip ", "unblock ip ", "scan ")
    if cmd not in ALLOWED_COMMANDS and not cmd.startswith(ALLOWED_PREFIXES):
        return {
            "output": f"Unknown command: '{cmd}'. Type 'help' for available commands."
        }

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


# ── REST: geo intelligence ────────────────────────────────────


@app.get("/api/ip/{ip}/geo")
@limiter.limit("30/minute")
async def get_ip_geo(
    request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)
):
    if ip in _geo_cache:
        return _geo_cache[ip]

    if IPINFO_TOKEN:
        async with httpx.AsyncClient() as client:
            data = await _fetch_ipinfo(client, ip)
        if data:
            _geo_cache[ip] = data
            if "lat" in data:
                _ip_coords[ip] = (data["lat"], data["lng"])
            return data

    fallback = GEO_DATA.get(ip, {
        "country": "Unknown", "country_code": "??",
        "city": "Unknown", "org": "Unknown",
        "asn": "Unknown", "timezone": "UTC",
    })
    _geo_cache[ip] = fallback
    return fallback


# ── REST: related IPs ─────────────────────────────────────────


@app.get("/api/ip/{ip}/related")
@limiter.limit("30/minute")
async def get_related_ips(
    request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)
):
    target_events = list(ip_store.get(ip, []))
    if not target_events:
        return {"related": []}

    target_types = {e["attack_type"] for e in target_events}
    related = []
    for other_ip, events in ip_store.items():
        if other_ip == ip or not events:
            continue
        other_types = {e["attack_type"] for e in events}
        overlap = target_types & other_types
        if not overlap:
            continue
        avg = sum(e["score"] for e in events) / len(events)
        related.append(
            {
                "ip": other_ip,
                "shared_attacks": sorted(overlap),
                "score": int(avg),
                "threat_level": _score_to_level(avg),
                "event_count": len(events),
            }
        )
    related.sort(key=lambda x: x["score"], reverse=True)
    return {"related": related[:5]}


# ── REST: block / unblock ─────────────────────────────────────


@app.get("/api/ip/{ip}/block")
@limiter.limit("30/minute")
async def get_block_status(
    request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)
):
    return {"blocked": ip in _blocked_ips, "ip": ip}


@app.post("/api/ip/{ip}/block")
@limiter.limit("20/minute")
async def block_ip(
    request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)
):
    _blocked_ips.add(ip)
    return {"blocked": True, "ip": ip}


@app.delete("/api/ip/{ip}/block")
@limiter.limit("20/minute")
async def unblock_ip(
    request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)
):
    _blocked_ips.discard(ip)
    return {"blocked": False, "ip": ip}


# ── REST: incidents ────────────────────────────────────────────


@app.get("/api/incidents")
async def get_incidents(_=Depends(verify_token)):
    return list(incidents_store)


@app.patch("/api/incidents/{incident_id}")
async def patch_incident(incident_id: str, body: dict, _=Depends(verify_token)):
    inc = _find_incident(incident_id)
    if "status" in body:
        inc["status"] = body["status"]
    if "assigned_to" in body:
        inc["assigned_to"] = body["assigned_to"]
    inc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return inc


@app.get("/api/ip/{ip}/case")
async def get_ip_case(ip: str = Depends(validate_ip), _=Depends(verify_token)):
    for inc in incidents_store:
        if inc.get("source_ip") == ip and inc["status"] != "closed":
            return {"case_id": inc["id"]}
    return {"case_id": None}


@app.post("/api/incidents/from-ip")
async def create_incident_from_ip(body: dict, _=Depends(verify_token)):
    global _incident_counter
    ip = body.get("ip", "unknown")

    # Return existing active case if one already exists for this IP
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
        "mitre_tags": list(
            {t for e in events for t in MITRE_MAP.get(e["attack_type"], [])}
        ),
        "notes": [],
        "completed_tasks": [],
    }
    incidents_store.appendleft(incident)
    return {**incident, "existing": False}


@app.patch("/api/incidents/{incident_id}/tasks")
async def update_tasks(incident_id: str, body: dict, _=Depends(verify_token)):
    inc = _find_incident(incident_id)
    inc["completed_tasks"] = body.get("completed_tasks", [])
    inc["updated_at"] = datetime.now(timezone.utc).isoformat()
    return {"completed_tasks": inc["completed_tasks"]}


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


# ── REST: network graph ───────────────────────────────────────


@app.get("/api/network")
async def get_network(_=Depends(verify_token)):
    nodes: list[dict] = []
    links: list[dict] = []
    seen_attacks: set[str] = set()

    for ip, events in ip_store.items():
        ev = list(events)
        if not ev:
            continue
        scores = [e["score"] for e in ev]
        avg = sum(scores) / len(scores)
        score = int(avg)
        level = _score_to_level(avg)

        attack_counts: dict[str, int] = {}
        for e in ev:
            attack_counts[e["attack_type"]] = attack_counts.get(e["attack_type"], 0) + 1

        nodes.append({
            "id": ip, "type": "ip",
            "score": score, "threat_level": level,
            "event_count": len(ev),
        })

        for attack, count in attack_counts.items():
            seen_attacks.add(attack)
            links.append({"source": ip, "target": attack, "value": count})

    for attack in seen_attacks:
        nodes.append({"id": attack, "type": "attack"})

    return {"nodes": nodes, "links": links}


# ── REST: threat hunting ──────────────────────────────────────

_saved_hunts: list[dict] = []

_rules: list[dict] = []


@app.get("/api/hunt")
async def run_hunt(
    ip: Optional[str] = None,
    attack_type: Optional[str] = None,
    region: Optional[str] = None,
    min_score: int = 0,
    max_score: int = 100,
    limit: int = 200,
    _=Depends(verify_token),
):
    results = []
    for ip_addr, events in ip_store.items():
        if ip and ip.lower() not in ip_addr.lower():
            continue
        for e in events:
            if attack_type and e["attack_type"] != attack_type:
                continue
            if region and e["region"] != region:
                continue
            if not (min_score <= e["score"] <= max_score):
                continue
            results.append({**e, "ip": ip_addr})
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"results": results[:limit], "total": len(results)}


@app.get("/api/hunts")
async def get_saved_hunts(_=Depends(verify_token)):
    return _saved_hunts


@app.post("/api/hunts")
async def save_hunt(body: dict, _=Depends(verify_token)):
    hunt = {
        "id": str(uuid4())[:8],
        "name": body.get("name", "Unnamed hunt"),
        "query": body.get("query", {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result_count": body.get("result_count", 0),
    }
    _saved_hunts.insert(0, hunt)
    return hunt


@app.delete("/api/hunts/{hunt_id}")
async def delete_hunt(hunt_id: str, _=Depends(verify_token)):
    global _saved_hunts
    _saved_hunts = [h for h in _saved_hunts if h["id"] != hunt_id]
    return {"ok": True}


# ── REST: detection rules ─────────────────────────────────────


@app.get("/api/rules")
async def get_rules(_=Depends(verify_token)):
    return _rules


@app.post("/api/rules")
async def create_rule(body: dict, _=Depends(verify_token)):
    rule = {
        "id": str(uuid4())[:8],
        "name": body.get("name", "Unnamed Rule"),
        "enabled": body.get("enabled", True),
        "conditions": body.get("conditions", []),
        "logic": body.get("logic", "AND"),
        "actions": body.get("actions", ["alert"]),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "match_count": 0,
    }
    _rules.append(rule)
    return rule


@app.patch("/api/rules/{rule_id}")
async def update_rule(rule_id: str, body: dict, _=Depends(verify_token)):
    for rule in _rules:
        if rule["id"] == rule_id:
            for key in ["name", "enabled", "conditions", "logic", "actions"]:
                if key in body:
                    rule[key] = body[key]
            return rule
    raise HTTPException(status_code=404, detail="Rule not found")


@app.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: str, _=Depends(verify_token)):
    global _rules
    _rules = [r for r in _rules if r["id"] != rule_id]
    return {"ok": True}


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}
