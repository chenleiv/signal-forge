"""Typed request bodies. Unknown fields, wrong types and oversized strings
are rejected with 422 before a route runs.

The models check shape and size only. Rules that need the stored state or
the caller (permissions, playbook task indexes, password policy, note
trimming) stay in the routes and keep their messages. Where a permission
check must answer before validation (a non-owner gets 403, not a 422 that
describes the data), the field is typed loosely and the route validates it.
"""
from __future__ import annotations
from typing import Any, ClassVar, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

MAX_NAME = 100
MAX_SHORT = 64
MAX_PASSWORD = 256     # policy (12-72 bytes) is checked by users.password_problem
MAX_COMMAND = 1000     # the console answers "too long" past 100 itself
MAX_CONDITIONS = 20


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Patch(_Body):
    """A partial update: send only what changes. An explicit null is refused
    for every field not listed in `nullable`."""
    nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _no_nulls(self):
        for name in self.model_fields_set:
            if getattr(self, name) is None and name not in self.nullable:
                raise ValueError(f"{name} cannot be null")
        return self

    def changes(self) -> dict:
        return self.model_dump(exclude_unset=True)


# ── Auth ──────────────────────────────────────────────────────

class LoginBody(BaseModel):
    """Loose on purpose: any malformed login gets the same 401 as a wrong
    password (the route checks types and sizes), never a 422 that tells a
    guesser what is wrong."""
    username: Any = ""
    password: Any = ""

    def credentials(self) -> tuple[str, str]:
        u, p = self.username, self.password
        if (not isinstance(u, str) or not isinstance(p, str)
                or len(u) > MAX_SHORT or len(p) > MAX_PASSWORD):
            return "", ""
        return u, p


class OwnPasswordBody(_Body):
    current_password: StrictStr = Field(max_length=MAX_PASSWORD)
    new_password: StrictStr = Field(max_length=MAX_PASSWORD)


# ── Alerts ────────────────────────────────────────────────────

class AlertPatch(_Body):
    status: Literal["acknowledged", "dismissed"]


# ── Behavioral settings ───────────────────────────────────────

class BehavioralPatch(_Patch):
    """Ranges (and "at least one field") are checked by the route against
    constants.BEHAVIORAL_LIMITS."""
    repeated_threshold: Optional[StrictInt] = None
    escalation_delta: Optional[StrictInt] = None
    cooldown_min: Optional[StrictInt] = None


# ── Hunting ───────────────────────────────────────────────────

class HuntQuery(_Body):
    ip: Optional[StrictStr] = Field(None, max_length=MAX_SHORT)
    attack_type: Optional[StrictStr] = Field(None, max_length=MAX_SHORT)
    region: Optional[StrictStr] = Field(None, max_length=MAX_SHORT)
    min_score: Optional[int] = Field(None, ge=0, le=100)
    max_score: Optional[int] = Field(None, ge=0, le=100)


class SavedHuntBody(_Body):
    name: StrictStr = Field("Unnamed hunt", max_length=MAX_NAME)
    query: HuntQuery = Field(default_factory=HuntQuery)
    result_count: StrictInt = Field(0, ge=0)


# ── Rules ─────────────────────────────────────────────────────
# Rules run on every event in the live stream: a malformed condition used
# to reach the evaluator. Field, operator and action are closed sets.

RuleField = Literal["score", "attack_type", "region", "ip"]
RuleOperator = Literal[">", "<", "=", "contains"]
RuleAction = Literal["alert", "incident", "block"]
RuleValue = Union[StrictInt, StrictFloat, StrictStr]


class RuleCondition(_Body):
    field: RuleField
    operator: RuleOperator
    value: RuleValue

    @model_validator(mode="after")
    def _short_value(self):
        if isinstance(self.value, str) and len(self.value) > MAX_SHORT:
            raise ValueError(f"value is limited to {MAX_SHORT} characters")
        return self


class RuleCreate(_Body):
    name: StrictStr = Field("Unnamed Rule", max_length=MAX_NAME)
    enabled: StrictBool = True
    conditions: list[RuleCondition] = Field(default_factory=list, max_length=MAX_CONDITIONS)
    logic: Literal["AND", "OR"] = "AND"
    actions: list[RuleAction] = Field(default_factory=lambda: ["alert"], max_length=3)


class RulePatch(_Patch):
    name: Optional[StrictStr] = Field(None, max_length=MAX_NAME)
    enabled: Optional[StrictBool] = None
    conditions: Optional[list[RuleCondition]] = Field(None, max_length=MAX_CONDITIONS)
    logic: Optional[Literal["AND", "OR"]] = None
    actions: Optional[list[RuleAction]] = Field(None, max_length=3)

    def changes(self) -> dict:
        # Conditions go back to plain dicts, as the evaluator expects.
        return self.model_dump(exclude_unset=True, mode="json")


# ── Incidents ─────────────────────────────────────────────────

class IncidentPatch(_Patch):
    """Values are checked by authz.check_incident_patch, with the caller's
    permissions, so status is not a Literal here."""
    nullable: ClassVar[frozenset[str]] = frozenset({"assigned_to"})  # null unassigns
    status: Optional[StrictStr] = Field(None, max_length=MAX_SHORT)
    assigned_to: Optional[StrictStr] = Field(None, max_length=MAX_SHORT)


class IncidentFromIp(_Body):
    ip: StrictStr = Field(max_length=MAX_SHORT)


class TasksBody(_Body):
    # Any on purpose: a non-owner must get 403 before the value is judged.
    completed_tasks: Any


class NoteBody(BaseModel):
    # Unknown fields are ignored, not refused: a client-sent "author" is
    # dropped and the session user is the author (tests/test_security.py).
    # Length is checked after trimming (MAX_NOTE_LENGTH); the body limit
    # bounds the raw size.
    model_config = ConfigDict(extra="ignore")
    text: StrictStr


# ── Users ─────────────────────────────────────────────────────

class UserCreate(_Body):
    """Format and policy errors keep their messages (user_admin.create_user)."""
    username: StrictStr = Field(max_length=MAX_SHORT)
    display_name: StrictStr = Field(max_length=MAX_NAME * 2)
    role: StrictStr = Field(max_length=MAX_SHORT)
    password: StrictStr = Field(max_length=MAX_PASSWORD)


class UserPatch(_Patch):
    role: Optional[StrictStr] = Field(None, max_length=MAX_SHORT)
    password: Optional[StrictStr] = Field(None, max_length=MAX_PASSWORD)


# ── Console ───────────────────────────────────────────────────

class CommandBody(_Body):
    command: StrictStr = Field("", max_length=MAX_COMMAND)
