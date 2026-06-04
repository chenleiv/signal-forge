from __future__ import annotations
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from jose import jwt

from store import SECRET_KEY

router = APIRouter()


@router.post("/auth/login")
async def login(body: dict):
    if body.get("username") == "analyst" and body.get("password") == "signalforge":
        token = jwt.encode(
            {"sub": "analyst", "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
            SECRET_KEY,
            algorithm="HS256",
        )
        return {"access_token": token}
    raise HTTPException(status_code=401, detail="Invalid credentials")
