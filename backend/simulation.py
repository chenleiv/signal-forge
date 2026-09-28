from __future__ import annotations
import json
import os
import pathlib
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Optional

import httpx

from constants import (
    COUNTRY_NAMES, ATTACK_TYPES, REGIONS, _SEVERITY_BANDS, _SQLI_PAYLOADS, _MALWARE_FAMILIES,
    _SERVICES, _PROTOCOLS, _SCAN_TYPES, _ENDPOINTS,
)
from db_ops import db_get_threat_feed_snapshot, db_save_threat_feed_snapshot
from store import _ip_coords, is_public_ip

ABUSEIPDB_API_KEY = os.environ.get("ABUSEIPDB_API_KEY", "")
IPINFO_TOKEN      = os.environ.get("IPINFO_TOKEN", "")

THREAT_IPS: dict[str, int] = {}

# THREAT_IPS_CACHE: another cache file (e2e tests use a fixed one).
_CACHE_FILE = pathlib.Path(os.environ.get("THREAT_IPS_CACHE") or pathlib.Path(__file__).parent / "threat_ips_cache.json")
# Bundled sample IPs: demo mode only, when there is no feed and no cache.
_SAMPLE_FILE = pathlib.Path(__file__).parent / "threat_ips_sample.json"

REFRESH_SECONDS = 24 * 3600
RETRY_SECONDS   = 3600
# A 429's Retry-After is clamped to [MIN_RETRY_SECONDS, REFRESH_SECONDS]: a
# huge value must not freeze the feed, a tiny one must not hammer the API.
MIN_RETRY_SECONDS = 5 * 60
_quota_resets_in: Optional[int] = None

# What the live stream is built from, served to the UI so a paused or sample
# feed is explained instead of looking like a fault.
#   state:  live (fresh data) | cached (older data) | sample | unavailable
#   reason: why it is not live: quota (AbuseIPDB 429) | no_key | error
FEED_STATUS: dict[str, Optional[str]] = {"state": "unavailable", "reason": None}

# Stored lists (file, database) are only trusted after this check, since
# they feed the live stream directly.
MAX_FEED_IPS = 1000


def _clean_ips(raw: object) -> dict[str, int]:
    """Public IPs with an integer score 0-100; anything else is dropped."""
    if not isinstance(raw, dict):
        return {}
    clean = {
        ip: score for ip, score in raw.items()
        if is_public_ip(ip) and type(score) is int and 0 <= score <= 100
    }
    return dict(list(clean.items())[:MAX_FEED_IPS])


def _load_cache() -> dict[str, int]:
    try:
        if _CACHE_FILE.exists():
            data = json.loads(_CACHE_FILE.read_text())
            ips = _clean_ips(data.get("ips")) if isinstance(data, dict) else {}
            if ips:
                print(f"[AbuseIPDB] Loaded {len(ips)} threat IPs from cache")
                return ips
    except Exception:
        pass
    return {}


def _load_sample() -> dict[str, int]:
    try:
        return json.loads(_SAMPLE_FILE.read_text()).get("ips") or {}
    except Exception:
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
        r.raise_for_status()   # an error body (quota, bad token) is not geolocation data
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


def _set_status(state: str, reason: Optional[str]) -> None:
    FEED_STATUS.update(state=state, reason=reason)


# ── Database snapshot ─────────────────────────────────────────
# Render's disk is wiped on every restart, so the file cache alone let each
# restart spend one of the few daily blacklist calls. The snapshot survives.

SessionFactory = Callable[[], object]


async def _load_snapshot(session_factory: Optional[SessionFactory]) -> Optional[tuple[dict[str, int], float]]:
    """(ips, age in seconds), or None: no database, no row, or unusable data."""
    if session_factory is None:
        return None
    try:
        async with session_factory() as session:
            stored = await db_get_threat_feed_snapshot(session)
    except Exception as exc:
        print(f"[AbuseIPDB] Could not read the stored snapshot ({type(exc).__name__})")
        return None
    if stored is None:
        return None
    ips = _clean_ips(stored[0])
    age = datetime.now(timezone.utc).timestamp() - stored[1].timestamp()
    return (ips, age) if ips else None


async def _save_snapshot(session_factory: Optional[SessionFactory], ips: dict[str, int]) -> None:
    if session_factory is None:
        return
    try:
        async with session_factory() as session:
            await db_save_threat_feed_snapshot(session, ips)
    except Exception as exc:
        print(f"[AbuseIPDB] Could not store the snapshot ({type(exc).__name__})")


def _use_fallback(reason: str, allow_sample: bool, stored: Optional[tuple[dict[str, int], float]] = None) -> None:
    """No fresh data: stream the file cache or the stored snapshot, else the
    sample (demo only), else nothing."""
    global THREAT_IPS
    if cached := _load_cache() or (stored[0] if stored else {}):
        THREAT_IPS, state = cached, "cached"
    elif allow_sample and (sample := _load_sample()):
        THREAT_IPS, state = sample, "sample"
        print(f"[AbuseIPDB] Using {len(sample)} bundled sample IPs")
    else:
        THREAT_IPS, state = {}, "unavailable"
    _set_status(state, reason)


def _retry_after(response: httpx.Response) -> Optional[int]:
    """Seconds until the quota resets, from Retry-After (seconds or an HTTP date).
    None when the header is missing or unreadable."""
    value = response.headers.get("Retry-After", "").strip()
    if value.isdigit():
        seconds = float(value)
    else:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    return int(min(max(seconds, MIN_RETRY_SECONDS), REFRESH_SECONDS))


def next_refresh_in() -> int:
    """When to fetch again: daily when live; at the quota reset after a 429
    that says when; otherwise hourly, so the feed resumes soon."""
    if FEED_STATUS["state"] == "live" or FEED_STATUS["reason"] == "no_key":
        return REFRESH_SECONDS
    if FEED_STATUS["reason"] == "quota" and _quota_resets_in is not None:
        return _quota_resets_in
    return RETRY_SECONDS


async def refresh_threat_ips(allow_sample: bool = False, session_factory: Optional[SessionFactory] = None) -> None:
    global THREAT_IPS, _quota_resets_in
    _quota_resets_in = None
    stored = await _load_snapshot(session_factory)
    if not ABUSEIPDB_API_KEY:
        _use_fallback("no_key", allow_sample, stored)
        if not THREAT_IPS:
            print("[AbuseIPDB] No API key and no cache — simulation paused")
        return
    if _cache_is_fresh() and (cached := _load_cache()):
        THREAT_IPS = cached
        _set_status("live", None)
        print(f"[AbuseIPDB] Cache is fresh — skipping API call ({len(THREAT_IPS)} IPs)")
        return
    if stored and stored[1] < REFRESH_SECONDS:
        THREAT_IPS = stored[0]
        _set_status("live", None)
        print(f"[AbuseIPDB] Stored snapshot is fresh — skipping API call ({len(THREAT_IPS)} IPs)")
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
            ip_scores = _clean_ips({
                e["ipAddress"]: e.get("abuseConfidenceScore", 50)
                for e in entries if isinstance(e, dict) and e.get("ipAddress")
            })
            if ip_scores:
                THREAT_IPS = ip_scores
                _save_cache(ip_scores)
                await _save_snapshot(session_factory, ip_scores)
                _set_status("live", None)
                print(f"[AbuseIPDB] Loaded {len(ip_scores)} threat IPs with real scores")
            else:
                _use_fallback("error", allow_sample, stored)
                print("[AbuseIPDB] Empty response — falling back to cache")
    except Exception as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        if status == 429:
            _quota_resets_in = _retry_after(exc.response)
        _use_fallback("quota" if status == 429 else "error", allow_sample, stored)
        # Type and status only: the message may echo the request (and its key).
        print(f"[AbuseIPDB] Refresh failed ({type(exc).__name__}, status={status}) — feed is {FEED_STATUS['state']}")


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
