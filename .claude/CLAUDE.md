# SignalForge

SOC threat monitoring platform. Claude acts as an engineering team, not a code generator.

---

## Project Context

Stack, rules, architecture:

Read `.claude/memory/context.md` before any implementation.

---

## Development Rules

Before coding:

1. Read context.md
2. Understand affected files
3. Return a plan
4. Wait for approval on significant changes

Never:
- rewrite unrelated code
- change architecture silently
- remove security controls
- introduce unnecessary abstractions

---

## Commands

/feature — plan then build
/debug — root cause first
/review — feedback on changes
/ship — validate before commit
/cleanup — remove leftovers

---

## Output

Concise. Explain: what changed, why, risks.
