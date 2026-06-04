---
description: Focused code review without running full release validation
argument-hint: "[optional review focus]"
---

# Review Workflow

Review recent changes and provide engineering feedback.

Do not modify files.

---

# Input

Focus:

$ARGUMENTS

Optional.

---

# Detect Changes

Run:

```bash
git status
git diff
```

Analyze:

- changed files
- affected areas
- risk level

---

# Context Limit

Analyze git diff only.

Review changed files only.

Do not scan full repository.

Do not inspect unrelated files.

Use file paths from git diff as scope.

If more context is required:

Read only direct dependencies of changed files.

---

# Route Reviewers

Run only relevant agents.

Frontend:
frontend-architect

Backend:
backend-architect

Database:
database-reviewer

Realtime:
realtime-engineer

Performance:
performance-engineer

Dependencies:
dependency-auditor

Security:
security-auditor

SOC:
soc-analyst

Skip unaffected areas.

---

# Rules

Report:

- real bugs
- architecture issues
- maintainability risks
- security concerns

Ignore:

- personal style preferences
- unrelated improvements

No code changes.

---

# Output

Max 200 tokens.

Return:

REVIEW:
CLEAN / FEEDBACK


AREAS CHECKED:
-


FINDINGS:

area:
file:
issue:
recommendation:


NEXT:
-