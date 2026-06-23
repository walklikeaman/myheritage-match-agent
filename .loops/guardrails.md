# Guardrails — MyHeritage Agent

> Permanent hard constraints. Written when a failure repeated twice. Read at session startup. Treated as law.

## Guardrail: Never git add -A or git add .
**Written**: 2026-06-23 (Per universal-agent-framework)
Explicit paths only in all `git add` commands. Never use `-A` or `.` — these can accidentally include `data/` (contains session cookies), `.env`, or `logs/`.

## Guardrail: wiki/log.md entries newest-first within a day
**Written**: 2026-06-23 (Per universal-agent-framework)
Prepend new entries at the top of the file, not append at the bottom.

## Guardrail: Read wiki/index.md before any domain question
**Written**: 2026-06-23 (Per universal-agent-framework)
Don't answer questions about match flow, API limits, selectors, or extraction rules from memory — check the wiki first.

## Guardrail: Never touch selectors without reading wiki/concepts/selectors.md first
**Written**: 2026-06-23 (Per house rules in CLAUDE.md)
Selectors in MyHeritage UI change. The wiki page tracks verified vs. candidate selectors. Reading it first avoids coding against stale selector assumptions.

## Guardrail: Never auto-save conflicting genealogy data
**Written**: 2026-06-23 (Per house rules in CLAUDE.md)
Name mismatches, date conflicts, and relationship restructures always go to `flagged_matches` table for manual review. This protects tree integrity.

## Guardrail: Max 200 matches per agent session
**Written**: 2026-06-23 (Per briefing risk table)
Hard cap enforced in `config.py`. Never raise it without explicit instruction from Nikita. Account safety depends on staying under human-plausible daily volumes.
