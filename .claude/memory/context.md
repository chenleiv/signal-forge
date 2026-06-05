# SignalForge Context

Compact project context loaded by all agents.

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

Angular 19
TypeScript
RxJS
Signals
SCSS


Backend:

FastAPI
Python
JWT HttpOnly authentication

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

Use:

router
↓
service
↓
model/schema


Routers:

HTTP only.


Services:

Business logic.


Avoid:

- business logic in routes
- leaking internal errors

---

## Security Rules

Authentication:

JWT only inside HttpOnly cookies.


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