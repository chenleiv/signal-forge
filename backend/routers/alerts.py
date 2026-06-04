from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from store import alerts_store, _find_alert, verify_token
from routers.incidents import build_incident_for_ip

router = APIRouter()


@router.get("/api/alerts")
async def get_alerts(include_dismissed: bool = False, _=Depends(verify_token)):
    if include_dismissed:
        return list(alerts_store)
    return [a for a in alerts_store if a["status"] != "dismissed"]


@router.patch("/api/alerts/{alert_id}")
async def patch_alert(alert_id: str, body: dict, _=Depends(verify_token)):
    alert = _find_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    new_status = body.get("status")
    if new_status not in ("acknowledged", "dismissed"):
        raise HTTPException(status_code=422, detail="status must be 'acknowledged' or 'dismissed'")
    alert["status"] = new_status
    if new_status == "acknowledged":
        alert["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    return alert


@router.post("/api/alerts/{alert_id}/case")
async def create_case_from_alert(
    alert_id: str,
    db: Optional[AsyncSession] = Depends(get_db), _=Depends(verify_token)
):
    alert = _find_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    ip = alert.get("ip")
    if not ip:
        raise HTTPException(status_code=400, detail="Alert has no associated IP")
    return await build_incident_for_ip(ip, db)
