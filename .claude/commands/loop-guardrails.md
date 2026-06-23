---
description: Write a new guardrail when a failure or mistake repeats for the second time.
argument-hint: "<what went wrong>"
---

Start the 'guardrails' loop. Goal: encode a hard constraint so this failure never repeats.
Exit when: the guardrail is written and `/ship`ped.

**Step 1**: Read `.loops/reflexion.md` and `.loops/guardrails.md` to check if this failure is already documented.
**Step 2**: If the exact failure already has a guardrail, strengthen the existing one (make it more specific). If new, write a new entry:
  ```markdown
  ## Guardrail: <short name>
  **Written**: <YYYY-MM-DD> (Per <source — who identified this>)
  <Plain-English rule. What to do / not to do. Specific enough to apply without ambiguity.>
  ```
**Step 3**: Stage and commit `.loops/guardrails.md` with message: `guardrail: add constraint for <short name>`.
**Step 4**: Update `CLAUDE.md` house rules section if the guardrail is broad enough to apply to all future sessions.

**Guardrail rules**:
- The rule must be checkable — "be careful" is not a guardrail; "never do X" is.
- Don't write guardrails for things that only go wrong once.
