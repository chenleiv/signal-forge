from __future__ import annotations
import os

from limits import parse_many
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import HTTPConnection

# Number of reverse proxies in front of the app that append to
# X-Forwarded-For, per connection type: on Render, HTTP requests and WebSocket
# upgrades pass through a different number of proxies, so one value cannot fit
# both (docs/DECISIONS.md). 0 = ignore the header, use the socket address.
# Default 1: the only value that cannot be spoofed on either path.
LEGACY_HOPS_VAR = "TRUSTED_PROXY_HOPS"


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


def client_ip(request: HTTPConnection) -> str:
    """The client address as seen by the outermost trusted proxy. Works for
    HTTP requests and WebSocket handshakes alike (headers and client only).

    Each proxy APPENDS the address it received the request from, so only the
    rightmost `hops` entries are trustworthy; everything to their left is
    whatever the client chose to send. (uvicorn --forwarded-allow-ips='*'
    takes the leftmost entry, which the client controls.) `hops` is
    TRUSTED_PROXY_HOPS_WS for WebSocket upgrades, else TRUSTED_PROXY_HOPS_HTTP.
    """
    hops = TRUSTED_PROXY_HOPS_WS if request.scope["type"] == "websocket" else TRUSTED_PROXY_HOPS_HTTP
    if hops:
        entries = forwarded_entries(request)
        if len(entries) >= hops:
            return entries[-hops]
    return get_remote_address(request)


# Shared by main.py and the routers (a limiter defined in main.py cannot be
# imported by routers without a circular import).
limiter = Limiter(key_func=client_ip)

# Per-IP limits for state-changing routes. Far above what a person clicking
# in the UI sends; they cap scripted floods of writes.
WRITE_LIMIT = "30/minute"
ADMIN_WRITE_LIMIT = "20/minute"


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


def login_locked(username: str) -> bool:
    return LOGIN_FAILURES_PER_USER.exceeded(username)


def record_login_failure(username: str) -> None:
    LOGIN_FAILURES_PER_USER.hit(username)


def reset_limits() -> None:
    limiter.reset()
    KeyedLimit._storage.reset()
