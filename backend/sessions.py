"""Per-session revocation: logging out ends THIS session only.

Every session token carries a random session id ("sid"). Logging out puts
that id on a revocation list until the token would have expired anyway, so
a copied cookie stops working at once. Other sessions of the same user
(another device, or other visitors of a shared demo account) are untouched.

The list lives in memory (checked on every request by store.verify_token)
and, with a database, is persisted so a restart does not bring revoked
sessions back. One process only (README: single worker).
"""
from __future__ import annotations
import secrets
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from db_ops import db_load_revoked_sessions, db_revoke_session

# sid -> expiry (epoch seconds) of the revoked token
_revoked: dict[str, float] = {}


def new_session_id() -> str:
    return secrets.token_hex(16)


def is_revoked(sid: str) -> bool:
    return sid in _revoked


def _purge(now: float) -> None:
    """Expired tokens are rejected anyway; forget them."""
    for sid in [s for s, exp in _revoked.items() if exp <= now]:
        del _revoked[sid]


async def revoke_session(db: Optional[AsyncSession], sid: str, expires_at: float) -> None:
    now = time.time()
    _purge(now)
    if expires_at <= now:
        return
    _revoked[sid] = expires_at   # effective at once, before any await
    if db is not None:
        try:
            await db_revoke_session(db, sid, datetime.fromtimestamp(expires_at, tz=timezone.utc))
        except Exception as exc:  # the in-memory revocation still holds until a restart
            print(f"[Sessions] Could not persist a logout: {type(exc).__name__}")


async def load_revoked_sessions(db: AsyncSession) -> None:
    """Startup: reload revocations that have not expired yet."""
    rows = await db_load_revoked_sessions(db)
    _revoked.clear()
    _revoked.update({sid: exp.timestamp() for sid, exp in rows})
    print(f"[Sessions] Loaded {len(_revoked)} revoked sessions")
