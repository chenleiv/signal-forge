"""Admin user management (RBAC phase 6): create, change role / reset
password, soft delete. Changes take effect immediately on existing sessions."""
from __future__ import annotations
import copy
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

import main
import store
import users
from tests.conftest import ANALYST_PASSWORD, session_client

NEW_PASSWORD = "brand-new-password-1"


@pytest.fixture(autouse=True)
def _restore_state():
    saved_users = copy.deepcopy(users._users)
    incidents = copy.deepcopy(list(store.incidents_store))
    yield
    users._users.clear()
    users._users.update(saved_users)
    store.incidents_store.clear()
    store.incidents_store.extend(incidents)


@pytest.fixture
def admin():
    return session_client("admin", "admin")


@pytest.fixture
def alice():
    return session_client("alice", "analyst")


def _login(username: str, password: str) -> TestClient:
    client = TestClient(main.app)
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return client


def _new_user(admin, username="carol", role="analyst", password=NEW_PASSWORD, display_name="Carol Diaz"):
    return admin.post("/api/users", json={"username": username, "display_name": display_name,
                                          "role": role, "password": password})


# ── Admin only ────────────────────────────────────────────────

@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/users", {"username": "eve", "display_name": "Eve", "role": "admin", "password": NEW_PASSWORD}),
    ("PATCH", "/api/users/bob", {"role": "admin"}),
    ("PATCH", "/api/users/bob", {"password": NEW_PASSWORD}),
    ("DELETE", "/api/users/bob", None),
])
def test_analyst_cannot_manage_users(alice, method, path, body):
    before = copy.deepcopy(users._users)
    r = alice.request(method, path, json=body)
    assert r.status_code == 403 and r.json() == {"detail": "Admin role required"}
    assert users._users == before


# ── Create ────────────────────────────────────────────────────

def test_admin_creates_a_user_who_can_log_in(admin):
    r = _new_user(admin)
    assert r.status_code == 201
    assert r.json() == {"username": "carol", "display_name": "Carol Diaz", "role": "analyst"}
    me = _login("carol", NEW_PASSWORD).get("/auth/me").json()
    assert me["role"] == "analyst"
    assert "carol" in {u["username"] for u in admin.get("/api/users").json()}


@pytest.mark.parametrize("override", [
    {"username": "ab"}, {"username": "Carol"}, {"username": "carol smith"}, {"username": "c" * 51},
    {"username": "../admin"}, {"username": 42},
    {"display_name": ""}, {"display_name": "   "}, {"display_name": "x" * 101}, {"display_name": None},
    {"role": "superuser"}, {"role": None},
    {"password": "short"}, {"password": "p" * 73}, {"password": None}, {"password": 123456789012},
])
def test_create_validates_input(admin, override):
    body = {"username": "carol", "display_name": "Carol", "role": "analyst", "password": NEW_PASSWORD, **override}
    before = set(users._users)
    assert admin.post("/api/users", json=body).status_code == 422
    assert set(users._users) == before  # nothing created


def test_new_password_uses_the_admin_password_rule():
    """One rule for ADMIN_PASSWORD, new users and resets."""
    assert users.password_problem("x" * 11) and users.password_problem("x" * 73)
    assert users.password_problem("x" * 12) is None and users.password_problem("x" * 72) is None


def test_username_taken_is_409(admin):
    assert _new_user(admin, username="alice").status_code == 409


# ── Change role / reset password ──────────────────────────────

def test_role_change_takes_effect_on_existing_sessions_immediately(admin):
    bob = _login("bob", ANALYST_PASSWORD)
    assert bob.get("/auth/me").json()["role"] == "analyst"

    assert admin.patch("/api/users/bob", json={"role": "manager"}).status_code == 200

    assert bob.get("/auth/me").status_code == 401            # old session is gone
    assert _login("bob", ANALYST_PASSWORD).get("/auth/me").json()["role"] == "manager"


def test_demoted_manager_loses_manager_rights_immediately(admin):
    _new_user(admin, username="dana", role="manager")
    dana = _login("dana", NEW_PASSWORD)
    assert dana.patch("/api/users/bob", json={"password": "another-password-1"}).status_code == 200

    assert admin.patch("/api/users/dana", json={"role": "analyst"}).status_code == 200

    assert dana.get("/auth/me").status_code == 401
    again = _login("dana", NEW_PASSWORD)
    assert again.patch("/api/users/bob", json={"password": "another-password-2"}).status_code == 403


def test_password_reset_signs_out_every_session(admin):
    bob1, bob2 = _login("bob", ANALYST_PASSWORD), _login("bob", ANALYST_PASSWORD)

    assert admin.patch("/api/users/bob", json={"password": NEW_PASSWORD}).status_code == 200

    assert bob1.get("/auth/me").status_code == 401
    assert bob2.get("/auth/me").status_code == 401
    assert TestClient(main.app).post("/auth/login", json={"username": "bob", "password": ANALYST_PASSWORD}).status_code == 401
    assert _login("bob", NEW_PASSWORD).get("/auth/me").status_code == 200


@pytest.mark.parametrize("body", [
    {"username": "robert"}, {"display_name": "Robert"}, {"role": "analyst", "username": "x"},
    {"is_admin": True}, {}, {"role": "root"}, {"password": "short"},
])
def test_patch_accepts_only_role_and_password(admin, body):
    before = copy.deepcopy(users._users["bob"])
    assert admin.patch("/api/users/bob", json=body).status_code == 422
    assert users._users["bob"] == before


def test_unchanged_role_does_not_sign_the_user_out(admin):
    bob = _login("bob", ANALYST_PASSWORD)
    assert admin.patch("/api/users/bob", json={"role": "analyst"}).status_code == 200
    assert bob.get("/auth/me").status_code == 200


@pytest.mark.parametrize("method,body", [("PATCH", {"role": "admin"}), ("DELETE", None)])
def test_unknown_user_is_404(admin, method, body):
    assert admin.request(method, "/api/users/nobody", json=body).status_code == 404


# ── Exactly one admin ─────────────────────────────────────────
# The admin account cannot be deleted, and the admin role is never granted
# or removed: not by the admin, not by anyone.

ADMIN_ROLE_FIXED = "There is exactly one admin: the admin role cannot be granted or removed"


@pytest.mark.parametrize("role", ["analyst", "manager"])
def test_the_admin_cannot_be_demoted(admin, role):
    r = admin.patch("/api/users/admin", json={"role": role})
    assert r.status_code == 403 and r.json() == {"detail": ADMIN_ROLE_FIXED}
    assert users._users["admin"]["role"] == "admin"


@pytest.mark.parametrize("target", ["bob", "mira"])
def test_the_admin_role_cannot_be_granted(admin, target):
    before = users._users[target]["role"]
    r = admin.patch(f"/api/users/{target}", json={"role": "admin"})
    assert r.status_code == 403 and r.json() == {"detail": ADMIN_ROLE_FIXED}
    assert users._users[target]["role"] == before


def test_nobody_is_created_as_an_admin(admin):
    r = _new_user(admin, username="eve", role="admin")
    assert r.status_code == 403 and r.json() == {"detail": ADMIN_ROLE_FIXED}
    assert users.get_user_record("eve") is None


def test_grant_hidden_in_a_password_reset_is_refused(admin):
    r = admin.patch("/api/users/bob", json={"password": NEW_PASSWORD, "role": "admin"})
    assert r.status_code == 403
    assert users._users["bob"]["role"] == "analyst"
    assert _login("bob", ANALYST_PASSWORD)  # the password did not change either


def test_admin_unchanged_role_is_fine_but_own_password_goes_through_settings(admin):
    """Unchanged role is a no-op. The admin's own password is NOT reset here
    (no current password asked); it changes only through PATCH /auth/me."""
    assert admin.patch("/api/users/admin", json={"role": "admin"}).status_code == 200
    r = admin.patch("/api/users/admin", json={"password": NEW_PASSWORD})
    assert r.status_code == 403
    assert r.json() == {"detail": "Change your own password in Settings (it asks for your current password)"}
    assert _login("admin", "test-admin-password")


def test_there_is_exactly_one_admin():
    active_admins = [u for u in users._users.values() if u["role"] == "admin" and not u.get("deleted_at")]
    assert [u["username"] for u in active_admins] == ["admin"]


# ── Soft delete ───────────────────────────────────────────────

def _incident(inc_id: str, assigned_to: str, status: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    store.incidents_store.appendleft({
        "id": inc_id, "title": "t", "severity": "high", "status": status, "attack_type": "SQLi",
        "source_ip": "8.8.8.8", "source_region": "US", "event_count": 1, "assigned_to": assigned_to,
        "created_at": now, "updated_at": now, "mitre_tags": [], "notes": [], "completed_tasks": [],
    })


def test_deleted_user_is_signed_out_and_cannot_log_in(admin):
    bob = _login("bob", ANALYST_PASSWORD)
    assert admin.delete("/api/users/bob").status_code == 200

    assert bob.get("/auth/me").status_code == 401
    r = TestClient(main.app).post("/auth/login", json={"username": "bob", "password": ANALYST_PASSWORD})
    assert r.status_code == 401 and r.json() == {"detail": "Invalid credentials"}  # same as unknown user


def test_deleted_user_leaves_the_options_but_history_keeps_the_name(admin):
    admin.delete("/api/users/bob")

    assert "bob" not in {u["username"] for u in admin.get("/api/users").json()}
    directory = {u["username"]: u for u in admin.get("/api/users/directory").json()}
    assert directory["bob"] == {"username": "bob", "display_name": "Bob Martinez", "deleted": True}
    assert directory["alice"]["deleted"] is False


def test_deleted_user_cannot_be_assigned(admin):
    _incident("INC-U1", None, "open")
    admin.delete("/api/users/bob")
    r = admin.patch("/api/incidents/INC-U1", json={"assigned_to": "bob"})
    assert r.status_code == 422


def test_deleting_a_user_unassigns_open_incidents_only(admin):
    _incident("INC-OPEN", "bob", "investigating")
    _incident("INC-DONE", "bob", "closed")
    _incident("INC-ALICE", "alice", "open")

    admin.delete("/api/users/bob")

    by_id = {i["id"]: i["assigned_to"] for i in store.incidents_store}
    assert by_id["INC-OPEN"] is None        # someone else must pick it up
    assert by_id["INC-DONE"] == "bob"       # history keeps the name
    assert by_id["INC-ALICE"] == "alice"


def test_deleted_username_can_never_be_reused(admin):
    """A new 'bob' must not inherit the old bob's history or sessions."""
    old_bob = _login("bob", ANALYST_PASSWORD)
    admin.delete("/api/users/bob")
    assert _new_user(admin, username="bob").status_code == 409
    assert old_bob.get("/auth/me").status_code == 401


def test_deleting_twice_is_404(admin):
    assert admin.delete("/api/users/bob").status_code == 200
    assert admin.delete("/api/users/bob").status_code == 404


def test_token_without_session_key_is_rejected():
    """Tokens issued before migration 005 carry no key: log in again."""
    import time
    import jwt
    token = jwt.encode({"sub": "alice", "role": "analyst", "typ": "session", "sid": "s1", "exp": int(time.time()) + 300},
                       store.SECRET_KEY, algorithm="HS256")
    client = TestClient(main.app)
    client.cookies.set("sf_session", token)
    assert client.get("/auth/me").status_code == 401


# ── DB path ───────────────────────────────────────────────────

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
async def test_db_soft_delete_and_unassign(db_session):
    from db_ops import (db_create_incident, db_create_user, db_get_incident, db_get_users,
                        db_unassign_open_incidents, db_update_user)
    await db_create_user(db_session, {"username": "bob", "display_name": "Bob", "role": "analyst",
                                      "password_hash": "h", "session_key": "k1"})
    now = datetime.now(timezone.utc).isoformat()
    for inc_id, status in (("INC-1", "open"), ("INC-2", "closed")):
        await db_create_incident(db_session, {
            "id": inc_id, "title": "t", "severity": "high", "status": status, "attack_type": "SQLi",
            "source_ip": "8.8.8.8", "source_region": "US", "event_count": 1, "assigned_to": "bob",
            "created_at": now, "updated_at": now, "mitre_tags": []})

    deleted_at = datetime.now(timezone.utc).isoformat()
    await db_update_user(db_session, "bob", {"deleted_at": deleted_at, "session_key": "k2"})
    assert await db_unassign_open_incidents(db_session, "bob") == 1

    row = (await db_get_users(db_session))[0]
    assert row["session_key"] == "k2" and row["deleted_at"] is not None
    assert (await db_get_incident(db_session, "INC-1"))["assigned_to"] is None
    assert (await db_get_incident(db_session, "INC-2"))["assigned_to"] == "bob"


# ── Database failures ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_failed_database_write_undoes_the_change(monkeypatch):
    import user_admin

    async def broken_write(*_args, **_kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr(store, "USE_DB", True)
    monkeypatch.setattr(user_admin, "db_update_user", broken_write)
    before = copy.deepcopy(users._users["bob"])

    with pytest.raises(RuntimeError):
        await user_admin.update_user(object(), "bob", {"role": "manager"})

    assert users._users["bob"] == before  # role and session key unchanged


# ── Manager: may only reset analysts' passwords ───────────────

@pytest.fixture
def manager():
    return session_client("mira", "manager")


def test_manager_resets_an_analysts_password_and_signs_them_out(manager):
    bob = _login("bob", ANALYST_PASSWORD)

    assert manager.patch("/api/users/bob", json={"password": NEW_PASSWORD}).status_code == 200

    assert bob.get("/auth/me").status_code == 401
    assert _login("bob", NEW_PASSWORD).get("/auth/me").status_code == 200


@pytest.mark.parametrize("target,reason", [
    ("admin", "Managers can only reset analysts' passwords"),
    ("mira", "Change your own password in Settings (it asks for your current password)"),  # self
])
def test_manager_cannot_reset_a_non_analysts_password(manager, target, reason):
    r = manager.patch(f"/api/users/{target}", json={"password": NEW_PASSWORD})
    assert r.status_code == 403
    assert r.json() == {"detail": reason}
    assert _login(target, "test-admin-password" if target == "admin" else ANALYST_PASSWORD)


@pytest.mark.parametrize("body", [
    {"role": "manager"},                              # promote an analyst
    {"role": "admin"},
    {"password": NEW_PASSWORD, "role": "manager"},    # a reset smuggling a role change
])
def test_manager_cannot_change_roles(manager, body):
    assert manager.patch("/api/users/bob", json=body).status_code == 403
    assert users.get_user("bob")["role"] == "analyst"


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/users", {"username": "eve", "display_name": "Eve", "role": "analyst", "password": NEW_PASSWORD}),
    ("DELETE", "/api/users/bob", None),
])
def test_manager_cannot_create_or_delete_users(manager, method, path, body):
    assert manager.request(method, path, json=body).status_code == 403


def test_manager_gets_404_for_an_unknown_user(manager):
    assert manager.patch("/api/users/nobody", json={"password": NEW_PASSWORD}).status_code == 404


def test_analyst_is_refused_before_the_user_lookup(alice):
    """403 for known and unknown users alike: the route reveals nothing to analysts."""
    for target in ("bob", "nobody"):
        r = alice.patch(f"/api/users/{target}", json={"password": NEW_PASSWORD})
        assert r.status_code == 403 and r.json() == {"detail": "Admin role required"}


def test_manager_reset_still_enforces_the_password_rule(manager):
    assert manager.patch("/api/users/bob", json={"password": "short"}).status_code == 422


@pytest.mark.asyncio
async def test_startup_refuses_a_database_with_two_admins(db_session):
    """Fail closed: a second admin (e.g. from an older build) stops startup."""
    from db_ops import db_create_user
    for name in ("admin", "root"):
        await db_create_user(db_session, {
            "username": name, "display_name": name, "role": "admin",
            "password_hash": users.hash_password(NEW_PASSWORD), "session_key": "k", "deleted_at": None,
        })
    with pytest.raises(RuntimeError, match="Exactly one admin"):
        await users.sync_users_with_db(db_session, demo_mode=False, admin_password="")


@pytest.mark.asyncio
async def test_startup_accepts_one_admin_plus_a_deleted_one(db_session):
    """Only ACTIVE admins count (a soft-deleted row is history, not an admin)."""
    from db_ops import db_create_user, db_update_user
    for name in ("admin", "root"):
        await db_create_user(db_session, {
            "username": name, "display_name": name, "role": "admin",
            "password_hash": users.hash_password(NEW_PASSWORD), "session_key": "k", "deleted_at": None,
        })
    await db_update_user(db_session, "root", {"deleted_at": "2026-01-01T00:00:00+00:00"})
    await users.sync_users_with_db(db_session, demo_mode=False, admin_password="")
    assert users.get_user("admin") is not None


# ── Switching a demo database to real mode ────────────────────
# Render: the site ran in demo mode (admin = public "admin-demo"), then
# DEMO_MODE=false on the SAME database. The admin must not keep the public
# password, and a real admin password must never be overwritten.

REAL_ADMIN_PASSWORD = "a-real-admin-password-1"


async def _run_demo_deployment(db_session):
    users.seed_users(demo_mode=True, admin_password="")
    await users.sync_users_with_db(db_session, demo_mode=True, admin_password="")


async def _switch_to_real_mode(db_session, admin_password: str):
    users.seed_users(demo_mode=False, admin_password=admin_password)
    await users.sync_users_with_db(db_session, demo_mode=False, admin_password=admin_password)


@pytest.mark.asyncio
async def test_real_mode_replaces_the_admins_public_demo_password(db_session):
    await _run_demo_deployment(db_session)
    demo_session_key = users.get_user("admin")["session_key"]

    await _switch_to_real_mode(db_session, REAL_ADMIN_PASSWORD)

    assert users.authenticate("admin", "admin-demo") is None
    assert users.authenticate("admin", REAL_ADMIN_PASSWORD) is not None
    assert users.get_user("admin")["session_key"] != demo_session_key  # demo sessions signed out
    # persisted, not only in memory
    from db_ops import db_get_users
    row = next(r for r in await db_get_users(db_session) if r["username"] == "admin")
    assert users.verify_password(REAL_ADMIN_PASSWORD, row["password_hash"])


@pytest.mark.asyncio
async def test_real_mode_refuses_to_start_with_a_demo_admin_and_no_admin_password(db_session):
    await _run_demo_deployment(db_session)
    with pytest.raises(RuntimeError, match="public demo password"):
        await _switch_to_real_mode(db_session, admin_password="")


@pytest.mark.asyncio
async def test_real_mode_never_overwrites_a_real_admin_password(db_session):
    await _switch_to_real_mode(db_session, REAL_ADMIN_PASSWORD)          # first real start
    await _switch_to_real_mode(db_session, "another-admin-password-2")  # env var changed later
    assert users.authenticate("admin", REAL_ADMIN_PASSWORD) is not None
    assert users.authenticate("admin", "another-admin-password-2") is None


@pytest.mark.asyncio
async def test_real_mode_with_a_real_admin_needs_no_admin_password(db_session):
    await _switch_to_real_mode(db_session, REAL_ADMIN_PASSWORD)
    await _switch_to_real_mode(db_session, admin_password="")  # variable removed afterwards
    assert users.authenticate("admin", REAL_ADMIN_PASSWORD) is not None


@pytest.mark.asyncio
async def test_demo_accounts_are_not_loaded_after_the_switch(db_session):
    await _run_demo_deployment(db_session)
    await _switch_to_real_mode(db_session, REAL_ADMIN_PASSWORD)
    assert users.get_user("alice") is None and users.get_user("bob") is None
