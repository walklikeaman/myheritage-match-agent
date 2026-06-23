---
type: concept
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing]
confidence: high
status: active
relates_to: [myheritage, browser-auth, agent-architecture]
staleness_window: none
tags: [anti-detection, safety, core]
---

# Concept: Rate Limiting & Anti-Detection

**These rules are non-negotiable.** Violating them risks account detection or banning.

## Delay parameters (in `config.py`)

| Parameter | Value | Where used |
|-----------|-------|-----------|
| `ACTION_DELAY_MIN/MAX` | 2–6 seconds | Between individual UI actions (click, type, scroll) |
| `MATCH_DELAY_MIN/MAX` | 15–45 seconds | Between finishing one match and starting the next |
| `MAX_MATCHES_PER_SESSION` | 200 | Hard cap — stop after this many, regardless of queue |

**Why random ranges?** Fixed delays are trivially detectable as bot patterns. Random delays within human-plausible ranges look organic.

## Session management
- Process at most 200-300 matches per day total across all sessions
- After hitting the session cap, stop. Don't restart immediately.
- Spread sessions across hours, not back-to-back
- Avoid peak hours if possible (when MyHeritage likely has higher monitoring traffic)

## Playwright settings
- `headless=False` for initial runs (harder to detect than headless)
- Persistent session state (not fresh sessions — fresh sessions are suspicious)
- Real Chrome user agent string
- Realistic viewport (1440x900)
- WebDriver property masked (`navigator.webdriver = undefined`)

## Future hardening options (if detection occurs)
- Add random mouse movements between actions
- Random scroll amounts before clicking
- Occasional "reading pause" (5-15s) on comparison pages before confirming
- Vary the time between sessions by day-of-week

## Implementation
Rate limiting delays are inserted by callers in `browser/smart_matches.py` and `browser/record_matches.py` using `random.uniform()` with the config values. Never hardcode delay values — always pull from `config.py`.
