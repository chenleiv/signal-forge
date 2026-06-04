from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends

from store import ip_store, _saved_hunts, verify_token

router = APIRouter()


@router.get("/api/hunt")
async def run_hunt(
    ip: Optional[str] = None,
    attack_type: Optional[str] = None,
    region: Optional[str] = None,
    min_score: int = 0,
    max_score: int = 100,
    limit: int = 200,
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
async def save_hunt(body: dict, _=Depends(verify_token)):
    hunt = {
        "id": str(uuid4())[:8],
        "name": body.get("name", "Unnamed hunt"),
        "query": body.get("query", {}),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result_count": body.get("result_count", 0),
    }
    _saved_hunts.insert(0, hunt)
    return hunt


@router.delete("/api/hunts/{hunt_id}")
async def delete_hunt(hunt_id: str, _=Depends(verify_token)):
    import store as _store
    _store._saved_hunts[:] = [h for h in _store._saved_hunts if h["id"] != hunt_id]
    return {"ok": True}
