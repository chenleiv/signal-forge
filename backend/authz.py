"""Authorization rules: the single place that decides who may do what.

Routers call these; no role checks anywhere else. The permission matrix
(analyst / manager / admin) is testing/permission-matrix.json.

- admin:   everything. There is exactly ONE admin: the account cannot be
           deleted, and the admin role can never be granted or removed.
- manager: works on and assigns any incident; resets analysts' passwords
- analyst: works on own incidents, takes unassigned ones
"""
from __future__ import annotations
from typing import Optional

from fastapi import Depends, HTTPException

from store import verify_token
from users import CurrentUser, get_user

INCIDENT_STATUSES = ("open", "investigating", "contained", "closed")

# Roles that work on and assign any incident.
INCIDENT_LEADS = ("admin", "manager")

MANAGER_RESET_ONLY = "Managers can only reset analysts' passwords"
ADMIN_ROLE_FIXED = "There is exactly one admin: the admin role cannot be granted or removed"
ADMIN_UNDELETABLE = "The admin account cannot be deleted"

_UNSET = object()


def require_admin(user: CurrentUser = Depends(verify_token)) -> CurrentUser:
    # verify_token runs first, so a missing/invalid session is still a 401.
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def can_work_on_incident(user: CurrentUser, incident: dict) -> bool:
    return user.role in INCIDENT_LEADS or incident.get("assigned_to") == user.username


def check_work_on_incident(user: CurrentUser, incident: dict) -> None:
    """Status, notes and tasks: the assignee, a manager or an admin."""
    if not can_work_on_incident(user, incident):
        raise HTTPException(
            status_code=403, detail="Only the assignee, a manager or an admin can change this incident"
        )


def check_assignment(user: CurrentUser, incident: dict, new_assignee: object) -> None:
    """Admins and managers assign anyone (or no one). Analysts only take
    unassigned incidents for themselves."""
    if new_assignee is not None and (not isinstance(new_assignee, str) or get_user(new_assignee) is None):
        raise HTTPException(status_code=422, detail="assigned_to must be an existing user")
    if user.role in INCIDENT_LEADS:
        return
    if incident.get("assigned_to") is None and new_assignee == user.username:
        return
    raise HTTPException(
        status_code=403, detail="Analysts can only take unassigned incidents for themselves"
    )


def check_incident_patch(user: CurrentUser, incident: dict, body: dict) -> dict:
    """Validate and authorize a PATCH /api/incidents/{id} body against the
    incident's CURRENT state. Every field is checked; if any check fails the
    whole request is rejected. Returns the fields to apply.

    An `assigned_to` equal to the current value is a no-op (clients may send
    the whole object back) and needs no permission; other fields still do.
    """
    patch: dict = {}

    status = body.get("status", _UNSET)
    if status is not _UNSET:
        if status not in INCIDENT_STATUSES:
            raise HTTPException(
                status_code=422, detail=f"status must be one of: {', '.join(INCIDENT_STATUSES)}"
            )
        check_work_on_incident(user, incident)
        patch["status"] = status

    new_assignee = body.get("assigned_to", _UNSET)
    if new_assignee is not _UNSET and new_assignee != incident.get("assigned_to"):
        check_assignment(user, incident, new_assignee)
        patch["assigned_to"] = new_assignee

    return patch


def check_user_update(actor: CurrentUser, target: Optional[dict], body: dict) -> dict:
    """Who may change which user fields (PATCH /api/users/{username}).
    Returns the target record.

    - admin:   role and password of any user, except that the admin role is
               never granted or removed
    - manager: only the password of an analyst (a reset, nothing else)
    - analyst: nothing

    Analysts are refused before the lookup, so they learn nothing from it.
    """
    if actor.role not in INCIDENT_LEADS:
        raise HTTPException(status_code=403, detail="Admin role required")
    if target is None or target.get("deleted_at"):
        raise HTTPException(status_code=404, detail="User not found")
    if actor.role == "manager" and not (set(body) == {"password"} and target["role"] == "analyst"):
        raise HTTPException(status_code=403, detail=MANAGER_RESET_ONLY)
    new_role = body.get("role", target["role"])
    if new_role != target["role"] and "admin" in (new_role, target["role"]):
        raise HTTPException(status_code=403, detail=ADMIN_ROLE_FIXED)
    return target


def check_user_create(body: dict) -> None:
    """POST /api/users (already admin-only): nobody is created as an admin."""
    if body.get("role") == "admin":
        raise HTTPException(status_code=403, detail=ADMIN_ROLE_FIXED)


def check_user_delete(target: Optional[dict]) -> dict:
    """DELETE /api/users/{username} (already admin-only): never the admin."""
    if target is None or target.get("deleted_at"):
        raise HTTPException(status_code=404, detail="User not found")
    if target["role"] == "admin":
        raise HTTPException(status_code=403, detail=ADMIN_UNDELETABLE)
    return target
