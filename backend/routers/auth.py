from __future__ import annotations
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from jose import jwt

from store import SECRET_KEY

router = APIRouter()

_COOKIE = "sf_session"
_MAX_AGE = 8 * 3600  # 8 hours


def _decode_session(request: Request) -> None:
    token = request.cookies.get(_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _set_session_cookie(response: Response, request: Request) -> None:
    token = jwt.encode(
        {"sub": "analyst", "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
        SECRET_KEY,
        algorithm="HS256",
    )
    secure = request.url.scheme == "https"
    response.set_cookie(
        key=_COOKIE,
        value=token,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
        max_age=_MAX_AGE,
    )


@router.post("/auth/login")
async def login(body: dict, request: Request, response: Response):
    if body.get("username") == "analyst" and body.get("password") == "signalforge":
        _set_session_cookie(response, request)
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key=_COOKIE, httponly=True, samesite="lax")
    return {"ok": True}


@router.get("/auth/me")
async def me(request: Request):
    _decode_session(request)
    return {"user": "analyst"}


@router.get("/auth/ws-ticket")
async def ws_ticket(request: Request):
    _decode_session(request)
    ticket = jwt.encode(
        {"sub": "analyst", "ws": True, "exp": datetime.now(timezone.utc) + timedelta(seconds=30)},
        SECRET_KEY,
        algorithm="HS256",
    )
    return {"ticket": ticket}
