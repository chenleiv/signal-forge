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

Never:
- rewrite unrelated code
- change architecture silently
- remove security controls
- introduce unnecessary abstractions

---

## Standing Rules

These apply to every task and every session.

- Never read, list, open or search any env file (`.env`, `.env.example`, any `.env*`).
- Exclude env files: pathspec `':!*.env*'` in git commands, `--exclude='.env*'` in grep, `-g '!.env*'` in rg.
- With `git ls-files`, do not combine a path and the exclude. Run `git ls-files -- ':!*.env*'` and filter the output with grep.
- Run backend tests with `--ignore=tests/test_env_example.py` locally. CI covers that file.
- No AI attribution lines in commits or PR descriptions.
- No Hebrew anywhere in the repo: code, comments, tests, commit messages and docs.
- Plan first and wait for approval before any significant change.
- Do not edit existing tests without the owner's explicit approval. New tests are allowed.

---

## Finishing a task

A standing rule. At the end of every task, after the commits, do these steps without being asked:

1. Run a read-only pre-push check. Run `git status` and `git log --oneline master..HEAD`, check every commit
   message for AI attribution lines (Co-Authored-By, "Generated with", session links), and list the files changed
   against master. Flag anything unrelated to the task and any env file. Exclude env files with `':!*.env*'` and
   never open one.
2. End the final report with a ready-to-paste PR title (one line, imperative, no prefix) and description (a short
   "What" section and a short "Checks" section with the lint, test and build results). No AI attribution lines
   and no "Generated with" footer.

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
