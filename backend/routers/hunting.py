from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from rate_limit import WRITE_LIMIT, limiter
from schemas import SavedHuntBody
from store import ip_store, _saved_hunts, verify_token

MAX_HUNT_RESULTS = 500
# In memory only: without a cap any user could grow the list without limit.
MAX_SAVED_HUNTS = 100

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
    return _saved_hunts


@router.post("/api/hunts")
@limiter.limit(WRITE_LIMIT)
async def save_hunt(request: Request, body: SavedHuntBody, _=Depends(verify_token)):
    if len(_saved_hunts) >= MAX_SAVED_HUNTS:
        raise HTTPException(status_code=409, detail=f"Saved hunts are limited to {MAX_SAVED_HUNTS}, delete one first")
    hunt = {
        "id": str(uuid4())[:8],
        "name": body.name,
        "query": body.query.model_dump(exclude_unset=True),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result_count": body.result_count,
    }
    _saved_hunts.insert(0, hunt)
    return hunt


@router.delete("/api/hunts/{hunt_id}")
@limiter.limit(WRITE_LIMIT)
async def delete_hunt(request: Request, hunt_id: str, _=Depends(verify_token)):
    import store as _store
    _store._saved_hunts[:] = [h for h in _store._saved_hunts if h["id"] != hunt_id]
    return {"ok": True}
