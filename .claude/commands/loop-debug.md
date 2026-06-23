---
description: Reflexion-based debug loop. Trigger: when a bug resisted its first fix.
argument-hint: "<bug description>"
---

Start the 'debug' loop. Goal: identify and fix the root cause. Max iterations: 5.
Between iterations: re-run the failing command/test and read the output.
Exit when: the failure no longer reproduces.

**Step 1**: Write an entry in `.loops/reflexion.md` with:
  ```
  ## [YYYY-MM-DD] Bug: <description>
  **Tried**: <what was tried>
  **Failed because**: <root cause hypothesis>
  **Next hypothesis**: <different approach>
  ```
**Step 2**: Try a DIFFERENT fix than last time. Never retry the same approach.
**Step 3**: For Playwright failures — take a screenshot at the failure point (`page.screenshot(path="debug_<timestamp>.png")`). Read it before guessing what broke.
**Step 4**: For selector failures — check `wiki/concepts/selectors.md` confidence level. If `confidence: low`, run `recon.py` first.
**Step 5**: Self-pace — re-run, update reflexion log, continue only if bug persists.

**Guardrail rules**:
- Never delete reflexion entries — the history of failed attempts IS the value.
- If blocked after 5 iterations, write "BLOCKED: <reason>" in reflexion and report to Nikita.
- Don't stub or bypass the failure — find the root cause.
