from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db_ops import db_get_behavioral_settings, db_update_behavioral_settings
from store import _behavioral_config, verify_token, USE_DB
import store as _store

router = APIRouter()


@router.get("/api/behavioral/settings")
async def get_behavioral_settings(
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    if USE_DB and db is not None:
        return await db_get_behavioral_settings(db)
    return _behavioral_config


@router.patch("/api/behavioral/settings")
async def update_behavioral_settings(
    body: dict,
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    if USE_DB and db is not None:
        result = await db_update_behavioral_settings(db, body)
        _store._behavioral_config.update({
            "cooldown_min":        result["cooldown_min"],
            "repeated_threshold":  result["repeated_threshold"],
            "escalation_delta":    result["escalation_delta"],
        })
        return result
    for key in ["repeated_threshold", "escalation_delta", "cooldown_min"]:
        if key in body:
            _store._behavioral_config[key] = body[key]
    return _store._behavioral_config
