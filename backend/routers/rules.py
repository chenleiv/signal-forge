from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from authz import require_admin
from database import get_db
from rate_limit import ADMIN_WRITE_LIMIT, limiter
from schemas import RuleCreate, RulePatch
from repositories import RULE_FIELDS, rules
from store import verify_token

router = APIRouter()


@router.get("/api/rules")
async def get_rules(db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)):
    return await rules(db).list()


@router.post("/api/rules")
@limiter.limit(ADMIN_WRITE_LIMIT)
async def create_rule(request: Request, body: RuleCreate,
                      db: Optional[AsyncSession] = Depends(get_db), _=Depends(require_admin)):
    return await rules(db).create({
        "id":          str(uuid4())[:8],
        **body.model_dump(mode="json"),
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "match_count": 0,
    })


@router.patch("/api/rules/{rule_id}")
@limiter.limit(ADMIN_WRITE_LIMIT)
async def update_rule(request: Request, rule_id: str, body: RulePatch,
                      db: Optional[AsyncSession] = Depends(get_db), _=Depends(require_admin)):
    changes = body.changes()
    updated = await rules(db).update(rule_id, {k: changes[k] for k in RULE_FIELDS if k in changes})
    if updated is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return updated


@router.delete("/api/rules/{rule_id}")
@limiter.limit(ADMIN_WRITE_LIMIT)
async def delete_rule(request: Request, rule_id: str, db: Optional[AsyncSession] = Depends(get_db), _=Depends(require_admin)):
    await rules(db).delete(rule_id)
    return {"ok": True}
