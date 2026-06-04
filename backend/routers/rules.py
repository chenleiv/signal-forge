from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db_ops import db_get_rules, db_create_rule, db_update_rule, db_delete_rule
from store import _rules, verify_token, USE_DB
import store as _store

router = APIRouter()


@router.get("/api/rules")
async def get_rules(db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)):
    if USE_DB and db is not None:
        return await db_get_rules(db)
    return _rules


@router.post("/api/rules")
async def create_rule(body: dict, db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)):
    rule_data = {
        "id":          str(uuid4())[:8],
        "name":        body.get("name", "Unnamed Rule"),
        "enabled":     body.get("enabled", True),
        "conditions":  body.get("conditions", []),
        "logic":       body.get("logic", "AND"),
        "actions":     body.get("actions", ["alert"]),
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "match_count": 0,
    }
    if USE_DB and db is not None:
        saved = await db_create_rule(db, rule_data)
        _store._rules.append(saved)
        return saved
    _store._rules.append(rule_data)
    return rule_data


@router.patch("/api/rules/{rule_id}")
async def update_rule(rule_id: str, body: dict, db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)):
    if USE_DB and db is not None:
        updated = await db_update_rule(db, rule_id, body)
        if updated is None:
            raise HTTPException(status_code=404, detail="Rule not found")
        for rule in _store._rules:
            if rule["id"] == rule_id:
                for key in ["name", "enabled", "conditions", "logic", "actions"]:
                    if key in body:
                        rule[key] = body[key]
                break
        return updated
    rule_in_mem = next((r for r in _store._rules if r["id"] == rule_id), None)
    if rule_in_mem is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    for key in ["name", "enabled", "conditions", "logic", "actions"]:
        if key in body:
            rule_in_mem[key] = body[key]
    return rule_in_mem


@router.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: str, db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)):
    _store._rules[:] = [r for r in _store._rules if r["id"] != rule_id]
    if USE_DB and db is not None:
        await db_delete_rule(db, rule_id)
    return {"ok": True}
