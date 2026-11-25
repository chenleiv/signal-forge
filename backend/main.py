from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()
import asyncio
import json
import os
import pathlib
import random
import re
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import jwt
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text as _sa_text
from starlette.requests import Request

from database import AsyncSessionLocal, engine as db_engine
from db_ops import db_get_rules, db_get_behavioral_settings
import simulation
from simulation import (
    refresh_threat_ips, fetch_ipinfo, generate_threat, next_refresh_in, backfill_demo_events, IPINFO_TOKEN,
)
from store import (
    _score_to_level, _create_alert, _record_event,
    SECRET_KEY, DEMO_MODE, ADMIN_PASSWORD, verify_token,
)
import store as _store
from rate_limit import READ_LIMIT, client_ip, limiter, rate_limit_exceeded_handler
from request_limits import BodySizeLimitMiddleware
from security_headers import SecurityHeadersMiddleware
from users import seed_users, sync_users_with_db
from sessions import load_revoked_sessions

from routers import auth, ip, incidents, alerts, hunting, rules, behavioral, users


USE_DB: bool = db_engine is not None
_store.USE_DB = USE_DB

# Without a database nothing persists, so the admin must be created from
# ADMIN_PASSWORD on every start. With one, startup fails later (in
# sync_users_with_db) only if the table has no admin yet.
if not DEMO_MODE and not USE_DB and not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD (12-72 bytes) is required when DEMO_MODE=false and there is no database")

# In-memory users exist even without a DB (and without lifespan, as in tests).
seed_users(DEMO_MODE, ADMIN_PASSWORD)

# ── Live event stream ─────────────────────────────────────────
# ONE generator feeds all connected clients (fan-out). Previously each
# WebSocket ran its own generator, so N open tabs recorded N x the events.
STREAM_INTERVAL: tuple[float, float] = (0.5, 1.5)
CLIENT_QUEUE_SIZE = 100
_clients: set[asyncio.Queue[str]] = set()


async def _stream_loop() -> None:
    while True:
        if _clients:
            threat = generate_threat()
            if threat:
                _record_event(threat)
                message = json.dumps(threat)
                for queue in list(_clients):
                    try:
                        queue.put_nowait(message)
                    except asyncio.QueueFull:
                        pass  # slow client: drop this event rather than block everyone
        await asyncio.sleep(random.uniform(*STREAM_INTERVAL))


MIGRATION_ERROR_MAX_CHARS = 300
# "module.ExceptionName: message", the line a traceback ends its error with.
_EXCEPTION_LINE_RE = re.compile(r"[A-Za-z_][\w.]*: ")
# user:password@ in a connection URL.
_URL_CREDENTIALS_RE = re.compile(r"://[^/\s:@]+:[^@\s]+@")


def _migration_error_summary(stderr: str) -> str:
    """One short line from Alembic's stderr: the last exception line (else the
    last line), credentials in a URL masked, capped in length. The full output
    is a traceback that can carry SQL, parameters and connection details."""
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    if not lines:
        return "no error output"
    picked = next((line for line in reversed(lines) if _EXCEPTION_LINE_RE.match(line)), lines[-1])
    picked = _URL_CREDENTIALS_RE.sub("://***@", picked)
    if len(picked) > MIGRATION_ERROR_MAX_CHARS:
        picked = picked[:MIGRATION_ERROR_MAX_CHARS] + "..."
    return picked


def _run_migrations() -> None:
    """Bring the schema up to date, or refuse to start: running on an unknown
    schema risks failed requests and bad writes."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True, cwd=pathlib.Path(__file__).parent
    )
    if result.returncode != 0:
        print(f"[Alembic] Migration failed: {_migration_error_summary(result.stderr)}")
        raise RuntimeError("Database migration failed, refusing to start")
    print("[Alembic] Migrations up to date")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if USE_DB:
        _run_migrations()

        if AsyncSessionLocal is not None:
            async with AsyncSessionLocal() as session:
                _row = await session.execute(
                    _sa_text("SELECT COALESCE(MAX(CAST(SUBSTR(id, 5) AS INTEGER)), 0) FROM incidents")
                )
                _max = _row.scalar() or 0
                if _max > 0:
                    _store._incident_counter = _max - 1000
                    print(f"[DB] Seeded incident counter to {_store._incident_counter}")

            async with AsyncSessionLocal() as session:
                await sync_users_with_db(session, DEMO_MODE, ADMIN_PASSWORD)
                await load_revoked_sessions(session)

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

    await refresh_threat_ips(allow_sample=DEMO_MODE, session_factory=AsyncSessionLocal if USE_DB else None)
    backfill_demo_events(DEMO_MODE)

    async def _prefetch_ipinfo():
        if IPINFO_TOKEN:
            async with httpx.AsyncClient() as client:
                # Read at call time: refresh_threat_ips() rebinds THREAT_IPS.
                for ip_addr in list(simulation.THREAT_IPS.keys())[:20]:
                    data = await fetch_ipinfo(client, ip_addr)
                    if data and "lat" in data:
                        _store._ip_coords[ip_addr] = (data["lat"], data["lng"])

    async def _refresh_loop():
        while True:
            await asyncio.sleep(next_refresh_in())
            await refresh_threat_ips(allow_sample=DEMO_MODE, session_factory=AsyncSessionLocal if USE_DB else None)

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
    prefetch_task   = asyncio.create_task(_prefetch_ipinfo())
    stream_task     = asyncio.create_task(_stream_loop())

    yield

    refresh_task.cancel()
    behavioral_task.cancel()
    prefetch_task.cancel()
    stream_task.cancel()
    for task in (behavioral_task, refresh_task, prefetch_task, stream_task):
        try:
            await task
        except asyncio.CancelledError:
            pass


# Swagger UI, ReDoc and the OpenAPI schema list every route and field,
# admin ones included: off unless ENABLE_API_DOCS=true (local development).
# When off, those paths fall through to the SPA like any unknown path.
ENABLE_API_DOCS = os.environ.get("ENABLE_API_DOCS", "").strip().lower() == "true"
_docs = {} if ENABLE_API_DOCS else {"docs_url": None, "redoc_url": None, "openapi_url": None}

# redirect_slashes=False: with uvicorn --no-proxy-headers the scheme is the
# one the proxy used to reach us (http), so a "/api/x/" -> "/api/x" redirect
# would point at http://. The frontend never adds a trailing slash, so such a
# path just gets the usual answer for an unknown path (docs/DECISIONS.md).
app = FastAPI(title="SignalForge API", lifespan=lifespan, redirect_slashes=False, **_docs)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# ── Read-only demo mode ───────────────────────────────────────
# Public demo: block every state-changing request server-side.
# DEMO_MODE is parsed (fail closed) in store.py.

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ALLOWED_WRITES = {
    ("POST", "/auth/login"),
    ("POST", "/auth/logout"),
}


# ── CORS ──────────────────────────────────────────────────────
# The deployed SPA is served by this app (same origin), so it needs no CORS.
# Cross-origin callers, such as `ng serve` on another port in development,
# are listed in CORS_ORIGINS: exact origins, comma-separated. Unset or empty
# means none. A malformed entry stops startup rather than being skipped.
_ORIGIN_RE = re.compile(r"https?://[a-z0-9.-]+(:[0-9]{1,5})?")
# Exactly what the routes and the frontend use.
CORS_METHODS = ["GET", "POST", "PATCH", "DELETE"]
CORS_HEADERS = ["Content-Type"]


def _cors_origins(raw: str) -> list[str]:
    origins = [entry.strip() for entry in raw.split(",") if entry.strip()]
    for origin in origins:
        if not _ORIGIN_RE.fullmatch(origin):
            raise RuntimeError(
                "CORS_ORIGINS: each entry must be an exact origin such as https://example.com "
                "(lowercase, no path, no trailing slash, no wildcard)"
            )
    return origins


CORS_ORIGINS = _cors_origins(os.environ.get("CORS_ORIGINS", ""))


# Registered before CORSMiddleware so CORS stays the outer layer and
# 403 responses still carry CORS headers.
@app.middleware("http")
async def demo_read_only(request: Request, call_next):
    if (
        DEMO_MODE
        and request.method not in SAFE_METHODS
        and (request.method, request.url.path) not in ALLOWED_WRITES
    ):
        return JSONResponse({"detail": "Read-only demo"}, status_code=403)
    return await call_next(request)


# Inside CORS, so a 413 still carries CORS headers.
app.add_middleware(BodySizeLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
    allow_credentials=True,
)

# Added last, so it is the outermost layer: every response gets the headers,
# including CORS preflights, demo-mode 403s and rate-limit 429s. Only the exact
# docs paths skip the CSP, and only while the docs are served.
_docs_paths = frozenset(
    path for path in (app.docs_url, app.docs_url and app.swagger_ui_oauth2_redirect_url, app.redoc_url) if path
)
app.add_middleware(SecurityHeadersMiddleware, docs_paths=_docs_paths)

app.include_router(auth.router)
app.include_router(ip.router)
app.include_router(incidents.router)
app.include_router(alerts.router)
app.include_router(hunting.router)
app.include_router(rules.router)
app.include_router(behavioral.router)
app.include_router(users.router)


# Close code for a missing, invalid, ended or expired session. The frontend
# checks the session once (a new ticket), then shows "signed out" and does
# not reconnect.
WS_SESSION_ENDED = 4001
# An idle stream re-checks its session at least this often (seconds).
WS_RECHECK_SECONDS = 2.0
# Close code when no first message arrives in time. The frontend treats it
# like any other drop: reconnect with backoff.
WS_AUTH_TIMEOUT = 4408
# Seconds a new socket has to send its ticket as the first message. The
# client sends it on open, so this only bounds sockets that never authenticate.
WS_AUTH_TIMEOUT_SECONDS = 5.0
# Upper bound for the first message; a ticket is a few hundred characters.
WS_AUTH_MAX_CHARS = 4096
# Sent once the ticket is accepted; events follow.
WS_READY = json.dumps({"type": "ready"})
# Close code for any frame the client sends after its ticket: the stream is
# one-way. The frontend treats it like any other drop (reconnect with backoff).
WS_POLICY_VIOLATION = 1008
# Open sockets, unauthenticated and streaming alike. Over either cap the
# handshake is refused with HTTP 429 before the upgrade. Per IP means
# rate_limit.client_ip, so it relies on TRUSTED_PROXY_HOPS_WS.
WS_MAX_PER_IP = 20
WS_MAX_TOTAL = 500
# client IP -> open sockets; an IP with none has no entry. Counted from before
# accept() until the handler returns. One event loop: no locks needed.
_ws_open_by_ip: dict[str, int] = {}


def _ws_ticket_claims(message: dict) -> dict | None:
    """The claims of a valid ticket in the first message, else None.

    Expected: a text frame {"type": "auth", "ticket": "<jwt>"}. Nothing here
    is logged: the ticket is a credential."""
    raw = message.get("text")
    if not isinstance(raw, str) or len(raw) > WS_AUTH_MAX_CHARS:
        return None
    try:
        body = json.loads(raw)
        if not isinstance(body, dict) or body.get("type") != "auth" or not isinstance(body.get("ticket"), str):
            return None
        claims = jwt.decode(body["ticket"], SECRET_KEY, algorithms=["HS256"])
        if claims.get("typ") != "ws" or not _store.session_claims_valid(claims):
            return None
        # Checked last, so the checks above still decide every other case.
        if _seconds_left(claims) <= 0:
            return None
        return claims
    except Exception:
        return None


def _seconds_left(claims: dict) -> float:
    """Seconds until the session behind a ticket expires ("sexp"); 0 when
    the ticket carries no usable expiry (fail closed)."""
    expiry = _store.usable_expiry(claims.get("sexp"))
    return 0.0 if expiry is None else expiry - time.time()


@app.websocket("/ws/threats")
async def threats_ws(ws: WebSocket):
    ip = client_ip(ws)
    if _ws_open_by_ip.get(ip, 0) >= WS_MAX_PER_IP or sum(_ws_open_by_ip.values()) >= WS_MAX_TOTAL:
        try:
            await ws.send_denial_response(JSONResponse({"detail": "Too many open streams"}, status_code=429))
        except RuntimeError:
            await ws.close(code=1013)  # no denial-response support: refused with 403
        return
    _ws_open_by_ip[ip] = _ws_open_by_ip.get(ip, 0) + 1
    try:
        await _serve_stream(ws)
    finally:
        left = _ws_open_by_ip[ip] - 1
        if left:
            _ws_open_by_ip[ip] = left
        else:
            del _ws_open_by_ip[ip]


async def _serve_stream(ws: WebSocket) -> None:
    # The ticket arrives as the first message, never in the URL, so it cannot
    # end up in server or proxy access logs.
    await ws.accept()
    try:
        try:
            first = await asyncio.wait_for(ws.receive(), timeout=WS_AUTH_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:  # the built-in TimeoutError only from Python 3.11
            await ws.close(code=WS_AUTH_TIMEOUT)
            return
        if first["type"] == "websocket.disconnect":
            return
        claims = _ws_ticket_claims(first)
        if claims is None:
            await ws.close(code=WS_SESSION_ENDED)
            return
        await ws.send_text(WS_READY)
    except (WebSocketDisconnect, RuntimeError):
        return

    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=CLIENT_QUEUE_SIZE)
    _clients.add(queue)
    # The client has nothing to send after its ticket. Reading anyway keeps
    # uvicorn reading the socket (it stops while the app leaves a message
    # untaken), and any text or binary frame ends the stream.
    reader: asyncio.Task = asyncio.create_task(ws.receive())
    getter: asyncio.Task | None = None
    try:
        while True:
            # Wake up no later than the session's expiry, so an idle stream
            # closes on time rather than up to WS_RECHECK_SECONDS late.
            timeout = max(0.0, min(WS_RECHECK_SECONDS, _seconds_left(claims)))
            if getter is None:
                getter = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({getter, reader}, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            if reader in done:
                if reader.result()["type"] != "websocket.disconnect":
                    await ws.close(code=WS_POLICY_VIOLATION)
                break
            message: str | None = None
            if getter in done:
                message, getter = getter.result(), None
            # Same checks as every HTTP request: logout, deletion, role change
            # and password resets end an open stream too, and so does the
            # session's own expiry.
            if _seconds_left(claims) <= 0 or not _store.session_claims_valid(claims):
                await ws.close(code=WS_SESSION_ENDED)
                break
            if message is not None:
                await ws.send_text(message)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        reader.cancel()
        if getter is not None:
            getter.cancel()
        _clients.discard(queue)


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


@app.get("/api/config")
@limiter.limit(READ_LIMIT)
async def get_config(request: Request):
    # Public, non-sensitive: lets the UI explain read-only demo mode up front.
    return {"demo_mode": DEMO_MODE}


@app.get("/api/threat-feed")
@limiter.limit(READ_LIMIT)
async def get_threat_feed(request: Request, _=Depends(verify_token)):
    # Lets the UI explain a paused or sample feed instead of empty charts.
    return dict(simulation.FEED_STATUS)


# HEAD for uptime monitors. Two methods on one route give both the same
# OpenAPI operation id, so HEAD is its own route, kept out of the schema.
@app.get("/health")
@app.head("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


# Serve Angular SPA — catch-all returns index.html for unknown paths (client-side routing)
_static = pathlib.Path(__file__).parent / "static"
if _static.exists():
    from fastapi.responses import FileResponse

    # HEAD too: some link-preview crawlers send HEAD before GET, and a GET-only
    # route answers it with 405. Not an API route, so kept out of the OpenAPI
    # schema (two methods on one function also give a duplicate operation id).
    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_spa(full_path: str):
        static_root = _static.resolve()
        try:
            file_path = (static_root / full_path).resolve()
            file_path.relative_to(static_root)
        except (ValueError, OSError):
            return FileResponse(str(static_root / "index.html"))
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(static_root / "index.html"))
