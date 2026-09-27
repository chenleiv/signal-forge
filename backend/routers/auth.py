from __future__ import annotations
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
import jwt
from starlette.concurrency import run_in_threadpool

from rate_limit import limiter, login_locked, record_login_failure
import store as _store
from store import SECRET_KEY, verify_token
from users import DEMO_USERNAMES, CurrentUser, authenticate, get_user, public_user

router = APIRouter()

_COOKIE = "sf_session"
_MAX_AGE = 8 * 3600

# HttpOnly + Secure in production; set ENV=development in .env for local HTTP dev
_DEV = os.environ.get("ENV") == "development"
_COOKIE_SECURE = not _DEV


def _set_session_cookie(response: Response, user: CurrentUser) -> None:
    token = jwt.encode(
        {
            "sub": user.username,
            "role": user.role,
            # Revocation handle: must match the user's current key (store.verify_token).
            "sk": get_user(user.username)["session_key"],
            "typ": "session",
            "exp": datetime.now(timezone.utc) + timedelta(hours=8),
        },
        SECRET_KEY,
        algorithm="HS256",
    )
    response.set_cookie(
        key=_COOKIE,
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        max_age=_MAX_AGE,
    )


@router.post("/auth/login")
@limiter.limit("5/minute")  # per client IP (see rate_limit.client_ip)
async def login(request: Request, body: dict, response: Response):
    username = body.get("username")
    password = body.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        username, password = "", ""
    # Per account, across all IPs. Checked before the password, so a correct
    # guess during the lockout does not get in either. The public demo
    # accounts are exempt in demo mode: their passwords are on the login page,
    # so a lockout protects nothing and would let anyone lock visitors out.
    # The per-IP limit above still applies to them.
    account_limited = not (_store.DEMO_MODE and username in DEMO_USERNAMES)
    if account_limited and login_locked(username):
        raise HTTPException(status_code=429, detail="Too many login attempts, try again later")
    # bcrypt is CPU-bound: keep it off the event loop. Unknown user and wrong
    # password take the same path and return the same 401 (no enumeration).
    user = await run_in_threadpool(authenticate, username, password)
    if user is None:
        if account_limited:
            record_login_failure(username)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _set_session_cookie(response, user)
    return {"ok": True}


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(
        key=_COOKIE, httponly=True, secure=_COOKIE_SECURE, samesite="lax"
    )
    return {"ok": True}


@router.get("/auth/me")
async def me(user: CurrentUser = Depends(verify_token)):
    record = get_user(user.username)
    if record is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return public_user(record)  # verify_token guarantees the role matches the token


@router.get("/auth/ws-ticket")
async def ws_ticket(user: CurrentUser = Depends(verify_token)):
    ticket = jwt.encode(
        {
            "sub": user.username,
            "typ": "ws",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        SECRET_KEY,
        algorithm="HS256",
    )
    return {"ticket": ticket}
