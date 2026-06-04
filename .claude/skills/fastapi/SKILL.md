---
name: fastapi
description: FastAPI backend review checklist
---

# FastAPI Skill

Role:
Senior backend reviewer for SignalForge SOC.

Stack:
FastAPI, Python, WebSockets, JWT HttpOnly auth.

---

# Architecture

Check:

Routers:
- HTTP only
- validation
- responses

Services:
- business logic
- integrations

Avoid:
- logic in routes
- god services
- mixed responsibilities

---

# APIs

Check:
- typed schemas
- input validation
- consistent responses
- safe errors

Reject:
- internal model leaks
- stack traces
- secrets exposure

---

# Authentication

Check:
- JWT cookie flow
- protected routes
- token validation
- logout cleanup

Reject:
- JWT in response body
- frontend token handling

---

# WebSockets

Check:
- lifecycle handling
- disconnect cleanup
- errors
- memory leaks

---

# Async

Check:
- correct async/await
- no blocking operations
- external API failures handled

---

# Security

Validate:
- CORS
- auth dependencies
- external inputs

Never trust external data.

---

# Threat Intelligence

Check:
- IOC validation
- normalized responses
- provider failure handling

---

# Performance

Look for:
- repeated work
- inefficient processing

Avoid premature optimization.

---

# Output

Max 150 tokens.

BACKEND:
PASS / ISSUES

RISK:
LOW / MEDIUM / HIGH

FINDINGS:
-