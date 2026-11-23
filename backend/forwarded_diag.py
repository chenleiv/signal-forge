"""TEMPORARY DIAGNOSTIC: remove once TRUSTED_PROXY_HOPS_HTTP is verified on
Render. See docs/DECISIONS.md, "Temporary X-Forwarded-For hash diagnostic".

Off unless DIAG_FORWARDED_COUNT=true (set in the Render dashboard, then
removed). When on, it logs one short line per NEW combination of values for
API requests (/api/, /auth/) and for WebSocket upgrades to /ws/threats, at
most MAX_PER_KIND lines per kind and MAX_LINES lines per process.

Each line carries the number of X-Forwarded-For entries (counted like
rate_limit.client_ip) and short salted hashes of:
- HTTP: entries[-2] (pick_hash), entries[-1] (last_hash) and the TCP peer;
- WebSocket: entries[-1] (pick_hash) and the TCP peer.
Equal hashes in one process mean equal addresses, so the HTTP and WebSocket
picks can be compared without logging either one.

It never logs an address, a header value, the salt, a ticket, a cookie or any
other header: the line is built only from fixed words, integers and hashes.
The salt is random per process, so hashes cannot be compared across restarts
and cannot be reversed by hashing candidate addresses offline.

/health is not counted: Render's own health checker may call it without
going through the proxy.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets

from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

import rate_limit

ENV_FLAG = "DIAG_FORWARDED_COUNT"
MAX_PER_KIND = 5
MAX_LINES = 2 * MAX_PER_KIND        # 10 per process
HTTP_PREFIXES = ("/api/", "/auth/")
WS_PATH = "/ws/threats"
HASH_CHARS = 6
NONE = "none"

logger = logging.getLogger("uvicorn.error")

# Random per process; never logged.
_SALT = secrets.token_bytes(16)

# Lines logged so far in this process, per kind, and the value tuples (hashes
# only) already logged, so repeated identical requests do not use up the cap.
_logged: dict[str, int] = {"http": 0, "ws": 0}
_seen: dict[str, set[tuple]] = {"http": set(), "ws": set()}


def enabled() -> bool:
    """On only for the exact value "true" (any case); off by default."""
    return os.environ.get(ENV_FLAG, "").strip().lower() == "true"


def short_hash(value: str | None) -> str:
    """First HASH_CHARS hex chars of HMAC-SHA256(_SALT, value); "none" if absent."""
    if value is None:
        return NONE
    return hmac.new(_SALT, value.encode(), hashlib.sha256).hexdigest()[:HASH_CHARS]


def _kind(scope: Scope) -> str | None:
    path = scope.get("path", "")
    if scope["type"] == "http" and path.startswith(HTTP_PREFIXES):
        return "http"
    if scope["type"] == "websocket" and path == WS_PATH:
        return "ws"
    return None


def _entry(entries: list[str], index: int) -> str | None:
    return entries[index] if len(entries) >= -index else None


def record(scope: Scope) -> None:
    kind = _kind(scope)
    if kind is None or _logged[kind] >= MAX_PER_KIND:
        return
    entries = rate_limit.forwarded_entries(HTTPConnection(scope))
    client = scope.get("client")
    peer_hash = short_hash(client[0] if client else None)
    if kind == "http":
        values = (len(entries), short_hash(_entry(entries, -2)), short_hash(_entry(entries, -1)), peer_hash)
    else:
        values = (len(entries), short_hash(_entry(entries, -1)), peer_hash)
    if values in _seen[kind]:
        return
    _seen[kind].add(values)
    _logged[kind] += 1
    line = (sum(_logged.values()), MAX_LINES)
    if kind == "http":
        logger.info(
            "[diag] forwarded-hash kind=http entries=%d pick=-2 pick_hash=%s last_hash=%s peer_hash=%s "
            "hops=%d line=%d/%d",
            *values, rate_limit.TRUSTED_PROXY_HOPS_HTTP, *line,
        )
    else:
        logger.info(
            "[diag] forwarded-hash kind=ws entries=%d pick=-1 pick_hash=%s peer_hash=%s hops=%d line=%d/%d",
            *values, rate_limit.TRUSTED_PROXY_HOPS_WS, *line,
        )


class ForwardedHashDiagnostic:
    """TEMPORARY. Pass-through ASGI middleware; reads the flag once, when the
    middleware stack is built at startup."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.enabled = enabled()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.enabled and scope["type"] in ("http", "websocket"):
            record(scope)
        await self.app(scope, receive, send)
