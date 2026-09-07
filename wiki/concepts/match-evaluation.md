---
type: concept
created: 2026-06-23
updated: 2026-09-08
sources: [agent-briefing]
confidence: high
status: active
relates_to: [smart-matches, record-matches, data-extraction, selectors]
staleness_window: none
tags: [decision-logic, core]
---

# Concept: Match Evaluation

The decision engine that determines what happens to each match.

## Decision rules

```
confidence ≥ 80%  → decision = "accepted"  → proceed to confirmation + extraction
confidence < 80%  → decision = "skipped"   → log, move on (NEVER auto-reject)
new_info_count = 0 AND accepted → confirm only, skip extraction
has conflicts     → decision = "flagged"   → write to flagged_matches, manual review
error during processing → decision = "error" → log error, move on
```

**Why never auto-reject?** Nikita may want to manually review borderline matches later. Logging as "skipped" preserves that option.

## Conflict detection (auto-save is BLOCKED for these)
- Name differs from existing tree data → flag `name_mismatch`
- Date conflicts with existing data → flag `date_conflict`
- Relationship would restructure tree hierarchy → flag `relationship_restructure`

These go to `flagged_matches` table with full match JSON for human review.

**Status (2026-09-08): `name_mismatch` implemented, the other two are not.**
This design was written 2026-06-23 and stayed unimplemented for months — the
`--smart-only` flow shipped without any conflict check at all, and it took a
live incident (operator spotted a wrong confirm on screen — see wiki/log.md
2026-09-08) to surface that gap; an audit of already-confirmed matches then
found 265 pre-existing conflicts going back to 2026-07-19. The actual
implementation lives in `browser/smart_matches.py`
(`_extract_merge_conflicts()`/`_names_conflict()`), not a separate
`agent/evaluator.py`, and writes to `data/merge_conflicts.jsonl`
(`MERGE_CONFLICTS_FILE`), not a `flagged_matches` table — it works by parsing
the extract wizard's own "Выберите X в Вашем семейном дереве: Y"
disambiguation text (present when MyHeritage itself isn't sure two profiles
are the same) and comparing X vs Y, rather than comparing against a
structured record of the tree's existing data. Date-conflict and
relationship-restructure detection are still unimplemented — this page's
original design for those two remains the intended direction, not yet built.

## Extraction priority (when saving data)
1. Birth date + place (high value, often missing)
2. Death date + place
3. Photos (very hard to find manually — grab everything)
4. Additional relatives (parents, siblings — tree expansion)
5. Source citations (links to original records — critical for genealogy integrity)
6. Newspapers / obituaries (rich narrative context)

## Implementation location
`agent/evaluator.py` — not yet written (Phase 2).

## Confidence score source
The confidence score is displayed on the match card in the MyHeritage UI. Exact selector TBD pending recon — see [[selectors]].
