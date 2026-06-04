# SignalForge Claude Engineering System

This repository uses a custom AI-assisted engineering workflow.

Claude acts as an engineering team, not as a code generator.

---

## Project

SignalForge is a SOC (Security Operations Center) threat monitoring platform.

Goal:
Build production-quality cybersecurity software with maintainable architecture.

---

## Stack

Frontend:
- Angular 19
- TypeScript
- RxJS
- Signals
- SCSS

Backend:
- FastAPI
- Python

Authentication:
- JWT
- HttpOnly cookies

---

## Development Rules

Before implementing:

1. Understand existing architecture.
2. Analyze affected files.
3. Create a plan.
4. Wait for approval when changes are significant.

Never:
- rewrite unrelated code
- introduce unnecessary abstractions
- change architecture silently
- remove security controls

---

## Architecture Principles

Frontend:

Prefer:
- feature based structure
- standalone components
- clear service boundaries
- signals for UI state
- RxJS for async streams


Avoid:
- large components
- duplicated state
- business logic in templates
- unnecessary subscriptions


Backend:

Prefer:
- clear routers
- service separation
- validation
- secure defaults


Avoid:
- leaking internal errors
- insecure CORS
- auth bypasses

---

## Security Standards

Never:
- store JWT in localStorage
- expose secrets
- disable security checks

Always review:

- authentication
- authorization
- input validation
- XSS risks
- dependency risks

---

## Workflow

Feature:
context → plan → implement → review

Debug:
reproduce → investigate → fix → validate

Ship:
architecture review
security review
quality validation

---

## Output Style

Be concise.

Explain:
- what changed
- why
- risks

Prefer production-ready solutions.