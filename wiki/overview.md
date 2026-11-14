---
type: concept
created: 2026-06-23
updated: 2026-11-13
sources: [agent-briefing, project-memory-2026-11]
status: active
---

# Overview — MyHeritage Automation Agent

## What we're building

A Python automation agent that processes genealogy match notifications on MyHeritage so that Nikita doesn't have to click through thousands of matches manually. The agent **evaluates confidence, confirms accepted matches, and enriches the family tree** with photos, dates, relatives, and source citations pulled from each match.

This is a **data enrichment agent**, not a click-bot. The distinction matters: the agent reads extracted data and decides *what is worth saving*, rather than blindly accepting everything.

## The fundamental constraint

MyHeritage's [Family Graph API](entities/family-graph-api.md) is read-only for match operations. There is no API endpoint to confirm a match or save extracted data. All write operations require browser automation via Playwright. This forces a **hybrid architecture**:
- Family Graph API → read tree structure, match counts (future)
- Playwright → everything that requires clicking

## Состояние на 2026-11-13

- Фоновый цикл работает на Mac Mini под launchd: две сессии Smart Matches, потом одна Record Matches, до 100 совпадений за сессию → [background-runner](concepts/background-runner.md).
- С 2026-11-08 16:48 сессии упираются в hCaptcha; лечит свежий вход Никиты → [captcha-and-waf](concepts/captcha-and-waf.md).
- Конфликты не сохраняются сами, а копятся в очереди ручной проверки → [conflict-review](concepts/conflict-review.md).
- Уведомление на Mac только о новых VIP-находках прямой линии → [vip-alerts](concepts/vip-alerts.md).
- Граф семьи публикуется на NAS после каждой сессии → [nas-graph-export](concepts/nas-graph-export.md).
- Как работают агенты в проекте → [agent-framework](concepts/agent-framework.md).

## Current state (2026-06-23, historical)

Phase 1 complete: authentication scaffolding + recon script + SQLite storage + config.
**Blocked on**: cookie export from Nikita → needed to run recon and identify live CSS selectors.

## Key design decisions

1. **80% confidence threshold** — below this, match is logged as `skipped`, never auto-rejected (Nikita may want to review manually later)
2. **Smart Matches first** — higher accuracy than Record Matches
3. **Confirm ≠ Save** — these are two separate UI actions; the agent handles both flows
4. **Never overwrite conflicting data** — name mismatches, date conflicts, relationship restructures all go to `flagged_matches` table for human review
5. **Resumable from interruption** — SQLite tracks every processed match ID; restart picks up where we left off

## Risk profile

The biggest risks are: (1) bot detection banning the account; (2) wrong data saved to tree. Both are mitigated by strict rate limiting, `headless=False`, and flagging-vs-saving logic. See [[rate-limiting]] and [[data-extraction]].
