---
type: entity
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing]
confidence: high
status: active
relates_to: [smart-matches, record-matches, family-graph-api, browser-auth]
staleness_window: 180d
tags: [platform, target-site]
---

# Entity: MyHeritage

## What it is
Genealogy platform at `myheritage.com`. Nikita has an active **Premium/PremiumPlus** subscription (required for confirming/rejecting matches). Tree size: ~10,000 people.

## Bot detection
MyHeritage is a React SPA with active bot detection. Mitigations:
- Launch with `headless=False` initially
- Use persistent cookies / storage_state (not fresh sessions)
- Real Chrome UA string
- Random human-like delays (see [[rate-limiting]])
- Never run `playwright install` with `--with-deps` on a production account machine

## Key URLs
| Page | URL |
|------|-----|
| All Discoveries | `https://www.myheritage.com/discoveries` |
| Smart Matches | `https://www.myheritage.com/smart-matches` |
| Record Matches | `https://www.myheritage.com/record-matches` |
| Account/profile | `https://www.myheritage.com/my/account` |

## Session validation heuristic
Navigate to `/my/account`. If redirected to a URL containing `login`, `signin`, or `accounts.myheritage`, session is expired. Otherwise look for a user-menu DOM element or confirm URL stayed at `myheritage.com/my`.

## Subscription note
Premium/PremiumPlus is required to *confirm* matches. Without it the Confirm button may be greyed out or absent. Always verify subscription is active before a full run.
