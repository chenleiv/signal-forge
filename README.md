# SignalForge

**[Live demo](https://signalforge-api-ah1q.onrender.com)**: no sign-up, use the [demo accounts](#demo-accounts). The first load can be slow while the server wakes up.

SignalForge is a Security Operations Center (SOC) dashboard for security analysts: watch threats in real time, triage alerts and investigate incidents, with role-based access control and AI-assisted IP analysis. Built with Angular 21 and FastAPI.

The attacking IPs come from the AbuseIPDB blacklist (or a bundled sample in demo mode when no list is available). The events around them are generated, so no real network is being monitored.

---

## Features

- **Live SOC Stream** — real-time threat event feed over WebSocket with severity color coding
- **Analytics Dashboard** — summary cards (tracked IPs, events, events per minute, regions, high severity, critical alerts) and charts for severity distribution, attack types, regions and top attacking IPs (Apache ECharts)
- **Threat Map** — animated D3.js world map showing attack origin → target lines in real time
- **Threat Intelligence** — IP index with split-view detail panel, MITRE ATT&CK tags, event timeline, and AbuseIPDB enrichment
- **AI Analysis** — per-IP threat summaries generated through the Groq API, displayed inline in the detail panel
- **Incidents** — incident log with split-view details, status tracking, response tasks, notes, and ownership (assignee)
- **Alerts** — live alert feed with severity filters; acknowledge, dismiss, or open a case from an alert
- **Detection Rules** — condition-based rules that raise alerts, open incidents, or block IPs
- **Threat Hunting** — query recent events and save hunts
- **Command Console** — terminal panel (toggle with `` ` ``) with commands: `help`, `status`, `block ip`, `unblock ip`, `scan`, and `clear` (handled in the browser)
- **Export** — CSV and PDF export of the threat table and the incident list
- **Users and roles** — `admin`, `manager` and `analyst` roles, user management screen; see [Security](#security) for the permission matrix
- **Authentication** — session in an HttpOnly cookie (8 hours), bcrypt-hashed passwords, rate-limited login
- **Demo mode** — read-only public demo with in-browser simulation of analyst actions
- **Settings** — WebSocket URL, reconnect delay, buffer size, theme, change your own password

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Angular 21, standalone components, Signals API, Vitest |
| Charts | Apache ECharts via ngx-echarts |
| Map | D3.js v7 + topojson-client |
| Backend | FastAPI, WebSockets, uvicorn, pytest |
| Database | Optional: SQLAlchemy (async) + Alembic — SQLite locally, Postgres in production; in-memory without `DATABASE_URL` |
| AI | Groq API (model set by `GROQ_MODEL`) |
| Threat Intel | AbuseIPDB (IP reputation), ipinfo (geolocation) |
| Auth | JWT (PyJWT, HS256) in an HttpOnly cookie, bcrypt password hashes, slowapi rate limits |
| Styling | SCSS, dark and light themes |

---

## Project Structure

```
signalforge/
├── backend/
│   ├── main.py              # App setup, lifespan, demo-mode middleware, WebSocket stream
│   ├── store.py             # In-memory state, session verification, config checks
│   ├── simulation.py        # Threat feed (AbuseIPDB, cache, snapshot, sample) and event generation
│   ├── constants.py         # Simulation data, MITRE map, response playbooks, behavioral defaults
│   ├── users.py             # Users, bcrypt, seeding, session checks
│   ├── user_admin.py        # Admin user management (create, role, password, soft delete)
│   ├── authz.py             # Authorization rules (single source for the server)
│   ├── repositories.py      # Storage: database or in-memory, one interface per data type
│   ├── sessions.py          # Logout revocation (per-session ids)
│   ├── rate_limit.py        # Per-IP and per-key rate limits
│   ├── schemas.py           # Typed request bodies (unknown fields, types, sizes: 422; notes ignore unknown fields)
│   ├── security_headers.py  # CSP, HSTS over HTTPS, no-store on the API
│   ├── request_limits.py    # Request body size limit (413 over 64 KB)
│   ├── routers/             # auth, users, incidents, alerts, rules, behavioral, hunting, ip
│   ├── database.py          # Async SQLAlchemy engine and session from DATABASE_URL
│   ├── models.py, db_ops.py # SQLAlchemy models and data access
│   ├── alembic/             # Database migrations
│   └── tests/               # pytest, including the security regression suite
├── testing/
│   └── permission-matrix.json  # RBAC matrix shared by backend and frontend tests
└── frontend/
    └── src/app/
        ├── core/
        │   ├── auth/        # Permission helper (client-side copy of the matrix)
        │   ├── services/    # ThreatStore, Threats, ThreatFeed, Auth, DemoMode, DemoSimulator, Settings, Theme
        │   ├── interceptors/# API base URL, 401 redirect, demo mode
        │   ├── guards/      # Auth guard (every page), admin guard (Users screen: admins and managers)
        │   └── utils/       # CSV and PDF export helpers
        ├── shared/
        │   ├── models/      # TypeScript interfaces
        │   └── ui/          # Export menu, filter pills, drawer resize
        ├── layout/          # AppLayout shell — sidebar, topbar, command console
        └── features/
            ├── dashboard/       # Live stream, ECharts panels, critical alerts
            ├── threat-map/      # D3 animated world map
            ├── threats/         # IP intelligence — split view (table + detail panel)
            ├── alerts/          # Live alert feed with filters
            ├── incidents/       # Incident management — split view (table + detail panel)
            ├── rules/           # Detection rules editor
            ├── admin-users/     # Admin user management
            ├── threat-hunting/  # Event queries and saved hunts
            ├── command-console/ # Terminal overlay
            ├── login/           # Login page (demo account buttons in demo mode)
            └── settings/        # App configuration
```

---

## Getting Started

### Prerequisites

- Node.js 26 (pinned in `.node-version`; CI reads it, and Render should too: check the build log after a deploy)
- Python 3.13 (pinned in `.python-version`; CI and Render read it, and `build.sh` stops on any other version)
- Angular CLI (`npm install -g @angular/cli`)

### Backend

```bash
cd backend
python3.13 -m venv venv
source venv/bin/activate
pip install --require-hashes --no-deps -r requirements-dev.txt   # locked runtime deps + pytest, ruff, pip-audit

cp .env.example .env
# Edit .env. For local development set at least:
#   JWT_SECRET=<random, at least 32 bytes>   (required, startup fails without it)
#   ENV=development                     (allows the session cookie over plain HTTP)
#   CORS_ORIGINS=http://localhost:4200  (ng serve calls the API on port 8000, another origin;
#                                        exact origins, comma-separated; unset allows none)
# Leave DEMO_MODE unset (demo mode is ON by default), or set DEMO_MODE=false
# together with ADMIN_PASSWORD (12-72 bytes) to run with writes enabled.

python3 -m uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`. API docs (Swagger UI at `/docs`, ReDoc at `/redoc`) are served only with
`ENABLE_API_DOCS=true`, for local development; otherwise those paths fall through to the SPA.
Without `DATABASE_URL` everything is kept in memory; with it, migrations run on startup and a failed migration stops the server.

### Environment variables

Every variable the backend reads (`backend/.env.example` lists the same names with empty values; an empty value
means "use the default"). Never commit real values.

| Name | Default | Required | Stops startup |
|---|---|---|---|
| `JWT_SECRET` | none | yes | when missing or shorter than 32 bytes |
| `DEMO_MODE` | on (anything but `false`) | no | no |
| `ADMIN_PASSWORD` | empty | with `DEMO_MODE=false`, until an admin with a real password exists | with `DEMO_MODE=false`: when set but not 12-72 bytes; when empty and there is no database; when empty and the database has no admin or the admin still has the demo password |
| `DATABASE_URL` | empty: in-memory storage | no | when a migration fails, or the database holds more than one active admin |
| `ENV` | empty: the session cookie is `Secure` | `development` for local plain HTTP | no |
| `CORS_ORIGINS` | empty: no cross-origin caller | for local `ng serve` | when an entry is not an exact lowercase `http(s)://host[:port]` origin |
| `ENABLE_API_DOCS` | off (only `true` turns it on) | no | no |
| `TRUSTED_PROXY_HOPS_HTTP` | 1 | no (Render: 2) | when not a non-negative integer |
| `TRUSTED_PROXY_HOPS_WS` | 1 | no (Render: 1) | when not a non-negative integer |
| `TRUSTED_PROXY_HOPS` | none (legacy name) | must not be set | **refused**: any non-empty value stops startup |
| `ABUSEIPDB_API_KEY` | empty: cached list, or the bundled sample in demo mode | no | no |
| `IPINFO_TOKEN` | empty: built-in geolocation data | no | no |
| `GROQ_API_KEY` | empty: no AI summaries (`{"summary": null}`) | no | no |
| `GROQ_MODEL` | `openai/gpt-oss-20b` (also when empty) | no | no |
| `THREAT_IPS_CACHE` | `backend/threat_ips_cache.json` | no | no |

Outside the backend: `PORT` is set by Render for the start command, and `BACKEND_PYTHON` points the e2e tests at
another Python (default `backend/venv`).

### Updating Python dependencies

`requirements.in` (runtime) and `requirements-dev.in` (tests, lint, audit) are the sources. `requirements.txt` and
`requirements-dev.txt` are generated locks with hashes: never edit them by hand. `build.sh` installs `requirements.txt`
with `--require-hashes`, so Render runs exactly the tested versions.

```bash
cd backend
python3.13 -m venv ~/.venvs/sf-piptools            # outside the repo; a separate venv because pip-tools pins pip
~/.venvs/sf-piptools/bin/python -m pip install --require-hashes --no-deps -r requirements-tools.txt
~/.venvs/sf-piptools/bin/pip-compile requirements.in                               # after editing requirements.in
~/.venvs/sf-piptools/bin/pip-compile -o requirements-dev.txt requirements-dev.in   # always after requirements.txt
~/.venvs/sf-piptools/bin/pip-compile -P uvicorn requirements.in                    # upgrade one package; then rerun the
                                                                                   # dev line with the same -P flag
pip install --require-hashes --no-deps -r requirements-dev.txt && ruff check . && python -m pytest
pip-audit --require-hashes --disable-pip -r requirements.txt
```

Options come from `backend/.pip-tools.toml`. Existing pins are kept unless `-P name` (or `-U`, all packages) is given.
CI (`python-lock`) recompiles every lock on Linux and fails if the result differs from the committed file, so commit
the `.in` file and its lock together.

### Frontend

```bash
cd frontend
npm install
ng serve
```

App runs on `http://localhost:4200`.

### Demo accounts

In demo mode (the default) these public accounts exist, and the login page has
**Try as Admin** and **Try as Analyst** buttons:

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin-demo` | admin ("SOC Admin") |
| `manager` | `manager-demo` | manager ("SOC Manager") |
| `analyst` | `analyst-demo` | analyst ("Tier 1 Analyst") |

Former demo accounts (`alice`, `bob`, `manny`, `anna`) are retired: a stored row that still has its old public password is
never loaded, in any mode.

They are **never created when `DEMO_MODE=false`**. Outside demo mode the only seeded account is `admin`,
with the password from `ADMIN_PASSWORD`.

**Switching an existing demo deployment to real mode** (same database, `DEMO_MODE=false`): set `ADMIN_PASSWORD`
first. On startup the admin's public demo password is replaced with it and every demo session is signed out;
without `ADMIN_PASSWORD` the server refuses to start. The demo analyst and manager accounts can no longer log in.
A real admin password, once set, is never overwritten by `ADMIN_PASSWORD`.

### Tests

```bash
cd backend && ruff check . && python -m pytest   # lint + all backend tests
cd frontend && npm run lint                       # ESLint (incl. template accessibility rules)
cd frontend && npm test -- --watch=false          # all frontend tests (Vitest)
cd frontend && npm run e2e                        # layout and behaviour checks in a real browser (Playwright)
```

**CI** (`.github/workflows/ci.yml`) runs all of the above on every pull request and on `master`, plus the production
build and the link-preview tag check, and three dependency jobs that also run weekly: `python-lock` (the locks match
their `.in` files), `pip-audit` (fails on any known advisory in `requirements.txt`; the dev and pip-tools locks are
only reported) and `npm-audit` (fails on a high or critical advisory in the runtime packages; the full tree is only
reported).

**Browser checks (`npm run e2e`).** Builds the frontend, serves it from the backend in demo mode (like on Render,
no database), and checks every page on a phone (390 px), a tablet (820 px) and a desktop (1440 px), each in its own
pass on a fresh server: nothing may be cut off by the
screen edge (only wide tables scroll sideways, inside `.h-scroll`), the phone menu opens and closes, and logout
is reachable. Behaviour specs in `frontend/e2e/` also cover the WebSocket ticket and session expiry, failed
incident updates and saving settings. Tests only talk to the local server: every other request is blocked. First run:
`npx playwright install chromium`. The backend virtualenv is expected at `backend/venv` (override with
`BACKEND_PYTHON`). When the e2e job fails in CI, the traces and screenshots of the failed tests are uploaded as the
`e2e-results-attempt-N` artifact for 7 days; open a trace with `npx playwright show-trace <trace.zip>`.

---

## API Endpoints

All endpoints require a session except those marked *public*. Role requirements are enforced by the server.

| Method | Path | Description | Who |
|--------|------|-------------|-----|
| POST | `/auth/login` | Log in, sets the session cookie (rate-limited) | public |
| POST | `/auth/logout` | End this session (revoked on the server) and clear the cookie | public |
| GET | `/auth/me` | Current user: username, display name, role | any user |
| PATCH | `/auth/me` | Change your own password: exactly `{current_password, new_password}` | any user (not in demo) |
| GET | `/auth/ws-ticket` | Short-lived (5 min) ticket for the WebSocket | any user |
| WS | `/ws/threats` | Live threat event stream; the first message must be `{"type":"auth","ticket":"…"}` | valid ticket |
| GET | `/api/config` | `{demo_mode}` | public |
| GET | `/api/threat-feed` | Threat feed `{state, reason}` (see below) | any user |
| GET | `/api/users` | Active users (no password hashes) | any user |
| GET | `/api/users/directory` | Every name ever used, incl. deleted users (for history) | any user |
| POST | `/api/users` | Create a user | admin |
| PATCH | `/api/users/{username}` | Change role and/or reset password (signs the user out) | admin, or manager for an analyst's password only |
| DELETE | `/api/users/{username}` | Delete a user (soft delete; never the admin account, `403`; not yourself, `409`) | admin |
| GET | `/api/stats` | Aggregated chart data | any user |
| GET | `/api/incidents` | Incident list | any user |
| PATCH | `/api/incidents/{id}` | Change status / assignee | see matrix |
| POST | `/api/incidents/{id}/notes` | Add a note | assignee, manager or admin |
| PATCH | `/api/incidents/{id}/tasks` | Update completed response tasks | assignee, manager or admin |
| POST | `/api/incidents/from-ip` | Open a case for an IP (assigned to the creator) | any user |
| GET | `/api/alerts`, `/api/alerts/summary` | Alerts and metrics | any user |
| PATCH | `/api/alerts/{id}` | Acknowledge / dismiss | any user |
| POST | `/api/alerts/{id}/case` | Open a case from an alert (assigned to the creator) | any user |
| GET | `/api/rules` | Detection rules | any user |
| POST, PATCH, DELETE | `/api/rules`, `/api/rules/{id}` | Create / edit / toggle / delete rules | admin |
| GET | `/api/behavioral/settings` | Behavioral detection settings | any user |
| PATCH | `/api/behavioral/settings` | Change behavioral detection settings | admin |
| GET | `/api/hunt`, `/api/hunts` | Run a hunt / list saved hunts (shared, each with its `created_by`) | any user |
| POST | `/api/hunts` | Save a hunt (20 per user, 100 in total, `409` past either) | any user |
| DELETE | `/api/hunts/{id}` | Delete a saved hunt (`404` if it does not exist) | its creator or admin |
| GET | `/api/ip/{ip}/history`, `/geo`, `/related`, `/case`, `/block` | IP intelligence and status | any user |
| GET | `/api/ip/{ip}/ai-summary` | AI-generated threat summary | any user |
| POST, DELETE | `/api/ip/{ip}/block` | Block / unblock an IP | any user |
| POST | `/api/command` | Command console | any user |
| GET, HEAD | `/health` | Health check (HEAD for uptime monitors, not in the schema) | public |

---

## Architecture

```
Browser
  └── Angular 21 (port 4200)
        ├── WebSocket → /ws/threats            (live events; ticket from /auth/ws-ticket as the first message)
        └── HTTP      → /api/*, /auth/*        (session in an HttpOnly cookie)

FastAPI (port 8000)
  ├── Demo-mode middleware  → rejects every write in demo mode (before any route runs)
  ├── Event generator       → ONE shared stream, fanned out to every WebSocket client
  ├── /auth/*               → login (bcrypt, rate limits), session, WebSocket tickets
  ├── /api/*                → routers → authz.py (permissions) → repositories.py
  └── Storage               → database (SQLAlchemy + Alembic) with DATABASE_URL, else in memory
```

Routers never branch on the storage: `repositories.py` gives them the database or the in-memory implementation, and both are tested the same way (the permission matrix and `test_storage_parity.py` run in both modes).

### Threat feed

The live stream is built from the AbuseIPDB blacklist (fetched at most once a day; the free tier allows only a few
blacklist calls per day). The last list is kept in a file cache and, with a database, in the `threat_feed_snapshot`
table, so a restart on a host with an ephemeral disk (Render) does not spend the quota.

| State | Meaning |
|-------|---------|
| `live` | A list fetched within the last day |
| `cached` | An older stored list, because the refresh failed (`reason`: `quota`, `error`) or there is no `ABUSEIPDB_API_KEY` (`reason`: `no_key`) |
| `sample` | Demo mode only, with no stored list: the bundled `threat_ips_sample.json` |
| `unavailable` | Nothing to stream (outside demo mode, sample data is never used) |

While the feed is not `live` the backend retries: at the quota reset when a 429 carries `Retry-After` (clamped to 5 minutes - 24 hours), daily when there is no `ABUSEIPDB_API_KEY`, otherwise hourly. The UI shows a banner for `sample` and `unavailable`.
Stored lists are validated before use: public IPs with an integer score 0-100, at most 1000 entries.

The frontend uses a central `ThreatStoreService` (Angular signals) as the single source of truth for HTTP calls and cached state. WebSocket events are pushed into the store, and components react to signal changes. The current user (from `/auth/me`) lives in `AuthService`; the UI hides or disables actions the user is not allowed to take, using the same permission rules as the server.

---

## Security

The server is the security boundary. Everything the frontend does with permissions is UX only.

### Sessions and tokens

- **Session:** a JWT in the `sf_session` cookie — `HttpOnly`, `SameSite=Lax`, `Secure` unless `ENV=development`, 8 hours.
  Claims: `sub` (username), `role`, `sk` (the user's session key), `sid` (this session's own id), `typ: "session"`,
  `exp`. Never stored in `localStorage`.
- **Logout ends the session on the server,** not only in the browser: the session's `sid` is revoked until the token
  would have expired, so a copied cookie stops working at once. Only that session ends: other devices of the same
  user, and other visitors of a shared demo account, stay signed in. Revocations are kept in memory and, with a
  database, in `revoked_sessions` (reloaded at startup, expired rows dropped).
- **WebSocket ticket:** a separate 5-minute JWT with `typ: "ws"`, fetched from `/auth/ws-ticket` and sent as the
  first WebSocket message, never in the URL, so it cannot appear in server or proxy access logs. The server answers
  `{"type":"ready"}`, closes with 4001 on a missing or invalid ticket, and with 4408 when none arrives within 5 seconds.
  The ticket carries the session's expiry (`sexp`): an open stream closes with 4001 when the 8-hour session expires.
- **WebSocket limits:** at most 20 open sockets per client IP and 500 in total, authenticated or not; over either cap
  the handshake is refused with `429` (the browser reports a failed connection and retries with backoff). Each
  incoming message is limited to 8 KiB by uvicorn (`--ws-max-size 8192` in the start command; uvicorn's default is
  16 MiB, decompressed size included): a larger one closes with 1009. The stream is one-way: any frame the client
  sends after `ready` closes it with 1008. The per-IP cap uses the same client IP as the rate limits below, so it is
  only per user if the proxy adds `X-Forwarded-For` to WebSocket upgrade requests and `TRUSTED_PROXY_HOPS_WS` is right
  (see the Deployment checklist); otherwise every user shares one count.
- Every decode site accepts only `HS256` and only its own `typ`, so a ticket cannot be used as a session and vice versa.
  `alg: none`, forged signatures, expired tokens, and tampered claims (e.g. `role` changed to `admin`) are rejected.
- Every request also checks the token against the **current** user record: the user must still exist, have
  the role in the token, and still have the session key in the token. So deleting a user, changing their role or
  resetting their password takes effect **immediately** on every HTTP request; an open WebSocket stream closes at its
  next check, within about 2 seconds.
- The server refuses to start without a `JWT_SECRET` of at least 32 bytes, and with `DEMO_MODE=false` when there is
  no admin yet (or the admin still has the demo password) and no `ADMIN_PASSWORD` of 12-72 bytes.

### Passwords and login

- Passwords are hashed with bcrypt. Passwords longer than bcrypt's 72-byte limit are rejected, not truncated.
- An unknown username and a wrong password return the same `401` and take about the same time (a dummy hash is checked),
  so the login does not reveal which accounts exist.

### Roles and permissions

| Action | analyst | manager | admin |
|---|---|---|---|
| Read all data | ✓ | ✓ | ✓ |
| Change incident status, add notes, update tasks | own incidents only | ✓ | ✓ |
| Take an unassigned incident for themselves | ✓ | ✓ | ✓ |
| Assign / reassign / unassign any incident | ✗ | ✓ | ✓ |
| Open a case from an IP or an alert (assigned to the creator) | ✓ | ✓ | ✓ |
| Acknowledge / dismiss alerts | ✓ | ✓ | ✓ |
| Block / unblock IPs, command console, save hunts | ✓ | ✓ | ✓ |
| Delete a saved hunt | own only | own only | ✓ |
| Detection rules (create / edit / toggle / delete) | ✗ | ✗ | ✓ |
| Behavioral detection settings | ✗ | ✗ | ✓ |
| Reset a user's password | ✗ | analysts only | ✓ |
| Create users, change roles (analyst ↔ manager), delete users (never the admin) | ✗ | ✗ | ✓ |

"Own" means `incident.assigned_to` is the caller. `assigned_to` must be an existing user (`422` otherwise).
For a saved hunt, "own" means `created_by` is the caller; a hunt with no `created_by` can be deleted by the admin
only. Managers have no extra rights over other users' hunts. The saved hunts list is shared and shows every owner.
Denied actions return `403` with a clear message. Every field of a request is checked against the incident's
current state; with a database, the write is conditional on the assignee the check saw (`409` if it changed).

All rules live in `backend/authz.py`. The frontend mirrors them in `frontend/src/app/core/auth/permissions.ts`.
[`testing/permission-matrix.json`](testing/permission-matrix.json) is the source of truth for both: the backend
test suite sends every case to the real API, and the frontend suite runs the same cases through the client-side
check, so the two cannot silently diverge.

### User management

- Admins create users, change roles, reset passwords and delete users (`/admin/users` in the UI).
- Managers open the same screen but can only reset **analysts'** passwords; a reset request must contain the
  password and nothing else (`403` otherwise).
- New and reset passwords follow the same rule as `ADMIN_PASSWORD` (12-72 bytes). Only `role` and `password` can be
  changed; anything else in the request is rejected (`422`).
- **Your own password** changes only in Settings (`PATCH /auth/me`), which asks for the current one: nobody, not
  even the admin, resets their own password from the Users screen (`403`), so a stolen session cannot set it.
  Only `current_password` and `new_password` are accepted (anything else is a `422`, never silently ignored). A
  wrong current password counts toward a per-user limit (5/minute, 20/hour, then `429`). A change signs out every
  other session of the user; the session that made it stays signed in. Blocked in demo mode: the demo accounts are
  shared.
- **There is exactly one admin.** The admin account cannot be deleted, and the admin role can never be granted to
  another user or removed from the admin, not even by the admin (`403`). New users are created as analysts or
  managers. At startup the server refuses to run if the database holds more than one active admin.
- **Deleting is a soft delete.** The user can no longer log in or be assigned, disappears from the user list and
  the assignee options, and their open incidents become unassigned. History (closed incidents, notes) keeps their
  name, and the username can never be reused, so old records never point at a different person.

### Demo mode

- **On unless `DEMO_MODE=false`** (fails closed). A middleware rejects every request other than `GET`, `HEAD` and
  `OPTIONS` with `403 {"detail": "Read-only demo"}`, except `POST /auth/login` and `POST /auth/logout`. It runs before
  any route or permission check.
- With a database, startup in demo mode puts the demo accounts back to their seeded names and roles, and resets the
  `admin` password to the public demo password if it was changed.
- In the browser, common analyst actions are simulated locally (nothing is saved) so the demo stays interactive.
  The simulation applies the same permission rules, so it never "succeeds" at something the real server would deny.
- The public demo accounts exist only in demo mode, and are exempt from the per-account login lockout
  (their passwords are public; a lockout would only let anyone lock visitors out).

### Rate limits

| Limit | Scope |
|---|---|
| Login (`POST /auth/login`): 5/minute | per client IP |
| Login failures: 10/minute, 100/hour (not for the demo accounts in demo mode) | per account, across all IPs |
| WebSocket tickets (`/auth/ws-ticket`): 60/minute | per client IP |
| Stats (`/api/stats`): 50/minute | per client IP |
| IP intelligence (`/api/ip/{ip}/history`, `/geo`, `/related`, `GET /block`): 30/minute each; `/ai-summary`: 10/minute | per client IP, per route |
| Block / unblock an IP (`POST`, `DELETE /api/ip/{ip}/block`), console (`/api/command`): 20/minute each | per client IP, per route |
| Writes: 30/minute each (`WRITE_LIMIT`): logout, `PATCH /auth/me`, every incident and alert write, opening a case, saving and deleting a hunt | per client IP, per route |
| Running a hunt (`GET /api/hunt`, scans every stored event): 30/minute (`WRITE_LIMIT`) | per client IP |
| Admin writes: 20/minute each (`ADMIN_WRITE_LIMIT`): create, change and delete users, every rule write, behavioral settings | per client IP, per route |
| Reads: alerts, alerts summary, saved hunts, users, user directory, `/auth/me`, threat feed status, `/api/config`: 120/minute (`READ_LIMIT`) | per client IP, per route |
| Database reads: incidents, rules, behavioral settings, open case for an IP: 60/minute (`DB_READ_LIMIT`) | per client IP, per route |
| New cases: 5/minute, 30/hour | per user |
| Wrong current password on `PATCH /auth/me`: 5/minute, 20/hour | per user |
| AI summaries that call Groq: 5/minute, 50/day | per user and client IP together |
| AI summaries that call Groq, whole server: 500/day | all users |
| Geolocation lookups that call ipinfo: 20/minute, 300/day | per user and client IP together |
| AbuseIPDB lookups for IP history: 20/minute, 300/day | per user and client IP together |
| WebSocket connections open at once: 20 | per client IP (and 500 in total) |

- Every rate-limit `429` on an HTTP route carries `Retry-After` (seconds). Per-IP limits answer
  `{"error": "Rate limit exceeded: ..."}`, the per-account and per-user ones `{"detail": "..."}`. The WebSocket cap is
  the exception: the handshake is refused with `429 {"detail": "Too many open streams"}` and no `Retry-After` (or, if
  the server cannot send a denial response, the socket closes with 1013). The frontend pauses stats and alerts polling for that time
  (one minute when the header is missing).
- The external lookup quotas count only requests that really call the service: a cached answer or a missing API key
  costs nothing, and a failed or timed-out call still counts. They are keyed by user and client IP together, so
  visitors sharing a demo account keep separate quotas. A used-up AI summary or geolocation quota answers `429`;
  a used-up history quota still returns the events, without the AbuseIPDB fields. The Groq client times out after
  10 seconds with no retries.
- `/health` and the SPA files have no limit. Unauthenticated requests are refused (`401`) before the
  read limits count them.

- **Client IP** is the `X-Forwarded-For` entry at position `-hops` (counted from the right). Leftmost entries are
  client-controlled and never used, so a spoofed header cannot rotate the key.
- Start uvicorn with `--no-proxy-headers`. Render's uvicorn trusts every peer (`FORWARDED_ALLOW_IPS='*'`), so without
  the flag uvicorn replaces the client address with the leftmost, client-chosen entry: measured on Render, a forged
  `X-Forwarded-For: 203.0.113.9` showed up in the access log as `203.0.113.9:0`. With the flag the client address is
  the real TCP peer (Render's proxy) and the access log shows that instead of a client IP.
- `hops` differs per connection type, because on Render HTTP requests and WebSocket upgrades pass through a
  different number of proxies (measured: HTTP 2 entries, WebSocket 1):

  | Variable | Used for | Default | Render |
  |---|---|---|---|
  | `TRUSTED_PROXY_HOPS_HTTP` | every HTTP rate limit above | 1 | 2 |
  | `TRUSTED_PROXY_HOPS_WS` | the WebSocket per-IP cap (upgrade request) | 1 | 1 |

- Too high: a client-chosen entry becomes the key and per-IP limits can be bypassed. Too low: the key is a proxy's
  address, so every user behind it shares one count. Fewer entries than `hops`: the limit fails closed, every user
  shares one fixed key (`xff-short-chain`) and one count, and the server logs one warning per process (counts only,
  never an address). `0` ignores the header and uses the connection address, which is only safe with
  `--no-proxy-headers` or no proxy in front.
- The old single `TRUSTED_PROXY_HOPS` is **refused**: the server will not start while it is set to a non-empty
  value. No single value fits both paths (docs/DECISIONS.md).
- Every per-key limit has its own namespace, so counters can never be shared between limits.
- Counters are **in memory, per process**: they are only correct with a single uvicorn worker.

### Input validation and SSRF

- IP addresses from paths, bodies and console commands must be valid public addresses: private, loopback,
  link-local (e.g. `169.254.169.254`), reserved and multicast ranges, and obfuscated forms, are rejected (`422`).
- Incident status, assignees, notes (non-empty string, max 2000 characters) and completed tasks (unique indexes
  within the incident's playbook) are validated (`422`, never `500`).
- The blocklist is capped at 1000 entries.

### Security headers

Set on every HTTP response, error responses and CORS preflights included (`backend/security_headers.py`, the
outermost middleware):

- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`,
  `Permissions-Policy: camera=(), microphone=(), geolocation=()`, `Cross-Origin-Opener-Policy: same-origin`.
- **CSP for the SPA:** `script-src 'self'` (no inline scripts); styles from `'self'`, inline (Angular injects
  component styles) and Google Fonts; `connect-src 'self'` plus the world map data on `cdn.jsdelivr.net`;
  `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'`.
- **CSP for `/api/`, `/auth/` and `/health`:** `default-src 'none'; frame-ancestors 'none'`, plus
  `Cache-Control: no-store`.
- Only the exact docs paths (`/docs`, `/docs/oauth2-redirect`, `/redoc`) skip the CSP, and only while
  `ENABLE_API_DOCS=true`.
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` over HTTPS (directly, or the last
  `X-Forwarded-Proto` value is `https`).
- Request bodies over 64 KB get `413` (`backend/request_limits.py`).

### CORS

- Production serves the SPA from the API service (same origin) and needs no CORS origin.
- `CORS_ORIGINS` lists exact origins, comma-separated (for local `ng serve`: `http://localhost:4200`). Unset or
  empty allows none. A wildcard, a path, a trailing slash or uppercase stops startup.
- Allowed methods `GET`, `POST`, `PATCH`, `DELETE`; the only allowed request header is `Content-Type`; credentials
  (the session cookie) are allowed. No response header is exposed, so a cross-origin client cannot read
  `Retry-After` and falls back to one minute.

### Running the security tests

```bash
cd backend
python -m pytest tests/test_security.py tests/test_authz.py tests/test_permission_matrix.py \
                 tests/test_auth.py tests/test_rate_limit.py tests/test_input_limits.py
cd ../frontend
npm test -- --watch=false
```

`tests/test_security.py` is an attack-style regression suite: token confusion, JWT attacks, a route-auth check that
discovers every route from the OpenAPI schema (new routes must require a session unless listed in `PUBLIC_ROUTES`),
SSRF, and demo mode. Security tests are mutation-checked: each check is broken on purpose to confirm a test fails.

### Deployment checklist

- Set `JWT_SECRET` (random, at least 32 bytes: `python -c "import secrets; print(secrets.token_urlsafe(48))"`), and either leave demo mode on or set `DEMO_MODE=false` with `ADMIN_PASSWORD`.
- Run a **single** uvicorn worker (rate-limit counters and WebSocket counts are per process).
- Start command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT --ws-max-size 8192 --no-proxy-headers`
  (on Render: the API service, Settings → Start Command). Without `--ws-max-size` each WebSocket message may be
  16 MiB. Without `--no-proxy-headers` the client address uvicorn reports is client-chosen (Client IP above).
  FastAPI's trailing-slash redirect is off (`redirect_slashes=False` in `main.py`): with the flag it would point at
  `http://`. A path with a trailing slash gets 404, or the SPA when `backend/static` exists.
- Check after a deploy: `curl -H "X-Forwarded-For: 203.0.113.9" https://signalforge-api-ah1q.onrender.com/health`,
  then the Render logs of the API service: the access log line must not show `203.0.113.9`.
- `uvicorn` is pinned with every other package in `backend/requirements.txt` (0.54.0), so Render runs the version
  that `tests/test_proxy_headers_uvicorn.py` and `tests/test_ws_max_size_uvicorn.py` checked. Upgrading it means
  rerunning both (see Updating Python dependencies).
- Render picks Python from `.python-version` (build log: "Using Python version 3.13.18 via .python-version"), with
  no `PYTHON_VERSION` set. `build.sh` stops the build on any version other than 3.13.
- **Proxy hops.** On Render set `TRUSTED_PROXY_HOPS_HTTP=2` and `TRUSTED_PROXY_HOPS_WS=1` (measured, see
  docs/DECISIONS.md), and **delete** `TRUSTED_PROXY_HOPS` (the server refuses to start while it is set). On another
  host, or if Render changes its proxy chain, keep both at 1 until re-measured.
- **Re-measuring the hops** needs the salted hash diagnostic, which was removed. Restore it from git history (last
  present in `eede244`, the merge of PR #43) on a temporary branch, follow "How to re-measure" in docs/DECISIONS.md
  ("Separate proxy hop counts for HTTP and WebSocket"), record the result there, then remove it again.
- Never commit `backend/.env` or the local SQLite database (both are git-ignored; the database holds password hashes).

---

## AI-Assisted Engineering

The repository includes a Claude Code setup (`.claude/`) that acts as an engineering team: specialized review
agents, workflow commands, and review checklists (skills).

```
.claude/
├── CLAUDE.md                 # Project rules (plan first, no silent architecture changes, keep security controls)
├── memory/context.md         # Stack, architecture and rules loaded by every agent
├── agents/
│   ├── context-analyzer      # Analyzes a change and routes it to the right reviewers
│   ├── frontend-architect    # Angular architecture: standalone components, Signals, RxJS
│   ├── backend-architect     # FastAPI structure, API boundaries, validation
│   ├── database-reviewer     # Schema, migrations, data access
│   ├── realtime-engineer     # WebSocket and realtime flows
│   ├── performance-engineer  # Frontend, backend and realtime performance
│   ├── security-auditor      # AuthN/AuthZ, JWT handling, XSS, SSRF, secret exposure
│   ├── dependency-auditor    # Dependency and package changes
│   ├── soc-analyst           # SOC product realism (is this useful to an analyst?)
│   └── quality-gatekeeper    # Release validation: types, tests, build
├── commands/
│   ├── feature               # Plan, then build
│   ├── debug                 # Root cause first
│   ├── review                # Focused code review
│   ├── ship                  # Validate before commit
│   └── cleanup               # Remove implementation leftovers
└── skills/                   # Review checklists: angular21, fastapi, security, testing, websocket
```

## Workflow

Changes follow a structured lifecycle, one reviewable step at a time:

Plan
→ Owner approval
→ Implement (minimal, focused changes)
→ Tests, including mutation checks for security tests
→ Security review of the diff (how could an attacker abuse each change, and what stops them)
→ Commit (one commit per step)

Before release, changes pass through:

- Architecture and security review
- TypeScript checks (`npx tsc --noEmit`)
- Backend and frontend test suites
- Production build (`ng build`)

---

## License

[MIT](LICENSE)
