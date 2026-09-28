from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from constants import BEHAVIORAL_LIMITS
from database import get_db
from authz import require_admin
from repositories import behavioral
from store import verify_token

router = APIRouter()


@router.get("/api/behavioral/settings")
async def get_behavioral_settings(
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    return await behavioral(db).get()


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
    return await behavioral(db).update(_validate(body))
