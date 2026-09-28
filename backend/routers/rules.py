from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from authz import require_admin
from database import get_db
from repositories import RULE_FIELDS, rules
from store import verify_token

router = APIRouter()


@router.get("/api/rules")
async def get_rules(db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)):
    return await rules(db).list()


@router.post("/api/rules")
async def create_rule(body: dict, db: Optional[AsyncSession] = Depends(get_db), _=Depends(require_admin)):
    return await rules(db).create({
        "id":          str(uuid4())[:8],
        "name":        body.get("name", "Unnamed Rule"),
        "enabled":     body.get("enabled", True),
        "conditions":  body.get("conditions", []),
        "logic":       body.get("logic", "AND"),
        "actions":     body.get("actions", ["alert"]),
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "match_count": 0,
    })


@router.patch("/api/rules/{rule_id}")
async def update_rule(rule_id: str, body: dict, db: Optional[AsyncSession] = Depends(get_db), _=Depends(require_admin)):
    updated = await rules(db).update(rule_id, {k: body[k] for k in RULE_FIELDS if k in body})
    if updated is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return updated


@router.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: str, db: Optional[AsyncSession] = Depends(get_db), _=Depends(require_admin)):
    await rules(db).delete(rule_id)
    return {"ok": True}
