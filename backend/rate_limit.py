from __future__ import annotations
import os

from limits import parse_many
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

# Number of reverse proxies in front of the app that append to
# X-Forwarded-For (Render: 1). 0 = ignore the header, use the socket address.
try:
    # An empty value (e.g. copied from .env.example) means "use the default".
    TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS") or "1")
except ValueError:
    TRUSTED_PROXY_HOPS = -1
if TRUSTED_PROXY_HOPS < 0:
    raise RuntimeError("TRUSTED_PROXY_HOPS must be a non-negative integer")


def client_ip(request: Request) -> str:
    """The client address as seen by the outermost trusted proxy.

    Each proxy APPENDS the address it received the request from, so only the
    rightmost TRUSTED_PROXY_HOPS entries are trustworthy; everything to their
    left is whatever the client chose to send. (uvicorn --forwarded-allow-ips='*'
    takes the leftmost entry, which the client controls.)
    """
    if TRUSTED_PROXY_HOPS:
        # A client can also send its own X-Forwarded-For header lines; the
        # proxy's entry is still last once all lines are joined in order.
        entries = [
            e.strip()
            for line in request.headers.getlist("x-forwarded-for")
            for e in line.split(",")
            if e.strip()
        ]
        if len(entries) >= TRUSTED_PROXY_HOPS:
            return entries[-TRUSTED_PROXY_HOPS]
    return get_remote_address(request)


# Shared by main.py and the routers (a limiter defined in main.py cannot be
# imported by routers without a circular import).
limiter = Limiter(key_func=client_ip)


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


def login_locked(username: str) -> bool:
    return LOGIN_FAILURES_PER_USER.exceeded(username)


def record_login_failure(username: str) -> None:
    LOGIN_FAILURES_PER_USER.hit(username)


def reset_limits() -> None:
    limiter.reset()
    KeyedLimit._storage.reset()
