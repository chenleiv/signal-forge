# SignalForge Architecture Decisions

This document explains important technical decisions.

Agents must respect these decisions unless explicitly changed.

---

# ADR-001
## Angular 19 as Frontend Framework

Status:
Accepted

Decision:

SignalForge uses Angular 19 with modern Angular patterns.

Reasons:

- strong TypeScript integration
- scalable enterprise architecture
- built-in dependency injection
- good fit for dashboard applications

Rules:

Use:

- standalone components
- signals
- modern control flow syntax

Avoid:

- legacy NgModule patterns for new features
- outdated Angular APIs

---

# ADR-002
## Signals for UI State

Status:
Accepted

Decision:

Use Angular Signals for local synchronous state.

Examples:

- selected items
- filters
- UI preferences
- loading states


Reasons:

- predictable state updates
- simpler component logic
- better Angular integration


Do not replace all RxJS usage with signals.

Signals and RxJS solve different problems.

---

# ADR-003
## RxJS for Async Streams

Status:
Accepted

Decision:

Use RxJS for event based and asynchronous data.

Examples:

- WebSockets
- HTTP streams
- real-time alerts
- async workflows


Reasons:

SOC applications rely heavily on event streams.

RxJS provides:

- transformation
- cancellation
- composition


Avoid:

- nested subscriptions
- manual memory management
- unnecessary Subjects

---

# ADR-004
## JWT Authentication Using HttpOnly Cookies

Status:
Accepted

Decision:

Authentication tokens are stored in secure HttpOnly cookies.

Reasons:

Reduce token exposure risk from browser JavaScript.

Rules:

Never use:

- localStorage
- sessionStorage

for JWT storage.


Frontend should not manually handle tokens.

Backend owns:

- issuing cookies
- validating tokens
- clearing sessions

---

# ADR-005
## Feature Based Frontend Structure

Status:
Accepted

Decision:

Organize frontend code by feature/domain.

Example:

features/
  alerts/
  dashboard/
  threat-intelligence/


Reasons:

- easier scaling
- clearer ownership
- less coupling


Avoid:

Organizing everything only by technical type.

Bad:

components/
services/
models/

with no feature boundaries.

---

# ADR-006
## Backend Separation

Status:
Accepted

Decision:

FastAPI follows layered responsibilities.


Routers:

Handle:

- HTTP
- request validation
- responses


Services:

Handle:

- business logic
- integrations


Reasons:

Keep API code maintainable.

---

# ADR-007
## Security First Development

Status:
Accepted

Decision:

Security review is part of normal development.

Every meaningful change should consider:

- authentication
- authorization
- input validation
- data exposure
- dependency risks


Security issues have higher priority than UI improvements.

---

# ADR-008
## AI Assisted Development Workflow

Status:
Accepted

Decision:

Claude Code is used as an engineering assistant.

Claude acts as:

- architect
- reviewer
- security engineer
- debugging assistant


Claude should not:

- blindly generate code
- rewrite large areas without approval
- ignore existing architecture


Workflow:

Understand

↓

Plan

↓

Implement

↓

Review

↓

Validate