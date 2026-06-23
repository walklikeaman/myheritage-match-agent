---
description: Strip debug code, dead branches, probe scripts, and slop before committing. Trigger: post-impl, pre-commit.
---

Start the 'de-sloppify' loop. Goal: clean working tree with no debug artifacts. Max iterations: 2.
Between iterations: `grep -rn "print(\|pdb\|breakpoint\|TODO\|FIXME\|xxx\|hack\|temp\|_probe_" --include="*.py" .`
Exit when: grep returns zero matches in non-wiki Python files.

**Step 1**: Find and delete all `_probe_*.py` scripts (these are throwaway scripts per CLAUDE.md).
**Step 2**: Find and remove stray `print()` debug statements in production Python files (auth/, browser/, agent/, storage/).
**Step 3**: Find and remove `pdb.set_trace()`, `breakpoint()`.
**Step 4**: Check for any hardcoded test values (magic strings, hardcoded IDs) that should be in config.
**Step 5**: Check screenshots from debugging (`debug_*.png`) — delete them unless they're in `recon/`.
**Step 6**: Self-pace — re-run the grep, continue only if matches remain.

**Guardrail rules**:
- Don't remove TODOs in wiki/ files — those are legitimate status markers.
- Don't remove intentional debug flags that are behind `--dry-run` or `--debug` CLI args.
- Don't touch `recon/` output — it's a legitimate artifact of the recon phase.
