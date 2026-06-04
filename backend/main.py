from __future__ import annotations
import asyncio
import json
import pathlib
import random
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text as _sa_text
from starlette.requests import Request

from database import AsyncSessionLocal, engine as db_engine, get_db
from db_ops import db_get_rules, db_get_behavioral_settings
from simulation import refresh_threat_ips, fetch_ipinfo, generate_threat, THREAT_IPS, IPINFO_TOKEN
from store import (
    _rules, _behavioral_config, _ip_coords,
    ip_store, minute_buckets, _current_minute, _current_bucket_count,
    _behavioral_flagged, _score_to_level, _create_alert, _record_event,
    SECRET_KEY, verify_token,
)
import store as _store

from routers import auth, ip, incidents, alerts, hunting, rules, behavioral

USE_DB: bool = db_engine is not None
_store.USE_DB = USE_DB


@asynccontextmanager
async def lifespan(app: FastAPI):
    if USE_DB:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, cwd=pathlib.Path(__file__).parent
        )
        if result.returncode != 0:
            print(f"[Alembic] Migration failed:\n{result.stderr}")
        else:
            print("[Alembic] Migrations up to date")

        if AsyncSessionLocal is not None:
            async with AsyncSessionLocal() as session:
                _count_row = await session.execute(_sa_text("SELECT COUNT(*) FROM incidents"))
                _count = _count_row.scalar() or 0
                if _count > 50:
                    await session.execute(_sa_text("DELETE FROM incidents"))
                    await session.commit()
                    print(f"[DB] Cleared {_count} auto-generated incidents from DB")

                _row = await session.execute(
                    _sa_text("SELECT COALESCE(MAX(CAST(SUBSTR(id, 5) AS INTEGER)), 0) FROM incidents")
                )
                _max = _row.scalar() or 0
                if _max > 0:
                    _store._incident_counter = _max - 1000
                    print(f"[DB] Seeded incident counter to {_store._incident_counter}")

            async with AsyncSessionLocal() as session:
                _store._rules.clear()
                _store._rules.extend(await db_get_rules(session))
                print(f"[DB] Loaded {len(_store._rules)} rules")

                bs = await db_get_behavioral_settings(session)
                _store._behavioral_config.update({
                    "cooldown_min":       bs["cooldown_min"],
                    "repeated_threshold": bs["repeated_threshold"],
                    "escalation_delta":   bs["escalation_delta"],
                })
                print(f"[DB] Loaded behavioral settings: {_store._behavioral_config}")

    await refresh_threat_ips()

    if IPINFO_TOKEN:
        async with httpx.AsyncClient() as client:
            for ip_addr in list(THREAT_IPS.keys())[:20]:
                data = await fetch_ipinfo(client, ip_addr)
                if data:
                    if "lat" in data:
                        _store._ip_coords[ip_addr] = (data["lat"], data["lng"])

    async def _refresh_loop():
        while True:
            await asyncio.sleep(6 * 3600)
            await refresh_threat_ips()

    async def _behavioral_loop():
        while True:
            await asyncio.sleep(60)
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(minutes=10)
            cooldown = timedelta(minutes=_store._behavioral_config["cooldown_min"])

            for ip_addr, events_deque in list(_store.ip_store.items()):
                events = list(events_deque)
                if not events:
                    continue

                flagged = _store._behavioral_flagged.setdefault(ip_addr, {})

                recent = [e for e in events if datetime.fromisoformat(e["timestamp"]) >= window_start]
                last_repeated = flagged.get("repeated_at")
                if (
                    len(recent) >= _store._behavioral_config["repeated_threshold"]
                    and (last_repeated is None or now - last_repeated > cooldown)
                ):
                    flagged["repeated_at"] = now
                    dominant = max(
                        set(e["attack_type"] for e in recent),
                        key=lambda t: sum(1 for e in recent if e["attack_type"] == t),
                    )
                    _create_alert(
                        source="behavioral", type="RepeatedIP", severity="high", ip=ip_addr,
                        message=f"{ip_addr} fired {len(recent)} events in 10 min (dominant: {dominant})",
                    )

                if len(events) < 6:
                    continue
                overall_avg = sum(e["score"] for e in events) / len(events)
                recent_avg  = sum(e["score"] for e in events[-5:]) / 5
                last_escalation = flagged.get("escalation_at")
                if (
                    recent_avg - overall_avg >= _store._behavioral_config["escalation_delta"]
                    and (last_escalation is None or now - last_escalation > cooldown)
                ):
                    flagged["escalation_at"] = now
                    _create_alert(
                        source="behavioral", type="Escalation", severity="critical", ip=ip_addr,
                        message=f"{ip_addr} score escalated: overall avg {int(overall_avg)} → recent avg {int(recent_avg)}",
                    )

    refresh_task    = asyncio.create_task(_refresh_loop())
    behavioral_task = asyncio.create_task(_behavioral_loop())

    yield

    refresh_task.cancel()
    behavioral_task.cancel()
    for task in (behavioral_task, refresh_task):
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="SignalForge API", lifespan=lifespan)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://signal-forge-tane.onrender.com", "http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ip.router)
app.include_router(incidents.router)
app.include_router(alerts.router)
app.include_router(hunting.router)
app.include_router(rules.router)
app.include_router(behavioral.router)


@app.websocket("/ws/threats")
async def threats_ws(ws: WebSocket, token: str = ""):
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        await ws.close(code=4001)
        return

    await ws.accept()
    try:
        while True:
            threat = generate_threat()
            if threat:
                _record_event(threat)
                await ws.send_text(json.dumps(threat))
            await asyncio.sleep(random.uniform(0.5, 1.5))
    except WebSocketDisconnect:
        pass


@app.get("/api/stats")
@limiter.limit("50/minute")
async def get_stats(request: Request, _=Depends(verify_token)):
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    attack_types    = {"SQLi": 0, "DDoS": 0, "BruteForce": 0, "PortScan": 0, "Malware": 0}
    ip_counts: dict[str, int]   = {}
    ip_scores: dict[str, float] = {}

    for ip_addr, events in _store.ip_store.items():
        if not events:
            continue
        score_sum = 0
        for e in events:
            score_sum += e["score"]
            lvl = e.get("threat_level", "low")
            if lvl in severity_counts:
                severity_counts[lvl] += 1
            atype = e.get("attack_type", "SQLi")
            if atype in attack_types:
                attack_types[atype] += 1
        avg = score_sum / len(events)
        ip_counts[ip_addr] = len(events)
        ip_scores[ip_addr] = avg

    top_ips = sorted(
        [{"ip": ip_addr, "count": ip_counts[ip_addr], "score": int(ip_scores[ip_addr]), "threat_level": _score_to_level(ip_scores[ip_addr])} for ip_addr in ip_counts],
        key=lambda x: x["count"], reverse=True,
    )[:10]

    buckets = list(_store.minute_buckets)
    if _store._current_minute:
        buckets.append({"minute": _store._current_minute, "count": _store._current_bucket_count})

    return {"severity_counts": severity_counts, "attack_types": attack_types, "events_per_min": buckets, "top_ips": top_ips}


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}
