from __future__ import annotations
import json
import os
import pathlib
import random
from datetime import datetime, timezone
from typing import Optional

import httpx

from constants import (
    COUNTRY_NAMES, ATTACK_TYPES, REGIONS, MITRE_MAP,
    _SEVERITY_BANDS, _SQLI_PAYLOADS, _MALWARE_FAMILIES,
    _SERVICES, _PROTOCOLS, _SCAN_TYPES, _ENDPOINTS,
)
from store import _ip_coords

ABUSEIPDB_API_KEY = os.environ.get("ABUSEIPDB_API_KEY", "")
IPINFO_TOKEN      = os.environ.get("IPINFO_TOKEN", "")

THREAT_IPS: dict[str, int] = {}

_CACHE_FILE = pathlib.Path(__file__).parent / "threat_ips_cache.json"


def _load_cache() -> dict[str, int]:
    try:
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text())
            if isinstance(data, dict) and data.get("ips"):
                print(f"[AbuseIPDB] Loaded {len(data['ips'])} threat IPs from cache")
                return data["ips"]
    except Exception:
        pass
    return {}


def _cache_is_fresh() -> bool:
    try:
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text())
            saved_at = data.get("saved_at")
            if saved_at:
                age = datetime.now(timezone.utc).timestamp() - saved_at
                return age < 24 * 3600
    except Exception:
        pass
    return False


def _save_cache(ip_scores: dict[str, int]) -> None:
    try:
        _CACHE_FILE.write_text(json.dumps({
            "saved_at": datetime.now(timezone.utc).timestamp(),
            "ips": ip_scores,
        }))
    except Exception:
        pass


async def fetch_ipinfo(client: httpx.AsyncClient, ip: str) -> Optional[dict]:
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


async def refresh_threat_ips() -> None:
    global THREAT_IPS
    if not ABUSEIPDB_API_KEY:
        THREAT_IPS = _load_cache()
        if not THREAT_IPS:
            print("[AbuseIPDB] No API key and no cache — simulation paused")
        return
    if _cache_is_fresh():
        THREAT_IPS = _load_cache()
        print(f"[AbuseIPDB] Cache is fresh — skipping API call ({len(THREAT_IPS)} IPs)")
        return
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.abuseipdb.com/api/v2/blacklist",
                headers={"Key": ABUSEIPDB_API_KEY, "Accept": "application/json"},
                params={"confidenceMinimum": 50, "limit": 100},
                timeout=10.0,
            )
            r.raise_for_status()
            entries = r.json().get("data", [])
            ip_scores = {
                e["ipAddress"]: e.get("abuseConfidenceScore", 50)
                for e in entries if e.get("ipAddress")
            }
            if ip_scores:
                THREAT_IPS = ip_scores
                _save_cache(ip_scores)
                print(f"[AbuseIPDB] Loaded {len(ip_scores)} threat IPs with real scores")
            else:
                THREAT_IPS = _load_cache()
                print("[AbuseIPDB] Empty response — falling back to cache")
    except Exception as exc:
        THREAT_IPS = _load_cache()
        if THREAT_IPS:
            print(f"[AbuseIPDB] Refresh failed ({exc}) — using cached data")
        else:
            print(f"[AbuseIPDB] Refresh failed ({exc}) — no cache available")


def _attack_metadata(attack_type: str) -> dict:
    if attack_type == "DDoS":
        return {"packet_rate": random.randint(10_000, 2_000_000), "duration_sec": random.randint(5, 300), "protocol": random.choice(_PROTOCOLS)}
    if attack_type == "SQLi":
        return {"payload": random.choice(_SQLI_PAYLOADS), "target_endpoint": random.choice(_ENDPOINTS)}
    if attack_type == "BruteForce":
        return {"attempts": random.randint(20, 5000), "username": random.choice(["admin", "root", "administrator", "user", "guest"]), "service": random.choice(_SERVICES)}
    if attack_type == "PortScan":
        start = random.randint(20, 1000)
        return {"ports_scanned": list(range(start, start + random.randint(10, 65))), "scan_type": random.choice(_SCAN_TYPES)}
    if attack_type == "Malware":
        return {"family": random.choice(_MALWARE_FAMILIES), "hash": "%032x" % random.getrandbits(128), "c2_domain": f"c2-{random.randint(1,999)}.{random.choice(['xyz','top','ru','cn'])}"}
    return {}


def generate_threat() -> dict:
    if not THREAT_IPS:
        return {}
    ip = random.choice(list(THREAT_IPS.keys()))
    level, lo, hi, _ = random.choices(_SEVERITY_BANDS, weights=[b[3] for b in _SEVERITY_BANDS], k=1)[0]
    score = random.randint(lo, hi)
    attack_type = random.choice(ATTACK_TYPES)
    region = random.choice(REGIONS)
    event: dict = {
        "ip": ip,
        "score": score,
        "threat_level": level,
        "attack_type": attack_type,
        "region": region,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **_attack_metadata(attack_type),
    }
    if ip in _ip_coords:
        lat, lng = _ip_coords[ip]
        event["lat"] = lat
        event["lng"] = lng
    return event
