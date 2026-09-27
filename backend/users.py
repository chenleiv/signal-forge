"""User accounts: in-memory store, bcrypt hashing and startup seeding.

`_users` is always the source of truth at runtime. With a database, startup
syncs it with the `users` table (see `sync_users_with_db`).
"""
from __future__ import annotations
import hmac
import re
import secrets
from dataclasses import dataclass
from functools import cache
from typing import Literal

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from db_ops import db_get_users, db_create_user, db_update_user

Role = Literal["admin", "manager", "analyst"]
ROLES: tuple[Role, ...] = ("admin", "manager", "analyst")
# There is exactly one admin (the bootstrap account). Every other account is
# a manager or an analyst; the admin role can never be granted or removed.
ASSIGNABLE_ROLES: tuple[Role, ...] = ("manager", "analyst")
ADMIN_USERNAME = "admin"

BCRYPT_ROUNDS = 12
_BCRYPT_MAX_BYTES = 72  # bcrypt ignores (5.x: rejects) anything longer
MIN_PASSWORD_BYTES = 12

USERNAME_RE = re.compile(r"^[a-z0-9-]{3,50}$")

# Public demo accounts, shown on the login page. Seeded ONLY in demo mode.
DEMO_USERS: list[tuple[str, str, Role, str]] = [
    ("admin", "Sarah Kim",    "admin",   "admin-demo"),
    ("alice", "Alice Chen",   "analyst", "alice-demo"),
    ("bob",   "Bob Martinez", "manager", "bob-demo"),
]
_DEMO_PASSWORDS = {u: pw for u, _, _, pw in DEMO_USERS}
DEMO_USERNAMES = frozenset(_DEMO_PASSWORDS)


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated caller, taken from a verified session token."""
    username: str
    role: Role


# username -> {username, display_name, role, password_hash, session_key, deleted_at}
# Soft-deleted users stay here (deleted_at set) so history can show their
# name; every lookup used for login, sessions or assignment skips them.
_users: dict[str, dict] = {}


# ── Passwords ─────────────────────────────────────────────────

def password_problem(password: object) -> str | None:
    """The one password rule (ADMIN_PASSWORD, new users, resets): 12-72 bytes."""
    if not isinstance(password, str):
        return "Password is required"
    if not MIN_PASSWORD_BYTES <= len(password.encode()) <= _BCRYPT_MAX_BYTES:
        return f"Password must be {MIN_PASSWORD_BYTES}-{_BCRYPT_MAX_BYTES} bytes long"
    return None


def new_session_key() -> str:
    return secrets.token_hex(16)


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
    user = get_user(username)  # active users only; a deleted one looks unknown
    if not verify_password(password, user["password_hash"] if user else None):
        return None
    return CurrentUser(username=user["username"], role=user["role"])


# ── Lookups ───────────────────────────────────────────────────

def public_user(user: dict) -> dict:
    """Never expose the password hash."""
    return {"username": user["username"], "display_name": user["display_name"], "role": user["role"]}


def get_user(username: str) -> dict | None:
    """An ACTIVE user: the only kind that can log in, hold a session or be assigned."""
    user = _users.get(username)
    return user if user and not user.get("deleted_at") else None


def get_user_record(username: str) -> dict | None:
    """Any user, including soft-deleted ones (admin operations, history)."""
    return _users.get(username)


def list_users() -> list[dict]:
    return [public_user(u) for u in _users.values() if not u.get("deleted_at")]


def user_directory() -> list[dict]:
    """Every name ever used, for showing history (no roles, no secrets)."""
    return [{"username": u["username"], "display_name": u["display_name"], "deleted": bool(u.get("deleted_at"))}
            for u in _users.values()]


def analyst_usernames() -> list[str]:
    return [u["username"] for u in _users.values() if u["role"] == "analyst" and not u.get("deleted_at")]


def is_session_current(username: str, role: str, session_key: object) -> bool:
    """A session is valid only while its user is active, still has the role in
    the token, and still has the session key in the token (rotated on password
    reset and role change). Checked on every request."""
    user = get_user(username)
    return (
        user is not None
        and user["role"] == role
        and isinstance(session_key, str)
        and bool(user.get("session_key"))
        and hmac.compare_digest(user["session_key"], session_key)
    )


def add_user(username: str, display_name: str, role: Role, password: str) -> dict:
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    user = {
        "username": username,
        "display_name": display_name,
        "role": role,
        "password_hash": hash_password(password),
        "session_key": new_session_key(),
        "deleted_at": None,
    }
    _users[username] = user
    return user


# ── Seeding ───────────────────────────────────────────────────

def seed_users(demo_mode: bool, admin_password: str) -> None:
    """Demo mode: the public demo accounts. Otherwise only `admin`, with the
    operator-supplied ADMIN_PASSWORD, never an account with a known password.

    Outside demo mode ADMIN_PASSWORD only BOOTSTRAPS the admin: with a database,
    an existing admin keeps the password it has (it can be changed in the app),
    and the variable can be removed once the admin exists."""
    _users.clear()
    if demo_mode:
        for username, display_name, role, password in DEMO_USERS:
            add_user(username, display_name, role, password)
    elif admin_password:
        add_user(ADMIN_USERNAME, "Sarah Kim", "admin", admin_password)


async def sync_users_with_db(session: AsyncSession, demo_mode: bool, admin_password: str) -> None:
    """Persist the seeded users and load the table into memory.

    - Seeded users missing from the table are created.
    - Demo mode: the admin always has the public demo password.
      Otherwise the admin is created from ADMIN_PASSWORD only if the table has
      no admin yet; an existing admin's REAL password is never overwritten.
    - Outside demo mode, an admin that still has the public demo password
      (left over from a demo deployment on the same DB) gets ADMIN_PASSWORD
      instead; without ADMIN_PASSWORD, startup fails. A real deployment must
      never run with an admin whose password is shown on the login page.
    - Outside demo mode, rows still holding a public demo password (left over
      from a demo deployment on the same DB) are not loaded: they cannot log in.
    - Rows without a session key get one.
    - Soft-deleted rows are loaded too (history shows their names).
    """
    rows = {r["username"]: r for r in await db_get_users(session)}
    table_has_admin = any(r["role"] == "admin" and not r.get("deleted_at") for r in rows.values())

    for username, seeded in _users.items():
        row = rows.get(username)
        if row is None:
            if seeded["role"] == "admin" and table_has_admin:
                continue  # never a second admin
            rows[username] = await db_create_user(session, seeded)
        elif demo_mode and username == ADMIN_USERNAME \
                and not verify_password(_DEMO_PASSWORDS["admin"], row["password_hash"]):
            fields = {"password_hash": seeded["password_hash"], "session_key": new_session_key()}
            await db_update_user(session, username, fields)
            row.update(fields)

    admins = [u for u, r in rows.items() if r["role"] == "admin" and not r.get("deleted_at")]

    if not demo_mode:
        for username in admins:
            row = rows[username]
            if not verify_password(_DEMO_PASSWORDS["admin"], row["password_hash"]):
                continue  # a real password: never touched
            if not admin_password:
                raise RuntimeError(
                    f"Admin '{username}' still has the public demo password: "
                    "set ADMIN_PASSWORD (12-72 bytes) to replace it"
                )
            # A new key also signs out every session opened with the demo password.
            fields = {"password_hash": hash_password(admin_password), "session_key": new_session_key()}
            await db_update_user(session, username, fields)
            row.update(fields)
            print(f"[Users] Replaced the public demo password of admin '{username}' with ADMIN_PASSWORD")

    if not admins:
        raise RuntimeError("No admin account exists: set ADMIN_PASSWORD (12-72 bytes) to create it")
    if len(admins) > 1:
        # Fail closed: the single-admin rule must hold before serving requests.
        raise RuntimeError(f"Exactly one admin is allowed, found {len(admins)}: change the others' role in the database")

    for username, row in rows.items():
        if not row.get("session_key"):
            row["session_key"] = new_session_key()
            await db_update_user(session, username, {"session_key": row["session_key"]})

    if not demo_mode:
        for username, demo_pw in _DEMO_PASSWORDS.items():
            row = rows.get(username)
            if username != "admin" and row and not row.get("deleted_at") and verify_password(demo_pw, row["password_hash"]):
                print(f"[Users] Not loading '{username}': it still has the public demo password")
                del rows[username]

    _users.clear()
    _users.update(rows)
    print(f"[Users] Loaded {len(_users)} users")
