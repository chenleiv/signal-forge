---
description: Smart release validation workflow
argument-hint: "[optional description]"
---

# Ship Workflow

Validate current changes before commit/release.

Goal:
Run only required reviewers.

---

# Input

Context:

$ARGUMENTS

Optional.

---

# Detect Changes

Run:

git status
git diff --staged

If no staged changes:

git diff

---

# Analyze

Run:

context-analyzer

Determine:

- changed areas
- risk level
- required agents

---

# Agent Routing

Run only relevant agents.

Frontend changes:
→ frontend-architect

Backend changes:
→ backend-architect

Database changes:
→ database-reviewer

Realtime/WebSocket changes:
→ realtime-engineer

Performance sensitive changes:
→ performance-engineer

Dependency changes:
→ dependency-auditor

Security sensitive changes:
→ security-auditor

SOC workflow changes:
→ soc-analyst

Always run:
→ quality-gatekeeper

---

# Rules

Do not run unnecessary agents.

Do not modify code.

Validate only.

---

# Block Release

BLOCK when:

- build fails
- tests fail
- type errors exist
- high security risk exists

---

# Output

Max 250 tokens.

Return:


SHIP STATUS:
READY / BLOCKED


CHANGE:
-


REVIEWS:

Frontend:
PASS / ISSUES / SKIPPED

Backend:
PASS / ISSUES / SKIPPED

Database:
PASS / ISSUES / SKIPPED

Realtime:
PASS / ISSUES / SKIPPED

Performance:
PASS / ISSUES / SKIPPED

Dependencies:
PASS / ISSUES / SKIPPED

Security:
PASS / ISSUES / SKIPPED

SOC:
PASS / ISSUES / SKIPPED

Quality:
PASS / FAIL


AGENTS RUN:
-


BLOCKERS:
-


NEXT:
-