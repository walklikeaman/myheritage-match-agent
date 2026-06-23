---
type: entity
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing]
confidence: high
status: active
relates_to: [myheritage, smart-matches, match-evaluation, selectors, data-extraction]
staleness_window: 90d
tags: [feature, priority-2]
---

# Entity: Record Matches

**Priority 2 — process after Smart Matches.**

## What they are
Matches to historical documents: census records, birth/death certificates, newspapers, immigration records, obituaries. These link a person in your tree to an archived historical source.

## UI flow (documented from briefing — verify with recon)
1. Land on `https://www.myheritage.com/record-matches`
2. Each card shows: record type, source name (census, newspaper, immigration, etc.), confidence
3. Click → opens **record comparison view**
4. Historical record data shown on left, tree person on right
5. Click **"Confirm"** then selectively save fields
6. Photos/documents can be attached to the person profile

## Value of record matches
Record matches have the highest genealogical integrity — they link to primary sources. Source citations from record matches are especially valuable. See [[data-extraction]] for priority order.

## Selector note
Record matches likely use the same or similar selectors to Smart Matches, but the comparison view layout will differ (left = historical record, right = tree). The recon script targets both pages — see [[selectors]].
