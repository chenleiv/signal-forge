from __future__ import annotations
import hashlib
import logging
import math
import os
import time

from limits import parse_many
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import HTTPConnection, Request
from starlette.responses import Response

# Number of reverse proxies in front of the app that append to
# X-Forwarded-For, per connection type: on Render, HTTP requests and WebSocket
# upgrades pass through a different number of proxies, so one value cannot fit
# both (docs/DECISIONS.md). 0 = ignore the header, use the socket address:
# only safe with uvicorn --no-proxy-headers or no proxy in front, since
# uvicorn's proxy headers handling can replace that address with a
# client-chosen header entry. Fewer entries than hops: every client shares
# one fixed key (fail closed). Default 1: the only value that cannot be
# spoofed on either path.
LEGACY_HOPS_VAR = "TRUSTED_PROXY_HOPS"

# The key for a request whose X-Forwarded-For has fewer entries than `hops`.
# Not an IP address, so it never equals a real client's key.
SHORT_CHAIN_KEY = "xff-short-chain"

_logger = logging.getLogger("uvicorn.error")
_short_chain_warned = False


def _hops_from_env(name: str) -> int:
    # An empty value (e.g. copied from .env.example) means "use the default".
    raw = os.environ.get(name, "").strip()
    try:
        hops = int(raw or "1")
    except ValueError:
        hops = -1
    if hops < 0:
        raise RuntimeError(f"{name} must be a non-negative integer")
    return hops


# The old single value is refused, never used as a fallback: a value right for
# one path is wrong for the other, and a stale one would silently keep it.
if os.environ.get("TRUSTED_PROXY_HOPS", "").strip():
    raise RuntimeError(
        f"{LEGACY_HOPS_VAR} was replaced by TRUSTED_PROXY_HOPS_HTTP and "
        f"TRUSTED_PROXY_HOPS_WS; remove {LEGACY_HOPS_VAR} and set those two"
    )

TRUSTED_PROXY_HOPS_HTTP = _hops_from_env("TRUSTED_PROXY_HOPS_HTTP")
TRUSTED_PROXY_HOPS_WS = _hops_from_env("TRUSTED_PROXY_HOPS_WS")


def forwarded_entries(request: HTTPConnection) -> list[str]:
    """Non-empty X-Forwarded-For entries over all header lines, in order.
    A client can send its own header lines; the proxies' entries are still
    last once all lines are joined in order."""
    return [
        e.strip()
        for line in request.headers.getlist("x-forwarded-for")
        for e in line.split(",")
        if e.strip()
    ]


def _warn_short_chain(variable: str, entries: int, hops: int) -> None:
    """Once per process. Counts and the variable name only: never an
    address or a header value."""
    global _short_chain_warned
    if _short_chain_warned:
        return
    _short_chain_warned = True
    _logger.warning(
        "X-Forwarded-For has %d entries, fewer than %s=%d; per-IP limits share one bucket",
        entries, variable, hops,
    )


def client_ip(request: HTTPConnection) -> str:
    """The client address as seen by the outermost trusted proxy. Works for
    HTTP requests and WebSocket handshakes alike (headers and client only).

    Each proxy APPENDS the address it received the request from, so only the
    rightmost `hops` entries are trustworthy; everything to their left is
    whatever the client chose to send. `hops` is TRUSTED_PROXY_HOPS_WS for
    WebSocket upgrades, else TRUSTED_PROXY_HOPS_HTTP.

    Fewer entries than `hops` (the proxy chain is not what was measured):
    SHORT_CHAIN_KEY, one bucket for everyone, and one warning per process.
    Never the socket address: uvicorn with FORWARDED_ALLOW_IPS='*' (as on
    Render) replaces it with the leftmost entry, which the client controls.
    With `hops` 0 the socket address is used; run uvicorn with
    --no-proxy-headers so it is the real TCP peer.
    """
    websocket = request.scope["type"] == "websocket"
    hops = TRUSTED_PROXY_HOPS_WS if websocket else TRUSTED_PROXY_HOPS_HTTP
    if not hops:
        return get_remote_address(request)
    entries = forwarded_entries(request)
    if len(entries) >= hops:
        return entries[-hops]
    _warn_short_chain("TRUSTED_PROXY_HOPS_WS" if websocket else "TRUSTED_PROXY_HOPS_HTTP", len(entries), hops)
    return SHORT_CHAIN_KEY


# Shared by main.py and the routers (a limiter defined in main.py cannot be
# imported by routers without a circular import).
limiter = Limiter(key_func=client_ip)

# Per-IP limits for state-changing routes. Far above what a person clicking
# in the UI sends; they cap scripted floods of writes.
WRITE_LIMIT = "30/minute"
ADMIN_WRITE_LIMIT = "20/minute"

# Per-IP limits for reads. Pages poll (alerts every 15 s, incidents every
# 30 s, the feed status every minute) and every page load reads /auth/me and
# /api/config; the busiest e2e pass sends at most 45 of one route in under a
# minute (docs/DECISIONS.md). READ_LIMIT: in-memory reads and the public
# /api/config. DB_READ_LIMIT: reads that query the database when
# DATABASE_URL is set.
READ_LIMIT = "120/minute"
DB_READ_LIMIT = "60/minute"


def seconds_until(reset_time: float) -> int:
    """Whole seconds until `reset_time` (epoch), at least 1: the value of a
    Retry-After header."""
    return max(1, math.ceil(reset_time - time.time()))


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """slowapi's own 429 (same body), plus Retry-After: the seconds until the
    window that was hit has room again. slowapi's `headers_enabled` is not
    used: it would need a `response` parameter on every limited route."""
    response = _rate_limit_exceeded_handler(request, exc)
    current = getattr(request.state, "view_rate_limit", None)
    if current is not None:
        stats = limiter.limiter.get_window_stats(current[0], *current[1])
        response.headers["Retry-After"] = str(seconds_until(stats.reset_time))
    return response


class KeyedLimit:
    """A rate limit on an application key (username, ...) rather than on the
    client IP. Callers decide what counts: check `exceeded` before the action,
    `hit` when it should count. In-memory: per process.

    Every instance owns a unique namespace, and the namespace is part of every
    storage key, so two limits never share a counter, even with equal rates.
    Reusing a namespace fails at import time."""

    _storage = MemoryStorage()
    _limiter = FixedWindowRateLimiter(_storage)
    _namespaces: set[str] = set()

    def __init__(self, namespace: str, limits: str):
        if not namespace or namespace in KeyedLimit._namespaces:
            raise ValueError(f"rate limit namespace {namespace!r} is empty or already in use")
        KeyedLimit._namespaces.add(namespace)
        self.namespace = namespace
        self.items = parse_many(limits)

    def exceeded(self, key: str) -> bool:
        return not all(self._limiter.test(i, self.namespace, key[:64]) for i in self.items)

    def hit(self, key: str) -> None:
        for item in self.items:
            self._limiter.hit(item, self.namespace, key[:64])

    def retry_after(self, key: str) -> int:
        """Seconds until every exceeded window of `key` has room again (the
        longest wait when several are full), at least 1."""
        waits = [
            self._limiter.get_window_stats(i, self.namespace, key[:64]).reset_time
            for i in self.items
            if not self._limiter.test(i, self.namespace, key[:64])
        ]
        return seconds_until(max(waits)) if waits else 1


# ── Per-account login limit ───────────────────────────────────
# Independent of IP, so a distributed brute force against one account is
# capped too. Counts FAILED attempts only (unknown usernames included, so the
# limit does not reveal which accounts exist). Trade-off: anyone can lock an
# account out for the window by failing on purpose.
LOGIN_FAILURES_PER_USER = KeyedLimit("login-user", "10/minute;100/hour")

# ── Per-user case creation limit ──────────────────────────────
# Counts NEW cases only (reopening an existing open case is free). Keeps one
# user from flooding the incident list; in memory only 50 incidents are kept.
CASES_PER_USER = KeyedLimit("case-user", "5/minute;30/hour")

# ── Per-user wrong current password (self-service password change) ──
# Stops a stolen session from brute-forcing the account's current password.
PASSWORD_CHANGE_FAILURES = KeyedLimit("password-change", "5/minute;20/hour")

# ── Quotas for external lookups (AbuseIPDB, ipinfo, Groq) ─────
# Keyed by user AND client IP together (`user_ip_key`): the public demo
# accounts are shared, so one visitor cannot use up another's quota. Counted
# only when the request will call the service (not cached, key configured),
# before the call, so a failed or slow call still counts. The per-IP route
# limits still apply on top. AI summaries also have one daily cap for the
# whole server, to bound Groq cost across many users and addresses.
AI_SUMMARY_PER_USER_IP = KeyedLimit("ai-summary-user-ip", "5/minute;50/day")
AI_SUMMARY_GLOBAL = KeyedLimit("ai-summary-global", "500/day")
GEO_PER_USER_IP = KeyedLimit("geo-user-ip", "20/minute;300/day")
HISTORY_PER_USER_IP = KeyedLimit("history-user-ip", "20/minute;300/day")
GLOBAL_KEY = "all"


def user_ip_key(username: str, request: HTTPConnection) -> str:
    """The quota key for one user at one client address. A SHA-256 hex digest
    is exactly KeyedLimit's 64-character key, so a long username never cuts
    the address off, and no address is held in memory as text."""
    return hashlib.sha256(f"{username}\0{client_ip(request)}".encode()).hexdigest()


def login_locked(username: str) -> bool:
    return LOGIN_FAILURES_PER_USER.exceeded(username)


def login_retry_after(username: str) -> int:
    return LOGIN_FAILURES_PER_USER.retry_after(username)


def record_login_failure(username: str) -> None:
    LOGIN_FAILURES_PER_USER.hit(username)


def reset_limits() -> None:
    limiter.reset()
    KeyedLimit._storage.reset()
