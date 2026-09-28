"""Logout ends the session on the server, not only in the browser.

Every session token carries its own id ("sid"); logout revokes that id until
the token would have expired. A copied cookie stops working; other sessions
of the same user (another device, other visitors of a shared demo account)
keep working.
"""
from __future__ import annotations
import time

import jwt
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

import main
import sessions
import store
from tests.conftest import ANALYST_PASSWORD

COOKIE = "sf_session"


@pytest.fixture(autouse=True)
def _clean_revocations():
    saved = dict(sessions._revoked)
    yield
    sessions._revoked.clear()
    sessions._revoked.update(saved)


def _login(username: str = "alice", password: str = ANALYST_PASSWORD) -> TestClient:
    client = TestClient(main.app)
    assert client.post("/auth/login", json={"username": username, "password": password}).status_code == 200
    return client


def _with_cookie(token: str) -> TestClient:
    client = TestClient(main.app)
    client.cookies.set(COOKIE, token)
    return client


def test_a_copied_cookie_stops_working_after_logout():
    browser = _login()
    stolen = browser.cookies.get(COOKIE)
    assert _with_cookie(stolen).get("/auth/me").status_code == 200

    assert browser.post("/auth/logout").status_code == 200

    assert _with_cookie(stolen).get("/auth/me").status_code == 401
    assert _with_cookie(stolen).get("/auth/ws-ticket").status_code == 401


def test_logout_ends_only_this_session():
    """Another device of the same user, or another visitor of a shared demo
    account, stays signed in."""
    phone, laptop = _login(), _login()
    assert phone.cookies.get(COOKIE) != laptop.cookies.get(COOKIE)   # each login is its own session

    phone.post("/auth/logout")

    assert laptop.get("/auth/me").status_code == 200


def test_logging_in_again_after_logout_works():
    client = _login()
    client.post("/auth/logout")
    assert _login().get("/auth/me").status_code == 200


def test_every_login_gets_a_fresh_session_id():
    a, b = _login(), _login()
    sid = lambda c: jwt.decode(c.cookies.get(COOKIE), store.SECRET_KEY, algorithms=["HS256"])["sid"]
    assert sid(a) != sid(b)


def test_a_token_without_a_session_id_is_rejected():
    """Tokens issued before this change cannot be logged out: force a new login."""
    import users
    legacy = jwt.encode({"sub": "alice", "role": "analyst", "typ": "session",
                         "sk": users.get_user("alice")["session_key"], "exp": int(time.time()) + 300},
                        store.SECRET_KEY, algorithm="HS256")
    assert _with_cookie(legacy).get("/auth/me").status_code == 401


@pytest.mark.parametrize("cookie", [None, "garbage", "a.b.c"])
def test_logout_without_a_valid_session_is_harmless(cookie):
    client = TestClient(main.app)
    if cookie:
        client.cookies.set(COOKIE, cookie)
    assert client.post("/auth/logout").status_code == 200


def test_logout_does_not_revoke_on_a_forged_token():
    """Only a token signed by us can put an id on the list (no flooding it)."""
    forged = jwt.encode({"sub": "alice", "typ": "session", "sid": "victim-sid", "exp": int(time.time()) + 300},
                        "attacker-guessed-key-of-a-valid-32-byte-length", algorithm="HS256")
    _with_cookie(forged).post("/auth/logout")
    assert not sessions.is_revoked("victim-sid")


def test_expired_revocations_are_forgotten():
    sessions._revoked["old"] = time.time() - 1
    sessions._purge(time.time())
    assert not sessions.is_revoked("old")


def test_demo_mode_still_allows_logout(monkeypatch):
    client = _login()
    stolen = client.cookies.get(COOKIE)
    monkeypatch.setattr(main, "DEMO_MODE", True)
    assert client.post("/auth/logout").status_code == 200
    assert _with_cookie(stolen).get("/auth/me").status_code == 401


# ── Survives a restart (with a database) ──────────────────────

@pytest_asyncio.fixture
async def db_session():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base
    import models  # noqa: F401
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_a_revocation_survives_a_restart(db_session):
    await sessions.revoke_session(db_session, "sid-1", time.time() + 3600)
    sessions._revoked.clear()                      # the process restarts

    await sessions.load_revoked_sessions(db_session)

    assert sessions.is_revoked("sid-1")


@pytest.mark.asyncio
async def test_expired_revocations_are_dropped_from_the_database(db_session):
    from datetime import datetime, timedelta, timezone
    from db_ops import db_load_revoked_sessions, db_revoke_session
    await db_revoke_session(db_session, "expired", datetime.now(timezone.utc) - timedelta(seconds=1))
    await db_revoke_session(db_session, "live", datetime.now(timezone.utc) + timedelta(hours=1))

    rows = await db_load_revoked_sessions(db_session)

    assert [sid for sid, _ in rows] == ["live"]
