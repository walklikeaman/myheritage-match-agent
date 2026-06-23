---
type: source
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing]
confidence: high
status: active
relates_to: [myheritage, smart-matches, record-matches, family-graph-api, match-evaluation, browser-auth, rate-limiting, data-extraction, agent-architecture]
---

# Source: MyHeritage Agent Briefing

**File**: `Context/myheritage-agent-briefing.md`
**Origin**: Conversation between Nikita and Claude Chat about automating genealogy work.

## Key takeaways

- Tree has ~10,000 people; match volume is in the **thousands** — unmanageable manually
- MyHeritage **Premium/PremiumPlus subscription** active (required for match confirmation)
- Priority: Smart Matches first (higher accuracy), then Record Matches
- **Confidence ≥ 80%** → auto-accept; below 80% → skip (log, don't reject)
- "Confirm" and "Save data" are **two separate UI steps** — agent handles both
- Family Graph API is **read-only** for matches — write ops require Playwright
- Phase 1 instruction: write `recon.py` + `auth/browser_auth.py` → run recon → document selectors → THEN build automation

## Architecture specified

Hybrid: Playwright (primary write ops) + Family Graph API (future read ops). 
Module layout: `auth/`, `browser/`, `agent/`, `storage/`, `tests/`.
Implementation order: auth → recon → storage → smart_matches (read-only) → evaluator → dry-run → clicking → extractor → record_matches → pilot.

## Risk table from briefing

| Risk | Mitigation |
|------|-----------|
| Bot detection | headless=False, real UA, persistent cookies, human delays |
| Account ban | Max 200-300 matches/day, spread across hours |
| Wrong data saved | Flag conflicts, never overwrite, always log |
| Session expiry | Validate before batch, save storage_state after auth |
| UI selector changes | All selectors in one place (`wiki/concepts/selectors.md`), screenshot on failure |
| Tree corruption | Never use "Extract all info" button — save field-by-field |
