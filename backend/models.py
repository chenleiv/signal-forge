from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, Boolean, ForeignKey, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from constants import BEHAVIORAL_DEFAULTS
from database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id:            Mapped[str]           = mapped_column(String, primary_key=True)
    title:         Mapped[str]           = mapped_column(Text, nullable=False)
    status:        Mapped[str]           = mapped_column(String(20), nullable=False, default="open")
    severity:      Mapped[str]           = mapped_column(String(20), nullable=False)
    attack_type:   Mapped[str]           = mapped_column(String(50), nullable=False)
    source_ip:     Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    source_region: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    event_count:   Mapped[int]           = mapped_column(Integer, nullable=False, default=0)
    mitre_tags:    Mapped[str]           = mapped_column(Text, nullable=False, default="[]")
    assigned_to:   Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at:    Mapped[datetime]      = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at:    Mapped[datetime]      = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    notes:  Mapped[list[Note]]          = relationship("Note", back_populates="incident", cascade="all, delete-orphan")
    tasks:  Mapped[list[IncidentTask]]  = relationship("IncidentTask", back_populates="incident", cascade="all, delete-orphan")


class Note(Base):
    __tablename__ = "notes"

    id:          Mapped[str]      = mapped_column(String, primary_key=True)
    incident_id: Mapped[str]      = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    text:        Mapped[str]      = mapped_column(Text, nullable=False)
    author:      Mapped[str]      = mapped_column(String(100), nullable=False)
    created_at:  Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    incident: Mapped[Incident] = relationship("Incident", back_populates="notes")


class IncidentTask(Base):
    __tablename__ = "incident_tasks"

    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True)
    task_index:  Mapped[int] = mapped_column(Integer, primary_key=True)

    incident: Mapped[Incident] = relationship("Incident", back_populates="tasks")


class Rule(Base):
    __tablename__ = "rules"

    id:          Mapped[str]      = mapped_column(String(8), primary_key=True)
    name:        Mapped[str]      = mapped_column(Text, nullable=False)
    enabled:     Mapped[bool]     = mapped_column(Boolean, nullable=False, default=True)
    conditions:  Mapped[str]      = mapped_column(Text, nullable=False, default="[]")
    logic:       Mapped[str]      = mapped_column(String(3), nullable=False, default="AND")
    actions:     Mapped[str]      = mapped_column(Text, nullable=False, default="[]")
    match_count: Mapped[int]      = mapped_column(Integer, nullable=False, default=0)
    created_at:  Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class BehavioralSettings(Base):
    __tablename__ = "behavioral_settings"

    id:                    Mapped[int]      = mapped_column(Integer, primary_key=True)
    repeated_threshold:    Mapped[int]      = mapped_column(Integer, nullable=False, default=BEHAVIORAL_DEFAULTS["repeated_threshold"])
    escalation_delta:      Mapped[int]      = mapped_column(Integer, nullable=False, default=BEHAVIORAL_DEFAULTS["escalation_delta"])
    cooldown_min:          Mapped[int]      = mapped_column(Integer, nullable=False, default=BEHAVIORAL_DEFAULTS["cooldown_min"])
    created_at:            Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at:            Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class User(Base):
    __tablename__ = "users"

    username:      Mapped[str]      = mapped_column(String(50), primary_key=True)
    display_name:  Mapped[str]      = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str]      = mapped_column(String(100), nullable=False)
    role:          Mapped[str]      = mapped_column(String(10), nullable=False)
    created_at:    Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # Random per account; part of every session token. Rotating it signs out
    # all of the user's sessions (password reset, role change).
    session_key:   Mapped[Optional[str]]      = mapped_column(String(64), nullable=True)
    # Soft delete: the row stays so history keeps the name and the username
    # can never be reused; the user cannot log in or be assigned.
    deleted_at:    Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class RevokedSession(Base):
    """A logged-out session id, kept until its token would have expired."""
    __tablename__ = "revoked_sessions"

    sid:        Mapped[str]      = mapped_column(String(32), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
