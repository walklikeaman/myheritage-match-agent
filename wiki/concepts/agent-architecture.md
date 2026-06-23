---
type: concept
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing]
confidence: high
status: active
relates_to: [browser-auth, rate-limiting, match-evaluation, data-extraction, selectors, family-graph-api]
staleness_window: 90d
tags: [architecture, design, core]
---

# Concept: Agent Architecture

## Design philosophy
Hybrid: **Playwright for all writes**, Family Graph API for reads (future). The API cannot confirm matches or save extracted data — Playwright is the only path for those operations.

## Module map

| Module | Status | Purpose |
|--------|--------|---------|
| `config.py` | ✅ done | Thresholds, delays, URLs, paths |
| `auth/browser_auth.py` | ✅ done | Cookie loading, session management, auth validation |
| `recon.py` | ✅ done | Reconnaissance: screenshots, HTML, selector probing |
| `storage/db.py` | ✅ done | SQLite: processed_matches, flagged_matches, run_log |
| `browser/driver.py` | Phase 2 | Playwright setup with stealth config |
| `browser/smart_matches.py` | Phase 2→3 | Navigate + read → confirm + extract Smart Matches |
| `browser/record_matches.py` | Phase 4 | Same pattern, different selectors, Record Matches |
| `browser/extractor.py` | Phase 3 | Selective field-by-field data extraction |
| `agent/evaluator.py` | Phase 2 | Confidence scoring, accept/skip/flag decision |
| `agent/enricher.py` | Phase 3 | Photos, relatives, source citations |
| `main.py` | Phase 2 | Entry point: `--dry-run`, `--limit`, `--type` flags |

## Implementation order (from briefing)
1. ✅ `auth/browser_auth.py` — cookie loading, session validation
2. ✅ `recon.py` — run this, document all selectors → **BLOCKED on cookies**
3. ✅ `storage/db.py` — SQLite setup
4. `browser/smart_matches.py` — navigate + read (no clicking yet)
5. `agent/evaluator.py` — confidence scoring
6. `main.py` with `--dry-run` — full dry-run pipeline
7. Add clicking + confirmation to `smart_matches.py`
8. `browser/extractor.py` — selective data extraction
9. `browser/record_matches.py` — Record Match flow
10. Logging, error handling, resume logic
11. 10-match pilot → review → iterate → 50-match → full run

## Resume capability
On startup, `main.py` queries `processed_matches` for all known match IDs, then skips any match that's already been processed. This makes the agent safely restartable after any interruption.

## Dry run flag
`--dry-run`: navigate and read matches, log decisions, take screenshots — but never click Confirm or Save. Essential for validating selector logic before any real changes.

## CLI flags (planned for main.py)
```
--dry-run          Navigate + log without clicking
--limit N          Process at most N matches
--type smart|record|both  Which match type to process
--resume           Explicitly force resume mode (default behavior anyway)
```
