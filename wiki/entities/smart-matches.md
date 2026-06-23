---
type: entity
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing]
confidence: high
status: active
relates_to: [myheritage, match-evaluation, selectors, data-extraction]
staleness_window: 90d
tags: [feature, priority-1]
---

# Entity: Smart Matches

**Priority: process these first** (higher accuracy than Record Matches per Nikita).

## What they are
Links between your tree people and the same people in other users' trees. When another user has the same ancestor, MyHeritage surfaces this as a Smart Match with a confidence score.

## UI flow (documented from briefing — verify with recon)
1. Land on `https://www.myheritage.com/smart-matches`
2. Each match card shows: person name, confidence indicator, "New info" badge
3. Click match card → opens **comparison view** (your tree vs. their tree, side by side)
4. Review both sides
5. Click **"Confirm"** button
6. Page shows **extraction options** — checkboxes for what new info to save
7. Click **"Save to tree"** OR click "Back to match" to confirm without saving data

## Critical UX detail
**Confirming and saving data are TWO separate actions.**
- Confirm = registers the link between trees (always do this if ≥80% confidence)
- Save = pulls extracted data into your tree (do this selectively, field by field)

The agent must handle both flows independently. Never use "Extract all info" — always save field-by-field.

## Confidence score
Displayed as percentage on each match card. The exact selector is TBD — see [[selectors]] (update after recon).

## New info badge
Indicates how many additional data points the match would add. Check this before extracting — if `new_info_count == 0`, confirming is still valid but extraction is skipped.
