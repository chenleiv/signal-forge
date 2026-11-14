# SignalForge Context

Compact project context loaded by all agents.

---

## Paths

```
frontend/src/app/core/      Auth permissions, guards, interceptors, services, utils
frontend/src/app/features/  Feature pages
frontend/src/app/layout/    App shell
frontend/src/app/shared/    Shared models and UI
backend/main.py             App setup, startup, demo-mode middleware, WebSocket stream
backend/routers/            HTTP routes
backend/authz.py            Authorization rules (single source for the server)
backend/repositories.py     Storage interface: database or in-memory
backend/db_ops.py           SQLAlchemy data access
backend/models.py           SQLAlchemy models
backend/store.py            In-memory state, token verification, input and IP checks
backend/simulation.py       Threat feed and event generation
backend/users.py            Users, password hashing, seeding, session checks
backend/user_admin.py       User management operations
backend/sessions.py         Logout revocation
backend/rate_limit.py       Per-IP and per-key rate limits
backend/schemas.py          Typed Pydantic request bodies: shape and size checks, 422 before a route runs
backend/security_headers.py Security headers middleware: SPA and API CSP, HSTS over HTTPS, no-store on API
backend/request_limits.py   Request body size limit middleware: 413 over 64 KB, chunked bodies included
backend/database.py         Async SQLAlchemy engine and session from DATABASE_URL, None without it
backend/constants.py        Simulation data, MITRE map, response playbooks, behavioral defaults and limits
backend/alembic/            Database migrations
backend/tests/              pytest suites
testing/permission-matrix.json  RBAC cases shared by backend and frontend tests
.claude/memory/             Project context
.claude/skills/             Review skills
```

---

## Product

SignalForge is a SOC threat monitoring platform.

Purpose:

Help security analysts detect, understand and investigate threats.

Core domains:

- Alerts
- Threat Intelligence
- Investigations
- Dashboards
- Realtime monitoring

---

## Stack

Frontend:

Angular 21
TypeScript
RxJS
Signals
SCSS


Backend:

FastAPI
Python 3.13
JWT HttpOnly authentication
SQLAlchemy (async) and Alembic with DATABASE_URL, in-memory without it

---

## Frontend Rules

Use:

- standalone components
- feature based structure
- signals for UI state
- RxJS for async streams
- services for business/API logic


Avoid:

- large components
- API calls inside components
- duplicated state
- nested subscriptions

---

## Backend Rules

Request flow:

router
↓
authz.py
↓
repositories.py
↓
db_ops.py / models.py


Routers:

HTTP handling and request validation. Never branch on the storage type.


authz.py:

Every permission decision. The frontend mirrors it in core/auth/permissions.ts.
Change both together and keep testing/permission-matrix.json in step.


repositories.py:

Incidents, rules and behavioral settings, with a database and an in-memory
implementation that must behave the same.


Exceptions to this flow:

- users: routers/users.py -> authz.py -> user_admin.py
- alerts, hunting and IP routes use the in-memory state in store.py directly


Startup:

Migrations run on startup when DATABASE_URL is set. A failed migration stops
the server. Startup must never delete stored data.


Demo mode:

On unless DEMO_MODE=false. Middleware in main.py rejects every write except
login and logout. Frontend actions are simulated in the browser.


Avoid:

- business logic in routes
- leaking internal errors

---

## Security Rules

Authentication:

Session JWT only inside HttpOnly cookies. The one JWT outside a cookie is the
short-lived WebSocket ticket from /auth/ws-ticket.


Never:

- localStorage tokens
- exposed secrets
- trusting frontend validation


Always check:

- auth
- authorization
- input validation
- external threat data

---

## SOC Product Rules

Alerts need:

- severity reasoning
- confidence
- investigation context


Threat intelligence needs:

- reputation
- source
- confidence


Dashboards should show:

useful analyst decisions

not vanity metrics.

---

## Development Rules

Before coding:

understand → plan → implement


Prefer:

- minimal changes
- existing patterns
- production quality


Avoid:

- unrelated refactors
- over engineering

---

## Engineering Priority

1. Security
2. Correctness
3. Maintainability
4. Performance

---

## TypeScript Rules

Prefer union types over string:

type AlertSeverity = 'low' | 'medium' | 'high' | 'critical'

Avoid: `any`, type assertions without reason, duplicated types.

Use strict typing. Handle nullable values safely.