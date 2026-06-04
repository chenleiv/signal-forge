---
description: Smart SignalForge feature workflow
argument-hint: "[feature description]"
---

# Feature Workflow

Build production features safely.

Never code before planning.

---

# Input

Feature:

$ARGUMENTS

If missing:
ask for requirements.

---

# Analyze

Run:

context-analyzer

Detect:

- frontend
- backend
- database
- realtime
- security
- SOC impact

---

# Route

Use only required agents:

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

SOC:
soc-analyst

Do not run unnecessary agents.

---

# Plan First

Before editing return:

PLAN:

Goal:
-

Files:
-

Changes:
-

Risks:
-

Validation:
-


Wait for approval.

---

# Implement

After approval:

Rules:

- minimal changes
- follow .claude/memory/context.md
- preserve architecture
- no unrelated refactors

---

# Finish

Recommend:

/ship

---

# Output

Max 200 tokens.

FEATURE:
PLANNED / COMPLETE

SUMMARY:
-

NEXT:
-