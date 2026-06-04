---
name: testing
description: Testing and release validation checklist
---

# Testing Skill

Role:
QA reviewer validating production readiness.

---

# Review

Prioritize:

- critical flows
- security logic
- business rules
- error handling

Avoid:
- meaningless coverage
- testing implementation details

---

# Frontend

Check:

Components:
- user behavior
- state changes

Services:
- API handling
- errors

Signals:
- state updates
- computed values

RxJS:
- cleanup
- error handling

---

# Backend

Check:

- API behavior
- validation
- authentication failures
- service logic

---

# Realtime

Check WebSockets:

- lifecycle
- reconnects
- duplicates
- cleanup

---

# Security Tests

Verify:

- protected routes
- invalid auth fails
- bad input rejected

---

# Commands

Run available:

Frontend:
- lint
- typecheck
- tests
- build

Backend:
- pytest

---

# Pass Criteria

Require:

- build passes
- no type errors
- tests pass
- no regressions

---

# Output

Max 150 tokens.

QUALITY:
PASS / FAIL

CHECKS:
-

BLOCKERS:
-