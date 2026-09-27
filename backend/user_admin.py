"""Admin user management: create, change role / reset password, soft delete.

Routers call these after `require_admin`. Every change is written to the
database (when there is one) and to the in-memory user store.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

import store as _store
from rate_limit import PASSWORD_CHANGE_FAILURES
from db_ops import db_create_user, db_unassign_open_incidents, db_update_user
from users import (
    ROLES, USERNAME_RE, CurrentUser, _users, get_user_record,
    hash_password, new_session_key, password_problem, public_user, verify_password,
)

_PATCH_FIELDS = {"role", "password"}
MAX_DISPLAY_NAME = 100

# Race safety: every change checks its rules and applies them to the in-memory
# store with NO await in between, and only then writes the database (undoing
# the in-memory change if that write fails). Two concurrent requests therefore
# never act on a state the other has already changed. One process only
# (README: single worker). Which changes are allowed at all (e.g. the single
# admin) is decided in authz.py before these run.


def _db(db: Optional[AsyncSession]) -> Optional[AsyncSession]:
    return db if _store.USE_DB and db is not None else None


def _require_existing(username: str) -> dict:
    user = get_user_record(username)
    if user is None or user.get("deleted_at"):
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _check_password(password: object) -> str:
    problem = password_problem(password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    return password  # type: ignore[return-value]


def _check_role(role: object) -> str:
    if role not in ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of: {', '.join(ROLES)}")
    return role  # type: ignore[return-value]


async def _apply(db: Optional[AsyncSession], user: dict, fields: dict) -> None:
    """Apply in memory first (no await since the rule checks), then persist;
    undo the in-memory change if the database write fails."""
    previous = {k: user.get(k) for k in fields}
    user.update(fields)
    if _db(db):
        try:
            await db_update_user(db, user["username"], fields)
        except Exception:
            user.update(previous)
            raise


async def create_user(db: Optional[AsyncSession], body: dict) -> dict:
    username = body.get("username")
    if not isinstance(username, str) or not USERNAME_RE.fullmatch(username):
        raise HTTPException(
            status_code=422,
            detail="username must be 3-50 characters: lowercase letters, digits and '-'",
        )
    display_name = body.get("display_name")
    if not isinstance(display_name, str) or not display_name.strip() or len(display_name.strip()) > MAX_DISPLAY_NAME:
        raise HTTPException(status_code=422, detail=f"display_name is required (max {MAX_DISPLAY_NAME} characters)")
    role = _check_role(body.get("role"))
    password = _check_password(body.get("password"))
    # Soft-deleted usernames stay taken: history must never point at a new person.
    if get_user_record(username) is not None:
        raise HTTPException(status_code=409, detail="Username is already taken")

    user = {
        "username": username,
        "display_name": display_name.strip(),
        "role": role,
        "password_hash": hash_password(password),
        "session_key": new_session_key(),
        "deleted_at": None,
    }
    _users[username] = user
    if _db(db):
        try:
            await db_create_user(db, user)
        except Exception:
            del _users[username]
            raise
    return public_user(user)


async def update_user(db: Optional[AsyncSession], username: str, body: dict) -> dict:
    """Change role and/or reset password. Only these two fields are accepted;
    username and display name cannot be changed here."""
    unknown = set(body) - _PATCH_FIELDS
    if unknown:
        raise HTTPException(status_code=422, detail=f"Only role and password can be changed (got: {', '.join(sorted(unknown))})")
    if not body:
        raise HTTPException(status_code=422, detail="Nothing to change")
    user = _require_existing(username)

    fields: dict = {}
    if "role" in body:
        role = _check_role(body["role"])
        if role != user["role"]:
            fields["role"] = role
    if "password" in body:
        fields["password_hash"] = hash_password(_check_password(body["password"]))
    if fields:
        # A new key signs out every session of this user.
        fields["session_key"] = new_session_key()
        await _apply(db, user, fields)
    return public_user(user)


async def delete_user(db: Optional[AsyncSession], actor: CurrentUser, username: str) -> None:
    """Soft delete: the user can no longer log in or be assigned, their open
    incidents become unassigned, and history keeps their name."""
    if username == actor.username:
        raise HTTPException(status_code=409, detail="You cannot delete your own account")
    user = _require_existing(username)

    fields = {"deleted_at": datetime.now(timezone.utc).isoformat(), "session_key": new_session_key()}
    await _apply(db, user, fields)
    if _db(db):
        await db_unassign_open_incidents(db, username)
    else:
        now = datetime.now(timezone.utc).isoformat()
        for inc in _store.incidents_store:
            if inc.get("assigned_to") == username and inc.get("status") != "closed":
                inc["assigned_to"] = None
                inc["updated_at"] = now


_OWN_PASSWORD_FIELDS = {"current_password", "new_password"}


async def change_own_password(db: Optional[AsyncSession], username: str, body: dict) -> dict:
    """Self-service password change (PATCH /auth/me).

    - The body is exactly {current_password, new_password}: anything else
      (role, username, ...) is a 422, never silently ignored.
    - The current password is verified like at login; wrong attempts are
      rate limited per user (a stolen session cannot brute-force it).
    - A new session key signs out every other session of the user; the
      caller re-issues the cookie for the session that made the change.
    """
    if set(body) != _OWN_PASSWORD_FIELDS:
        raise HTTPException(status_code=422, detail="Send exactly current_password and new_password")
    current, new = body["current_password"], body["new_password"]
    if not isinstance(current, str) or not isinstance(new, str):
        raise HTTPException(status_code=422, detail="Passwords must be strings")
    user = _require_existing(username)

    if PASSWORD_CHANGE_FAILURES.exceeded(username):
        raise HTTPException(status_code=429, detail="Too many attempts, try again later")
    if not await run_in_threadpool(verify_password, current, user["password_hash"]):
        PASSWORD_CHANGE_FAILURES.hit(username)
        raise HTTPException(status_code=403, detail="Current password is incorrect")

    _check_password(new)
    if new == current:
        raise HTTPException(status_code=422, detail="The new password must be different from the current one")
    fields = {"password_hash": await run_in_threadpool(hash_password, new), "session_key": new_session_key()}
    await _apply(db, user, fields)
    return public_user(user)
