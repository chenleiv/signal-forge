"""User accounts: in-memory store, bcrypt hashing and startup seeding.

`_users` is always the source of truth at runtime. With a database, startup
syncs it with the `users` table (see `sync_users_with_db`).
"""
from __future__ import annotations
import secrets
from dataclasses import dataclass
from functools import cache
from typing import Literal

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from db_ops import db_get_users, db_create_user, db_set_password_hash

Role = Literal["admin", "analyst"]
ROLES: tuple[Role, ...] = ("admin", "analyst")

BCRYPT_ROUNDS = 12
_BCRYPT_MAX_BYTES = 72  # bcrypt ignores (5.x: rejects) anything longer

# Public demo accounts, shown on the login page. Seeded ONLY in demo mode.
DEMO_USERS: list[tuple[str, str, Role, str]] = [
    ("admin", "Sarah Kim",    "admin",   "admin-demo"),
    ("alice", "Alice Chen",   "analyst", "alice-demo"),
    ("bob",   "Bob Martinez", "analyst", "bob-demo"),
]
_DEMO_PASSWORDS = {u: pw for u, _, _, pw in DEMO_USERS}


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated caller, taken from a verified session token."""
    username: str
    role: Role


# username -> {username, display_name, role, password_hash}
_users: dict[str, dict] = {}


# ── Passwords ─────────────────────────────────────────────────

def hash_password(password: str) -> str:
    pw = password.encode()
    if len(pw) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"password longer than {_BCRYPT_MAX_BYTES} bytes")
    return bcrypt.hashpw(pw, bcrypt.gensalt(BCRYPT_ROUNDS)).decode()


@cache
def _dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(16))


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-time check. With no hash (unknown user) it still runs bcrypt
    against a dummy hash, so both failures take about the same time."""
    pw = password.encode()[:_BCRYPT_MAX_BYTES]
    ok = bcrypt.checkpw(pw, (password_hash or _dummy_hash()).encode())
    too_long = len(password.encode()) > _BCRYPT_MAX_BYTES
    return ok and password_hash is not None and not too_long


def authenticate(username: str, password: str) -> CurrentUser | None:
    user = _users.get(username)
    if not verify_password(password, user["password_hash"] if user else None):
        return None
    return CurrentUser(username=user["username"], role=user["role"])


# ── Lookups ───────────────────────────────────────────────────

def public_user(user: dict) -> dict:
    """Never expose the password hash."""
    return {"username": user["username"], "display_name": user["display_name"], "role": user["role"]}


def get_user(username: str) -> dict | None:
    return _users.get(username)


def list_users() -> list[dict]:
    return [public_user(u) for u in _users.values()]


def analyst_usernames() -> list[str]:
    return [u["username"] for u in _users.values() if u["role"] == "analyst"]


def add_user(username: str, display_name: str, role: Role, password: str) -> dict:
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    user = {
        "username": username,
        "display_name": display_name,
        "role": role,
        "password_hash": hash_password(password),
    }
    _users[username] = user
    return user


# ── Seeding ───────────────────────────────────────────────────

def seed_users(demo_mode: bool, admin_password: str) -> None:
    """Demo mode: the public demo accounts. Otherwise only `admin`, with the
    operator-supplied ADMIN_PASSWORD — never an account with a known password."""
    _users.clear()
    if demo_mode:
        for username, display_name, role, password in DEMO_USERS:
            add_user(username, display_name, role, password)
    else:
        add_user("admin", "Sarah Kim", "admin", admin_password)


async def sync_users_with_db(session: AsyncSession, demo_mode: bool, admin_password: str) -> None:
    """Persist the seeded users and load the table into memory.

    - Seeded users missing from the table are created.
    - The admin password is re-applied if it changed (demo password in demo
      mode, ADMIN_PASSWORD otherwise), so rotating the env var takes effect.
    - Outside demo mode, rows still holding a public demo password (left over
      from a demo deployment on the same DB) are not loaded: they cannot log in.
    """
    effective_admin_pw = _DEMO_PASSWORDS["admin"] if demo_mode else admin_password
    rows = {r["username"]: r for r in await db_get_users(session)}

    for username, seeded in _users.items():
        row = rows.get(username)
        if row is None:
            rows[username] = await db_create_user(session, seeded)
        elif username == "admin" and not verify_password(effective_admin_pw, row["password_hash"]):
            await db_set_password_hash(session, username, seeded["password_hash"])
            row["password_hash"] = seeded["password_hash"]

    if not demo_mode:
        for username, demo_pw in _DEMO_PASSWORDS.items():
            row = rows.get(username)
            if username != "admin" and row and verify_password(demo_pw, row["password_hash"]):
                print(f"[Users] Not loading '{username}': it still has the public demo password")
                del rows[username]

    _users.clear()
    _users.update(rows)
    print(f"[Users] Loaded {len(_users)} users")
