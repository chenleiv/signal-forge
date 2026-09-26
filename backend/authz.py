"""Authorization rules: the single place that decides who may do what.

Routers call these; no role checks anywhere else. The permission matrix
(analyst vs admin) lives in the RBAC plan and is tested in tests/test_authz.py.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException

from store import verify_token
from users import CurrentUser, get_user

INCIDENT_STATUSES = ("open", "investigating", "contained", "closed")

_UNSET = object()


def require_admin(user: CurrentUser = Depends(verify_token)) -> CurrentUser:
    # verify_token runs first, so a missing/invalid session is still a 401.
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def can_work_on_incident(user: CurrentUser, incident: dict) -> bool:
    return user.role == "admin" or incident.get("assigned_to") == user.username


def check_work_on_incident(user: CurrentUser, incident: dict) -> None:
    """Status, notes and tasks: only the assignee or an admin."""
    if not can_work_on_incident(user, incident):
        raise HTTPException(
            status_code=403, detail="Only the assignee or an admin can change this incident"
        )


def check_assignment(user: CurrentUser, incident: dict, new_assignee: object) -> None:
    """Admins assign anyone (or no one). Analysts only take unassigned incidents for themselves."""
    if new_assignee is not None and (not isinstance(new_assignee, str) or get_user(new_assignee) is None):
        raise HTTPException(status_code=422, detail="assigned_to must be an existing user")
    if user.role == "admin":
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
