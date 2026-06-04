---
description: Remove implementation leftovers safely
argument-hint: "[optional cleanup scope]"
---

# Cleanup Workflow

Clean recent changes without changing behavior.

---

# Input

Scope:

$ARGUMENTS

Optional.

---

# Detect Changes

Run:

```bash
git status
git diff
```

Use changed files as cleanup scope.

---

# Context Limit

Analyze git diff only.

Clean changed files only.

Do not scan full repository.

Ignore unchanged files.

Do not search for global cleanup opportunities.

Use git diff as the cleanup boundary.

---

# Find

Look for:

- unused imports
- unused variables
- duplicate logic
- obvious dead code
- debug logs
- temporary code
- TODO leftovers

Only inside changed files.

---

# Rules

Allowed:

- remove obviously unused local code
- organize imports
- remove debug leftovers
- simplify obvious duplication

Forbidden:

- architecture changes
- behavior changes
- feature changes
- large refactors
- unrelated cleanup

Do not remove:

- unused constants
- unused utilities
- unused abstractions
- unused shared logic

without first checking if they should be connected instead.

Prefer:

- reuse existing code
- connect existing abstractions
- remove duplication

over deleting architecture.

When unsure:

Report the finding and ask before removing.

---

# Approval

Before editing return:

FILES:
-

CHANGES:
-

RISK:
LOW / MEDIUM

ARCHITECTURE IMPACT:
NONE / REVIEW REQUIRED


Wait for approval.

---

# Execute

After approval:

Apply approved cleanup only.

Keep changes minimal.

---

# Output

Max 150 tokens.

Return:

CLEANUP:
PLANNED / COMPLETE


REMOVED:
-


CHANGED:
-


NEXT:
-