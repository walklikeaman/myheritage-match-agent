---
type: concept
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing]
confidence: low
status: active
relates_to: [smart-matches, record-matches, data-extraction]
staleness_window: 30d
tags: [selectors, recon, MUST-UPDATE]
---

# Concept: MyHeritage CSS Selectors

> **⚠️ CONFIDENCE: LOW** — these are CANDIDATES, not verified selectors.
> **RULE**: Never hardcode selectors in code without running `recon.py` first.
> **RULE**: After every recon run, update this file with the real selectors and raise confidence to `high`.
> **STALENESS**: 30 days — MyHeritage updates their UI regularly.

## Status: NOT YET RECONNED

Waiting for: cookie export from Nikita → run `python recon.py` → update this file.

Recon output goes to `recon/` directory:
- `recon/smart_matches_selectors.json` — probed selector results
- `recon/smart_matches_01_initial.png` — screenshot
- `recon/smart_matches.html` — full page HTML

## Candidate selectors (unverified)

### Match card container
```
.match-card
.discovery-card
[data-testid='match-card']
[class*='MatchCard']
[class*='SmartMatch']
```

### Confidence score
```
.confidence-score
.match-score
[class*='confidence']
[class*='percentage']
[aria-label*='%']
```

### Person name on card
```
.person-name
.match-person-name
[class*='PersonName']
h2[class*='name']
```

### "New info" badge
```
.new-info-badge
[class*='new-info']
[class*='NewInfo']
.additions-count
```

### Confirm button (in comparison view)
```
button[data-testid='confirm']
button[class*='confirm']
button:has-text('Confirm')
a:has-text('Confirm')
```

### Extraction checkboxes
_Unknown — will be discovered after clicking Confirm on a test match_

### Save to tree button
_Unknown — will be discovered after clicking Confirm on a test match_

### Pagination / next page
```
button[aria-label='Next page']
.pagination-next
[data-testid='next-page']
```

## Update procedure
1. Run `python recon.py`
2. Open `recon/smart_matches_selectors.json` — look for elements with `count > 0`
3. Update the tables above with the WORKING selectors (those that returned a count)
4. Set `confidence: high` and `updated: <today>`
5. Run `/ship`
