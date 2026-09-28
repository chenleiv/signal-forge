"""The API with a real database (DATABASE_URL set): writes must reach it.

Regression: incidents, rules and behavioral settings used to read the
"is there a database" flag once, at import time, before main.py set it, so
with a database they silently kept everything in memory only.
"""
from __future__ import annotations

from sqlalchemy import select

import store
from models import BehavioralSettings, Incident, Note, Rule
from tests.conftest import session_client

PUBLIC_IP = "8.8.8.8"


def _count(db_app, model, **where):
    async def q(session):
        stmt = select(model)
        for k, v in where.items():
            stmt = stmt.where(getattr(model, k) == v)
        return len((await session.execute(stmt)).scalars().all())
    return db_app(q)


def test_a_new_case_and_its_work_are_stored(db_app):
    alice = session_client("alice", "analyst")
    store.incidents_store.clear()

    case = alice.post("/api/incidents/from-ip", json={"ip": PUBLIC_IP}).json()
    assert _count(db_app, Incident, id=case["id"], assigned_to="alice") == 1
    assert not any(i["id"] == case["id"] for i in store.incidents_store)   # not kept in memory instead

    assert alice.patch(f"/api/incidents/{case['id']}", json={"status": "investigating"}).status_code == 200
    assert _count(db_app, Incident, id=case["id"], status="investigating") == 1

    assert alice.post(f"/api/incidents/{case['id']}/notes", json={"text": "looked at it"}).status_code == 200
    assert _count(db_app, Note, incident_id=case["id"], author="alice") == 1

    assert alice.get("/api/incidents").json()[0]["id"] == case["id"]   # read back from the database


def test_rules_are_stored(db_app):
    admin = session_client("admin", "admin")
    rule = admin.post("/api/rules", json={"name": "persisted"}).json()
    assert _count(db_app, Rule, id=rule["id"], name="persisted") == 1

    admin.patch(f"/api/rules/{rule['id']}", json={"enabled": False})
    assert _count(db_app, Rule, id=rule["id"], enabled=False) == 1

    admin.delete(f"/api/rules/{rule['id']}")
    assert _count(db_app, Rule, id=rule["id"]) == 0
    store._rules[:] = [r for r in store._rules if r["id"] != rule["id"]]


def test_behavioral_settings_are_stored_with_the_same_defaults(db_app):
    """The first write creates the row: untouched fields get the SAME defaults
    as everywhere else (reading used 8, writing used 15)."""
    admin = session_client("admin", "admin")
    saved = dict(store._behavioral_config)
    try:
        r = admin.patch("/api/behavioral/settings", json={"cooldown_min": 45})
        assert r.status_code == 200
        assert r.json()["repeated_threshold"] == 8

        async def row(session):
            return (await session.execute(select(BehavioralSettings))).scalar_one()
        stored = db_app(row)
        assert (stored.cooldown_min, stored.repeated_threshold) == (45, 8)
    finally:
        store._behavioral_config.clear()
        store._behavioral_config.update(saved)
