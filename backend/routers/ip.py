from __future__ import annotations
import json
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from constants import GEO_DATA, MITRE_MAP
from store import ip_store, _blocked_ips, _ip_coords, _score_to_level, validate_ip, verify_token
from simulation import fetch_ipinfo, IPINFO_TOKEN

ABUSEIPDB_API_KEY = os.environ.get("ABUSEIPDB_API_KEY", "")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")

_abuse_cache: dict[str, dict] = {}
_geo_cache: dict[str, dict] = {}
_ai_summary_cache: dict[str, str] = {}

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


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
                "country_code":     data.get("countryCode"),
                "isp":              data.get("isp"),
                "total_reports":    data.get("totalReports"),
            }
            _abuse_cache[ip] = result
            return result
    except Exception:
        return None


@router.get("/api/ip/{ip}/history")
@limiter.limit("30/minute")
async def get_ip_history(
    request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)
):
    events = list(ip_store.get(ip, []))
    if not events:
        return {"ip": ip, "score": 0, "threat_level": "low", "events": [], "regions": [], "mitre_tags": []}

    avg = sum(e["score"] for e in events) / len(events)
    regions   = list({e.get("region", "US") for e in events})
    mitre_tags = list({tag for e in events for tag in MITRE_MAP.get(e.get("attack_type", ""), [])})
    enrichment = await enrich_ip(ip) or {}

    return {
        "ip": ip,
        "score": int(avg),
        "threat_level": _score_to_level(avg),
        "events": list(reversed(events))[:50],
        "regions": regions,
        "mitre_tags": mitre_tags,
        **enrichment,
    }


@router.get("/api/ip/{ip}/ai-summary")
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
        "mitre_tags": list({t for e in events for t in MITRE_MAP.get(e["attack_type"], [])}),
    }
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        max_tokens=150,
        messages=[{"role": "user", "content": f"You are a SOC analyst. Write a 2-sentence threat intelligence summary for this IP activity: {json.dumps(context)}. Be specific and technical."}],
    )
    summary = response.choices[0].message.content
    _ai_summary_cache[ip] = summary
    return {"summary": summary}


@router.get("/api/ip/{ip}/geo")
@limiter.limit("30/minute")
async def get_ip_geo(
    request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)
):
    if ip in _geo_cache:
        return _geo_cache[ip]

    if IPINFO_TOKEN:
        async with httpx.AsyncClient() as client:
            data = await fetch_ipinfo(client, ip)
        if data:
            _geo_cache[ip] = data
            if "lat" in data:
                _ip_coords[ip] = (data["lat"], data["lng"])
            return data

    fallback = GEO_DATA.get(ip, {"country": "Unknown", "country_code": "??", "city": "Unknown", "org": "Unknown", "asn": "Unknown", "timezone": "UTC"})
    _geo_cache[ip] = fallback
    return fallback


@router.get("/api/ip/{ip}/related")
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
        overlap = target_types & {e["attack_type"] for e in events}
        if not overlap:
            continue
        avg = sum(e["score"] for e in events) / len(events)
        related.append({"ip": other_ip, "shared_attacks": sorted(overlap), "score": int(avg), "threat_level": _score_to_level(avg), "event_count": len(events)})
    related.sort(key=lambda x: x["score"], reverse=True)
    return {"related": related[:5]}


@router.get("/api/ip/{ip}/block")
@limiter.limit("30/minute")
async def get_block_status(request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)):
    return {"blocked": ip in _blocked_ips, "ip": ip}


@router.post("/api/ip/{ip}/block")
@limiter.limit("20/minute")
async def block_ip(request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)):
    _blocked_ips.add(ip)
    return {"blocked": True, "ip": ip}


@router.delete("/api/ip/{ip}/block")
@limiter.limit("20/minute")
async def unblock_ip(request: Request, ip: str = Depends(validate_ip), _=Depends(verify_token)):
    _blocked_ips.discard(ip)
    return {"blocked": False, "ip": ip}


@router.post("/api/command")
@limiter.limit("20/minute")
async def run_command(request: Request, body: dict, _=Depends(verify_token)):
    from collections import deque
    cmd = body.get("command", "").strip().lower()
    if len(cmd) > 100:
        return {"output": "Error: command too long"}
    ALLOWED_COMMANDS = {"help", "status", "clear"}
    ALLOWED_PREFIXES = ("block ip ", "unblock ip ", "scan ")
    if cmd not in ALLOWED_COMMANDS and not cmd.startswith(ALLOWED_PREFIXES):
        return {"output": f"Unknown command: '{cmd}'. Type 'help' for available commands."}

    if cmd == "help":
        return {"output": "Commands: help | status | block ip <ip> | unblock ip <ip> | scan <ip> | clear"}
    if cmd == "status":
        total = sum(len(v) for v in ip_store.values())
        return {"output": f"Tracked IPs: {len(ip_store)} | Blocked: {len(_blocked_ips)} | Total Events: {total}"}
    if cmd.startswith("block ip "):
        target = cmd.split("block ip ")[1].strip()
        _blocked_ips.add(target)
        return {"output": f"[BLOCKED] {target} added to blocklist"}
    if cmd.startswith("unblock ip "):
        target = cmd.split("unblock ip ")[1].strip()
        _blocked_ips.discard(target)
        return {"output": f"[OK] {target} removed from blocklist"}
    if cmd.startswith("scan "):
        target = cmd.split("scan ")[1].strip()
        events = ip_store.get(target, deque())
        blocked = "BLOCKED" if target in _blocked_ips else "active"
        score = max((e["score"] for e in events), default=0)
        return {"output": f"{target} | {len(events)} events | max score: {score} | status: {blocked}"}
    if cmd == "clear":
        return {"output": "__clear__"}
