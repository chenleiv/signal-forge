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

## Standing Rules

These apply to every task and every session.

- Never read, list, open or search any env file (`.env`, `.env.example`, any `.env*`).
- Exclude env files in every grep and git command with the pathspec `':!*.env*'`.
- With `git ls-files`, do not combine a path and the exclude. Run `git ls-files -- ':!*.env*'` and filter the output with grep.
- Run backend tests with `--ignore=tests/test_env_example.py` locally. CI covers that file.
- Never push. The owner pushes.
- No AI attribution lines in commits or PR descriptions.
- No Hebrew anywhere in the repo: code, comments, tests, commit messages and docs.
- Plan first and wait for approval before any significant change.
- Do not edit tests without the owner's explicit approval.
- Run commands in the foreground with timeouts.
- Leave no background processes.
- Delete files only by explicit name.
- Ask before running anything outside the sandbox.

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
3. State in one line whether it is safe to push, and the owner's next steps: Publish Branch, Create PR, wait for
   green checks, merge.

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
