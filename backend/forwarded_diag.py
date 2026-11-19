"""TEMPORARY DIAGNOSTIC: remove once TRUSTED_PROXY_HOPS is verified on Render.
See docs/DECISIONS.md, "Temporary X-Forwarded-For count diagnostic".

Off unless DIAG_FORWARDED_COUNT=true (set in the Render dashboard, then
removed). When on, it logs one short line for each of the first
MAX_PER_KIND API requests (/api/, /auth/) and the first MAX_PER_KIND
WebSocket upgrades to /ws/threats: the request kind, whether X-Forwarded-For
is present, how many comma-separated entries it has (counted like
rate_limit.client_ip), and TRUSTED_PROXY_HOPS. At most MAX_LINES lines per
process.

It never logs an address, a header value, a ticket, a cookie or any other
header: the line is built only from fixed words and integers.

/health is not counted: Render's own health checker may call it without
going through the proxy, which would log a misleading "absent".
"""
from __future__ import annotations

import logging
import os
from typing import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send

import rate_limit

ENV_FLAG = "DIAG_FORWARDED_COUNT"
MAX_PER_KIND = 5
MAX_LINES = 2 * MAX_PER_KIND        # 10 per process
HTTP_PREFIXES = ("/api/", "/auth/")
WS_PATH = "/ws/threats"

logger = logging.getLogger("uvicorn.error")

# Lines logged so far in this process, per kind.
_logged: dict[str, int] = {"http": 0, "ws": 0}


def enabled() -> bool:
    """On only for the exact value "true" (any case); off by default."""
    return os.environ.get(ENV_FLAG, "").strip().lower() == "true"


def forwarded_entry_count(headers: Iterable[tuple[bytes, bytes]]) -> int | None:
    """Non-empty comma-separated X-Forwarded-For entries over all header
    lines; None when the header is absent. Only the count leaves here."""
    lines = [value for name, value in headers if name.lower() == b"x-forwarded-for"]
    if not lines:
        return None
    return sum(1 for line in lines for entry in line.split(b",") if entry.strip())


def _kind(scope: Scope) -> str | None:
    path = scope.get("path", "")
    if scope["type"] == "http" and path.startswith(HTTP_PREFIXES):
        return "http"
    if scope["type"] == "websocket" and path == WS_PATH:
        return "ws"
    return None


def record(scope: Scope) -> None:
    kind = _kind(scope)
    if kind is None or _logged[kind] >= MAX_PER_KIND:
        return
    _logged[kind] += 1
    count = forwarded_entry_count(scope.get("headers", []))
    logger.info(
        "[diag] forwarded-count kind=%s xff=%s entries=%d trusted_proxy_hops=%d line=%d/%d",
        kind, "present" if count is not None else "absent", count or 0,
        rate_limit.TRUSTED_PROXY_HOPS, sum(_logged.values()), MAX_LINES,
    )


class ForwardedCountDiagnostic:
    """TEMPORARY. Pass-through ASGI middleware; reads the flag once, when the
    middleware stack is built at startup."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.enabled = enabled()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.enabled and scope["type"] in ("http", "websocket"):
            record(scope)
        await self.app(scope, receive, send)
