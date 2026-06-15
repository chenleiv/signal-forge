from __future__ import annotations
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from jose import jwt

from store import SECRET_KEY

router = APIRouter()

_COOKIE  = "sf_session"
_MAX_AGE = 8 * 3600

_DEV           = os.environ.get("ENV") == "development"
_COOKIE_SECURE = not _DEV


def _make_token(extra: dict | None = None, hours: int = 8) -> str:
    payload = {"sub": "analyst", "exp": datetime.now(timezone.utc) + timedelta(hours=hours)}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def _decode_session(request: Request) -> None:
    # Authorization header first (cross-origin SPA), cookie as fallback (same-origin)
    token: str | None = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.cookies.get(_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.post("/auth/login")
async def login(body: dict, response: Response):
    if body.get("username") == "analyst" and body.get("password") == "signalforge":
        token = _make_token()
        # Set cookie for same-origin clients
        response.set_cookie(
            key=_COOKIE, value=token, httponly=True,
            secure=_COOKIE_SECURE, samesite="lax", max_age=_MAX_AGE,
        )
        # Return token in body for cross-origin SPA clients
        return {"ok": True, "token": token}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key=_COOKIE, httponly=True, secure=_COOKIE_SECURE, samesite="lax")
    return {"ok": True}


@router.get("/auth/me")
async def me(request: Request):
    _decode_session(request)
    return {"user": "analyst"}


@router.get("/auth/ws-ticket")
async def ws_ticket(request: Request):
    _decode_session(request)
    ticket = jwt.encode(
        {"sub": "analyst", "ws": True, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        SECRET_KEY, algorithm="HS256",
    )
    return {"ticket": ticket}
