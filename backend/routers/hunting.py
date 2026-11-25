from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from authz import check_delete_hunt
from rate_limit import WRITE_LIMIT, limiter
from schemas import SavedHuntBody
from store import ip_store, _saved_hunts, verify_token
from users import CurrentUser

MAX_HUNT_RESULTS = 500
# In memory only: without a cap any user could grow the list without limit.
MAX_SAVED_HUNTS = 100
# Per creator, so one user cannot fill the global cap alone.
MAX_SAVED_HUNTS_PER_USER = 20

router = APIRouter()


@router.get("/api/hunt")
@limiter.limit(WRITE_LIMIT)  # scans every stored event
async def run_hunt(
    request: Request,
    ip: Optional[str] = None,
    attack_type: Optional[str] = None,
    region: Optional[str] = None,
    min_score: int = 0,
    max_score: int = 100,
    limit: int = Query(200, ge=1, le=MAX_HUNT_RESULTS),
    _=Depends(verify_token),
):
    results = []
    for ip_addr, events in ip_store.items():
        if ip and ip.lower() not in ip_addr.lower():
            continue
        for e in events:
            if attack_type and e["attack_type"] != attack_type:
                continue
            if region and e["region"] != region:
                continue
            if not (min_score <= e["score"] <= max_score):
                continue
            results.append({**e, "ip": ip_addr})
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"results": results[:limit], "total": len(results)}


@router.get("/api/hunts")
async def get_saved_hunts(_=Depends(verify_token)):
    # Hunts saved before owners were recorded answer created_by: null.
    return [{"created_by": None, **h} for h in _saved_hunts]


@router.post("/api/hunts")
@limiter.limit(WRITE_LIMIT)
async def save_hunt(request: Request, body: SavedHuntBody, user: CurrentUser = Depends(verify_token)):
    if sum(1 for h in _saved_hunts if h.get("created_by") == user.username) >= MAX_SAVED_HUNTS_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=f"You have {MAX_SAVED_HUNTS_PER_USER} saved hunts, the most allowed. Delete one of yours first",
        )
    if len(_saved_hunts) >= MAX_SAVED_HUNTS:
        raise HTTPException(
            status_code=409,
            detail=f"Saved hunts are limited to {MAX_SAVED_HUNTS} in total. Ask an admin to delete old ones",
        )
    hunt = {
        "id": str(uuid4())[:8],
        "name": body.name,
        "query": body.query.model_dump(exclude_unset=True),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result_count": body.result_count,
        "created_by": user.username,
    }
    _saved_hunts.insert(0, hunt)
    return hunt


@router.delete("/api/hunts/{hunt_id}")
@limiter.limit(WRITE_LIMIT)
async def delete_hunt(request: Request, hunt_id: str, user: CurrentUser = Depends(verify_token)):
    # The list is shared with every signed-in user, so a 404 before the
    # permission check reveals nothing. No await between the check and the
    # removal, so no other request can change the list in between.
    hunt = next((h for h in _saved_hunts if h["id"] == hunt_id), None)
    if hunt is None:
        raise HTTPException(status_code=404, detail="Saved hunt not found")
    check_delete_hunt(user, hunt)
    _saved_hunts[:] = [h for h in _saved_hunts if h["id"] != hunt_id]
    return {"ok": True}
