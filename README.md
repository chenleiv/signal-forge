# SignalForge

A real-time Security Operations Center (SOC) dashboard built with Angular 21 and FastAPI. Simulates live threat intelligence with animated attack maps, analytics charts, incident management with role-based access control, and AI-powered threat analysis.

---

## Features

- **Live SOC Stream** — real-time threat event feed over WebSocket with severity color coding
- **Analytics Dashboard** — severity distribution, attack types, events-per-minute trend, and top attacking IPs (Apache ECharts)
- **Threat Map** — animated D3.js world map showing attack origin → target lines in real time
- **Threat Intelligence** — IP index with split-view detail panel, MITRE ATT&CK tags, event timeline, and AbuseIPDB enrichment
- **AI Analysis** — per-IP threat summaries generated through the Groq API, displayed inline in the detail panel
- **Incidents** — incident log with split-view details, status tracking, response tasks, notes, and ownership (assignee)
- **Alerts** — live alert feed with severity filters; acknowledge, dismiss, or open a case from an alert
- **Detection Rules** — condition-based rules that raise alerts, open incidents, or block IPs
- **Threat Hunting** — query recent events and save hunts
- **Command Console** — terminal panel (toggle with `` ` ``) with commands: `help`, `status`, `block ip`, `unblock ip`, `scan`
- **Users and roles** — `admin`, `manager` and `analyst` roles, user management screen; see [Security](#security) for the permission matrix
- **Authentication** — session in an HttpOnly cookie (8 hours), bcrypt-hashed passwords, rate-limited login
- **Demo mode** — read-only public demo with in-browser simulation of analyst actions
- **Settings** — WebSocket URL, reconnect delay, buffer size, alert thresholds, theme

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
| Auth | JWT (python-jose, HS256) in an HttpOnly cookie, bcrypt password hashes, slowapi rate limits |
| Styling | SCSS, dark and light themes |

---

## Project Structure

```
signalforge/
├── backend/
│   ├── main.py              # App setup, lifespan, demo-mode middleware, WebSocket stream
│   ├── store.py             # In-memory state, session verification, config checks
│   ├── users.py             # Users, bcrypt, seeding, session checks
│   ├── user_admin.py        # Admin user management (create, role, password, soft delete)
│   ├── authz.py             # Authorization rules (single source for the server)
│   ├── rate_limit.py        # Per-IP and per-key rate limits
│   ├── routers/             # auth, users, incidents, alerts, rules, behavioral, hunting, ip
│   ├── models.py, db_ops.py # SQLAlchemy models and data access
│   ├── alembic/             # Database migrations
│   └── tests/               # pytest, including the security regression suite
├── testing/
│   └── permission-matrix.json  # RBAC matrix shared by backend and frontend tests
└── frontend/
    └── src/app/
        ├── core/
        │   ├── auth/        # Permission helper (client-side copy of the matrix)
        │   ├── services/    # ThreatStore, Threats, Auth, DemoMode, DemoSimulator, Settings
        │   ├── interceptors/# API base URL, 401 redirect, demo mode
        │   └── guards/      # Auth guard (canActivate)
        ├── shared/
        │   └── models/      # TypeScript interfaces
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

- Node.js 20.19+ (required by Angular 21)
- Python 3.9+
- Angular CLI (`npm install -g @angular/cli`)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env. For local development set at least:
#   JWT_SECRET=<a long random string>   (required, startup fails without it)
#   ENV=development                     (allows the session cookie over plain HTTP)
# Leave DEMO_MODE unset (demo mode is ON by default), or set DEMO_MODE=false
# together with ADMIN_PASSWORD (12-72 bytes) to run with writes enabled.

python3 -m uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`. API docs at `http://localhost:8000/docs`.
Without `DATABASE_URL` everything is kept in memory; with it, migrations run on startup.

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
| `admin` | `admin-demo` | admin |
| `alice` | `alice-demo` | analyst |
| `bob` | `bob-demo` | manager |

They are **never created when `DEMO_MODE=false`**. Outside demo mode the only seeded account is `admin`,
with the password from `ADMIN_PASSWORD`.

### Tests

```bash
cd backend && python -m pytest          # all backend tests
cd frontend && npm test -- --watch=false # all frontend tests (Vitest)
```

---

## API Endpoints

All endpoints require a session except those marked *public*. Role requirements are enforced by the server.

| Method | Path | Description | Who |
|--------|------|-------------|-----|
| POST | `/auth/login` | Log in, sets the session cookie (rate-limited) | public |
| POST | `/auth/logout` | Clear the session cookie | public |
| GET | `/auth/me` | Current user: username, display name, role | any user |
| GET | `/auth/ws-ticket` | Short-lived (5 min) ticket for the WebSocket | any user |
| WS | `/ws/threats?ticket=…` | Live threat event stream | valid ticket |
| GET | `/api/config` | `{demo_mode}` | public |
| GET | `/api/users` | Active users (no password hashes) | any user |
| GET | `/api/users/directory` | Every name ever used, incl. deleted users (for history) | any user |
| POST | `/api/users` | Create a user | admin |
| PATCH | `/api/users/{username}` | Change role and/or reset password (signs the user out) | admin |
| DELETE | `/api/users/{username}` | Delete a user (soft delete; not yourself, not the last admin) | admin |
| GET | `/api/stats` | Aggregated chart data | any user |
| GET | `/api/incidents` | Incident list | any user |
| PATCH | `/api/incidents/{id}` | Change status / assignee | see matrix |
| POST | `/api/incidents/{id}/notes` | Add a note | assignee or admin |
| PATCH | `/api/incidents/{id}/tasks` | Update completed response tasks | assignee or admin |
| POST | `/api/incidents/from-ip` | Open a case for an IP (assigned to the creator) | any user |
| GET | `/api/alerts`, `/api/alerts/summary` | Alerts and metrics | any user |
| PATCH | `/api/alerts/{id}` | Acknowledge / dismiss | any user |
| POST | `/api/alerts/{id}/case` | Open a case from an alert (assigned to the creator) | any user |
| GET | `/api/rules` | Detection rules | any user |
| POST, PATCH, DELETE | `/api/rules`, `/api/rules/{id}` | Create / edit / toggle / delete rules | admin |
| GET | `/api/behavioral/settings` | Behavioral detection settings | any user |
| PATCH | `/api/behavioral/settings` | Change behavioral detection settings | admin |
| GET | `/api/hunt`, `/api/hunts` | Run a hunt / list saved hunts | any user |
| POST, DELETE | `/api/hunts`, `/api/hunts/{id}` | Save / delete a hunt | any user |
| GET | `/api/ip/{ip}/history`, `/geo`, `/related`, `/case`, `/block` | IP intelligence and status | any user |
| GET | `/api/ip/{ip}/ai-summary` | AI-generated threat summary | any user |
| POST, DELETE | `/api/ip/{ip}/block` | Block / unblock an IP | any user |
| POST | `/api/command` | Command console | any user |
| GET | `/health` | Health check | public |

---

## Architecture

```
Browser
  └── Angular 21 (port 4200)
        ├── WebSocket → /ws/threats?ticket=…   (live events; ticket from /auth/ws-ticket)
        └── HTTP      → /api/*, /auth/*        (session in an HttpOnly cookie)

FastAPI (port 8000)
  ├── Demo-mode middleware  → rejects every write in demo mode (before any route runs)
  ├── Event generator       → ONE shared stream, fanned out to every WebSocket client
  ├── /auth/*               → login (bcrypt, rate limits), session, WebSocket tickets
  ├── /api/*                → routers → authz.py (permissions) → store / db_ops
  └── Optional database     → SQLAlchemy + Alembic (in-memory without DATABASE_URL)
```

The frontend uses a central `ThreatStoreService` (Angular signals) as the single source of truth for HTTP calls and cached state. WebSocket events are pushed into the store, and components react to signal changes. The current user (from `/auth/me`) lives in `AuthService`; the UI hides or disables actions the user is not allowed to take, using the same permission rules as the server.

---

## Security

The server is the security boundary. Everything the frontend does with permissions is UX only.

### Sessions and tokens

- **Session:** a JWT in the `sf_session` cookie — `HttpOnly`, `SameSite=Lax`, `Secure` unless `ENV=development`, 8 hours.
  Claims: `sub` (username), `role`, `sk` (the user's session key), `typ: "session"`, `exp`. Never stored in `localStorage`.
- **WebSocket ticket:** a separate 5-minute JWT with `typ: "ws"`, fetched from `/auth/ws-ticket`.
- Every decode site accepts only `HS256` and only its own `typ`, so a ticket cannot be used as a session and vice versa.
  `alg: none`, forged signatures, expired tokens, and tampered claims (e.g. `role` changed to `admin`) are rejected.
- Every request also checks the token against the **current** user record: the user must still exist, have
  the role in the token, and still have the session key in the token. So deleting a user, changing their role or
  resetting their password takes effect **immediately**, on every open session.
- The server refuses to start without `JWT_SECRET`, and with `DEMO_MODE=false` without an `ADMIN_PASSWORD` of 12-72 bytes.

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
| Block / unblock IPs, command console, saved hunts | ✓ | ✓ | ✓ |
| Detection rules (create / edit / toggle / delete) | ✗ | ✗ | ✓ |
| Behavioral detection settings | ✗ | ✗ | ✓ |
| Reset a user's password | ✗ | analysts only | ✓ |
| Create users, change roles (analyst ↔ manager), delete users (never the admin) | ✗ | ✗ | ✓ |

"Own" means `incident.assigned_to` is the caller. `assigned_to` must be an existing user (`422` otherwise).
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
- **There is exactly one admin.** The admin account cannot be deleted, and the admin role can never be granted to
  another user or removed from the admin, not even by the admin (`403`). New users are created as analysts or
  managers. At startup the server refuses to run if the database holds more than one active admin.
- **Deleting is a soft delete.** The user can no longer log in or be assigned, disappears from the user list and
  the assignee options, and their open incidents become unassigned. History (closed incidents, notes) keeps their
  name, and the username can never be reused, so old records never point at a different person.

### Demo mode

- **On unless `DEMO_MODE=false`** (fails closed). A middleware rejects every non-GET request with
  `403 {"detail": "Read-only demo"}`, except login and logout. It runs before any route or permission check.
- In the browser, common analyst actions are simulated locally (nothing is saved) so the demo stays interactive.
  The simulation applies the same permission rules, so it never "succeeds" at something the real server would deny.
- The public demo accounts exist only in demo mode, and are exempt from the per-account login lockout
  (their passwords are public; a lockout would only let anyone lock visitors out).

### Rate limits

| Limit | Scope |
|---|---|
| Login: 5/minute | per client IP |
| Login failures: 10/minute, 100/hour | per account, across all IPs |
| New cases: 5/minute, 30/hour | per user |
| IP intelligence, block/unblock, console, stats | per client IP (10-50/minute depending on the route) |

- **Client IP** is the rightmost `X-Forwarded-For` entry added by the trusted proxies (`TRUSTED_PROXY_HOPS`,
  default 1), falling back to the socket address. Leftmost entries are client-controlled and never used, so a
  spoofed header cannot rotate the key. Do not run uvicorn with `--forwarded-allow-ips='*'`.
- Every per-key limit has its own namespace, so counters can never be shared between limits.
- Counters are **in memory, per process**: they are only correct with a single uvicorn worker.

### Input validation and SSRF

- IP addresses from paths, bodies and console commands must be valid public addresses: private, loopback,
  link-local (e.g. `169.254.169.254`), reserved and multicast ranges, and obfuscated forms, are rejected (`422`).
- Incident status, assignees, notes (non-empty string, max 2000 characters) and completed tasks (unique indexes
  within the incident's playbook) are validated (`422`, never `500`).
- The blocklist is capped at 1000 entries.

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

- Set `JWT_SECRET` (long and random), and either leave demo mode on or set `DEMO_MODE=false` with `ADMIN_PASSWORD`.
- Run a **single** uvicorn worker (rate-limit counters are per process).
- **Verify `TRUSTED_PROXY_HOPS`** on the host: temporarily log only the **number** of `X-Forwarded-For` entries
  (never the IPs) for one real request, set the variable to the number of proxies that append to the header, then
  remove the log.
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
