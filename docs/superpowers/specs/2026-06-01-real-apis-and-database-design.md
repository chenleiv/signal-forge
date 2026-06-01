# Real APIs + Database — Design Spec
Date: 2026-06-01

## Goal

Replace simulated threat data with real IPs from AbuseIPDB, and persist incidents/notes
to PostgreSQL so data survives server restarts. No frontend changes required.

---

## Part 1 — AbuseIPDB Live Feed

### What changes

`THREAT_IPS` is currently a hardcoded list of 12 IPs. After this change, it is populated
at startup from AbuseIPDB's blacklist endpoint and refreshed every 6 hours.

### Endpoint

```
GET https://api.abuseipdb.com/api/v2/blacklist
Headers: Key: <ABUSEIPDB_API_KEY>
Params:  confidenceMinimum=90, limit=100
```

Returns a list of IPs with confidence scores ≥ 90 (highly reported attackers).

### Startup flow

1. `lifespan` calls `_refresh_threat_ips()` before yielding
2. `_refresh_threat_ips()` fetches blacklist → extracts IP strings → stores in `THREAT_IPS`
3. If fetch fails or `ABUSEIPDB_API_KEY` is empty → `THREAT_IPS` keeps the hardcoded fallback
4. Also enrich fetched IPs via IPInfo for geo coords (existing `_fetch_ipinfo` logic)

### Background refresh

A background `asyncio.Task` started in `lifespan` calls `_refresh_threat_ips()` every 6 hours.
Task is cancelled on shutdown via the lifespan context manager.

### Fallback

If no key is set, or the request fails, the existing 12-IP hardcoded list is used unchanged.
The simulation continues to work in local dev without any API key.

---

## Part 2 — PostgreSQL Persistence

### What is persisted

Only incidents and their associated data. Threat events remain in-memory (they are a
live stream that regenerates on every run — no value in persisting them).

### Schema

```sql
-- incidents
CREATE TABLE incidents (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',
    severity    TEXT NOT NULL,
    attack_type TEXT NOT NULL,
    source_ip   TEXT,
    source_region TEXT,
    event_count INTEGER NOT NULL DEFAULT 0,
    mitre_tags  TEXT NOT NULL DEFAULT '[]',  -- JSON array stored as text
    assigned_to TEXT,
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL
);

-- notes
CREATE TABLE notes (
    id          TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    author      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);

-- incident_tasks
CREATE TABLE incident_tasks (
    incident_id  TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    task_index   INTEGER NOT NULL,
    PRIMARY KEY (incident_id, task_index)
);
```

### Stack

- **SQLAlchemy 2.0 async** (`sqlalchemy[asyncio]`) with `asyncpg` driver
- **Alembic** for migrations — auto-run at startup via `alembic upgrade head`
- Connection string via `DATABASE_URL` env var

### Migration strategy

Alembic runs `upgrade head` during `lifespan` before the app starts serving requests.
This means the schema is always up to date on every deploy. Alembic version files
live in `backend/alembic/versions/`.

### API compatibility

All existing API endpoints keep the same URLs and response shapes. Only the internal
storage layer changes from `deque`/`dict` to async DB calls.

Affected endpoints:
- `GET /api/incidents` — reads from DB instead of `incidents_store`
- `PATCH /api/incidents/{id}` — updates DB row
- `POST /api/incidents/{id}/notes` — inserts into `notes` table
- `PUT /api/incidents/{id}/tasks` — replaces rows in `incident_tasks`

New incidents created by the simulation (`_create_incident`) are written to DB instead of
the in-memory deque.

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes (prod) | PostgreSQL connection string. Render injects automatically. |
| `ABUSEIPDB_API_KEY` | No | If absent, falls back to hardcoded IP list. |
| `IPINFO_TOKEN` | No | Geo enrichment. Already wired. |

Local `.env` already has `ABUSEIPDB_API_KEY`. Add `DATABASE_URL` pointing to a local
PostgreSQL instance for local DB testing, or omit to keep using in-memory behavior.

**`DATABASE_URL` absent behavior:**
- Local dev (no `DATABASE_URL`): app falls back to current in-memory `deque` — no DB required
- Production (Render): Render injects `DATABASE_URL` automatically — if missing, app fails at
  startup with a clear error (misconfiguration should be loud)

**Existing in-memory data on first deploy:** incidents in the old in-memory deque are lost
on the first DB-enabled deploy. This is acceptable — the deque was ephemeral anyway and
reset on every restart before this change.

---

## New dependencies

```
sqlalchemy[asyncio]>=2.0
asyncpg
alembic
```

---

## Out of scope

- Persisting threat events (they are ephemeral by design)
- User authentication persistence (JWT is stateless)
- Any frontend changes
