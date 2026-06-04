from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, Boolean, ForeignKey, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
    repeated_threshold:    Mapped[int]      = mapped_column(Integer, nullable=False, default=8)
    escalation_delta:      Mapped[int]      = mapped_column(Integer, nullable=False, default=20)
    cooldown_min:          Mapped[int]      = mapped_column(Integer, nullable=False, default=30)
    created_at:            Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at:            Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
