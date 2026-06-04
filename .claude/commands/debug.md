---
description: Smart debugging workflow
argument-hint: "[optional bug description]"
---

# Debug Workflow

Find root cause before changing code.

Never guess fixes.

---

# Input

Issue:

$ARGUMENTS

If missing:

Inspect current repository state.

---

# Analyze

Run:

context-analyzer

Inspect:

- errors
- logs
- recent changes
- affected modules

---

# Investigation

Identify:

- expected behavior
- actual behavior
- root cause
- affected files

Use relevant agents only:

Frontend:
frontend-architect

Backend:
backend-architect

Database:
database-reviewer

Realtime:
realtime-engineer

Security:
security-auditor

Performance:
performance-engineer

---

# Before Fix

Return:

ROOT CAUSE:
-

EVIDENCE:
-

FILES:
-

FIX PLAN:
-

Wait for approval.

---

# Fix Rules

Allowed:

- minimal targeted fixes
- failing logic correction
- missing validation


Forbidden:

- rewrites
- unrelated refactors
- hiding errors
- removing safeguards

---

# Validate

After fix:

Run relevant checks.

Recommend:

/ship

---

# Output

Max 200 tokens.

DEBUG:
FOUND / FIXED

CAUSE:
-

FIX:
-

VALIDATION:
-