---
type: concept
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing]
confidence: high
status: active
relates_to: [myheritage, agent-architecture, rate-limiting]
staleness_window: 90d
tags: [auth, session, security]
---

# Concept: Browser Authentication

## Strategy: cookie-based → Playwright storage_state

**Step 1**: Export cookies from a manually-logged-in Chrome session using EditThisCookie extension (JSON format). Save to `data/myheritage_cookies.json`.

**Step 2**: `auth/browser_auth.py` normalizes the cookie format (EditThisCookie uses `expirationDate` float; Playwright needs `expires` int) and loads them into a Playwright context.

**Step 3**: After successful auth check, `context.storage_state()` is saved to `data/myheritage_session.json`. **On all subsequent runs, the session_state is used directly** — no need to re-import cookies unless the session expires.

## Auth check method
Navigate to `https://www.myheritage.com/my/account`. If the final URL contains `login`, `signin`, or `accounts.myheritage` → not authenticated. Otherwise look for user-menu DOM elements or confirm URL didn't redirect.

## Cookie expiry
MyHeritage cookies typically expire in ~30 days. When a session expires mid-run:
- Current run will fail auth check before starting
- User needs to re-export cookies from Chrome
- Re-running `python auth/browser_auth.py` will validate and save new session_state

## WebDriver masking
All contexts include:
```js
Object.defineProperty(navigator, 'webdriver', {get: () => undefined})
```
This prevents the most basic bot-detection check.

## Files
| File | Purpose |
|------|---------|
| `data/myheritage_cookies.json` | Raw cookie export (gitignored, user-provided) |
| `data/myheritage_session.json` | Playwright storage_state (gitignored, auto-generated) |
| `auth/browser_auth.py` | Session management module |

## Precedence
1. Try `SESSION_FILE` (storage_state) — most complete, includes localStorage
2. Try `COOKIES_FILE` (raw cookie export) — fallback
3. Return unauthenticated context — recon/manual mode
