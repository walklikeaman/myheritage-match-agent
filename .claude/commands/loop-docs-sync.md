---
description: Sync stale wiki/docs to match code. Trigger: after any code or config change.
---

Start the 'docs-sync' loop. Goal: wiki pages match the current code. Max iterations: 3.
Between iterations: `grep -rn "TODO\|FIXME\|TBD\|not yet written\|Phase 2\|Phase 3" wiki/`.
Exit when: no unresolved TBDs that contradict actual code state.

**Step 1**: Read `git diff --name-only HEAD~1` — which files changed?
**Step 2**: For each changed Python file, check if the matching wiki concept/entity page references it accurately (module name, behavior, status).
**Step 3**: Update stale wiki pages. Pay special attention to:
  - `wiki/concepts/agent-architecture.md` module status table
  - `wiki/concepts/selectors.md` after any recon run
  - `wiki/index.md` phase status section
**Step 4**: Self-pace — re-run the grep check, continue only if not met.

**Guardrail rules**:
- Don't modify the check to force a pass.
- If a wiki page accurately documents that something is unimplemented, leave the TBD — that's correct.
- Only flag TBDs where the code has moved ahead of the wiki.
