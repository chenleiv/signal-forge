from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from constants import BEHAVIORAL_DEFAULTS, BEHAVIORAL_LIMITS
from database import get_db
from db_ops import db_get_behavioral_settings, db_update_behavioral_settings
from authz import require_admin
from store import _behavioral_config, verify_token
import store as _store

router = APIRouter()


@router.get("/api/behavioral/settings")
async def get_behavioral_settings(
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    if _store.USE_DB and db is not None:
        return await db_get_behavioral_settings(db)
    return _behavioral_config


def _validate(body: dict) -> dict:
    """Known fields only, each an integer within its range (422 otherwise)."""
    unknown = set(body) - set(BEHAVIORAL_LIMITS)
    if unknown or not body:
        raise HTTPException(status_code=422, detail=f"Allowed fields: {', '.join(BEHAVIORAL_LIMITS)}")
    for key, value in body.items():
        low, high = BEHAVIORAL_LIMITS[key]
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            raise HTTPException(status_code=422, detail=f"{key} must be an integer between {low} and {high}")
    return body


@router.patch("/api/behavioral/settings")
async def update_behavioral_settings(
    body: dict,
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(require_admin)
):
    patch = _validate(body)
    if _store.USE_DB and db is not None:
        result = await db_update_behavioral_settings(db, patch)
        _store._behavioral_config.update({k: result[k] for k in BEHAVIORAL_DEFAULTS})
        return result
    _store._behavioral_config.update(patch)
    return _store._behavioral_config
