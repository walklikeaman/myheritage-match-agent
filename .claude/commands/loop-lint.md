---
description: Fix Python lint/typecheck errors with minimal diffs until clean. Trigger: when ruff or mypy reports errors.
---

Start the 'lint' loop. Goal: zero lint errors in all Python files. Max iterations: 5.
Between iterations: `source venv/bin/activate && ruff check . --exclude=venv`
Exit when: ruff returns exit code 0.

**Step 1**: Run `ruff check . --exclude=venv` and read the full output.
**Step 2**: Fix the first error. Make the minimal change — don't refactor surrounding code.
**Step 3**: Self-pace — re-run ruff, continue only if errors remain.

For ruff auto-fixable errors: `ruff check . --fix --exclude=venv` then review the diff before staging.

**Guardrail rules**:
- Don't suppress errors with `# noqa` unless there's a documented reason.
- Don't change code behavior while fixing lint — lint fixes are style only.
- If a ruff rule conflicts with the existing code style, note it but don't fix it without asking.
