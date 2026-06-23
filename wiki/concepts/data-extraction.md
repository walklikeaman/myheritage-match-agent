---
type: concept
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing]
confidence: high
status: active
relates_to: [smart-matches, record-matches, match-evaluation, selectors]
staleness_window: none
tags: [extraction, data-quality, core]
---

# Concept: Data Extraction

What the agent saves vs. flags vs. ignores when enriching the tree from a confirmed match.

## Save (auto-add if not already in tree)
1. **Birth date + place** — highest value, often the key missing field
2. **Death date + place** — same priority as birth
3. **Photos** — grab everything; photos are nearly impossible to find manually
4. **Additional relatives** — parents, siblings that expand the tree
5. **Source citations** — links to original records; critical for genealogy integrity
6. **Newspapers / obituaries** — rich narrative context, low conflict risk

## Flag for manual review (NEVER auto-save)
- **Names that differ** from existing tree data — could be transcription errors or genuinely different people
- **Dates that conflict** with existing data — don't overwrite; Nikita decides which is correct
- **Relationships that would restructure** tree hierarchy — always require human judgment

Flagged items go to `flagged_matches` table with full match JSON. See [[match-evaluation]].

## Never use
- **"Extract all info" button** — bulk extraction can import incorrect data and is harder to audit. Always save field-by-field.

## Extraction flow in the UI
1. Click Confirm on match card
2. Extraction UI appears with checkboxes per field
3. Agent checks each field:
   - If field is new (not in tree) and not a conflict type → check it
   - If field conflicts with existing → uncheck + flag
4. Click "Save to tree"

## Implementation location
`browser/extractor.py` — not yet written (Phase 3). Requires recon output for checkbox selectors.
