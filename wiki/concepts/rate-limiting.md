---
type: concept
created: 2026-06-23
updated: 2026-07-24
sources: [agent-briefing, postmortem-2026-06-26, live-note-2026-07-22, live-note-2026-07-24]
confidence: high
status: active
relates_to: [myheritage, browser-auth, agent-architecture]
staleness_window: none
tags: [anti-detection, safety, core]
---

# Concept: Rate Limiting & Anti-Detection

**These rules are non-negotiable.** Violating them risks account detection or banning.

## Delay parameters (in `config.py`)

| Parameter | Value (current) | Where used |
|-----------|-------|-----------|
| `ACTION_DELAY_MIN/MAX` | 3–9 seconds | Between individual UI actions (click, type, scroll) |
| `MATCH_DELAY_MIN/MAX` | 8–18 seconds | Between finishing one match and starting the next |
| `PERSON_DELAY_MIN/MAX` | 15–30 seconds | Between processing different people |
| `MAX_MATCHES_PER_SESSION` | 100 (efficiency optimum) / 500 (hard safety ceiling) | See note below |

> **2026-06-27 — delays were shortened (was 15–45s match / 120–300s person) and verified safe.**
> macOS was killing the headless Chromium during the long sleeps, so they were cut to
> 8–18s / 15–30s. A full day of runs (2,346 saves) showed **zero** throttling, captcha,
> or auth signals — the pacing is not what MyHeritage watches. Do not lengthen them to
> "fix" the wizard errors; that is a client-side render bug, not rate limiting. See
> [session-economics](session-economics.md).

**Why random ranges?** Fixed delays are trivially detectable as bot patterns. Random delays within human-plausible ranges look organic.

## Session management
- **Use `MAX=100` per session** — the discovery-hub list only surfaces ~100 confirmable
  matches per pass, so larger caps add error volume, not confirmed saves. The 500 cap in
  CLAUDE.md is a *safety* ceiling, not a target. Full reasoning: [session-economics](session-economics.md).
- The MAX guardrail is an **efficiency** lever, not a detection safeguard — the 2026-06-26
  postmortem found no server-side throttling at any MAX up to 300.
- After hitting the session cap, pause. The runner uses randomized inter-session gaps
  (40–150 min, off the hour) rather than back-to-back restarts.
- Spread sessions across hours; keep each session short (OK% degrades with wall-clock
  session length far more than with the per-action delay).

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

## Observed: an unusually long WAF flag (2026-07-21 evening → 2026-07-22)

Normal pattern (weeks of monitoring): a session runs 50-100 clean matches, hits a
reCAPTCHA/Incapsula challenge, backs off 2h, and the *next* session usually runs clean
again — the flag rarely survives more than one or two 2h cycles.

Starting the evening of 2026-07-21, the account instead hit the challenge on the
**very first match** of nine consecutive sessions in a row, spanning roughly 19 hours
with zero new confirms. Circuit breaker behaved correctly every time (detect → abort →
2h backoff) — this was not a code bug, just an exceptionally persistent flag. Best
guess: the live UI investigation earlier that day (see
[graph-accumulation](graph-accumulation.md) and the Vitkin relationship-lookup probing
in the session log) involved many manual page loads and one extra live match-confirm
outside the normal automated cadence, which may have pushed the WAF reputation score
higher than a normal automated session would. Not confirmed, just the most likely
explanation given the timing.

Takeaway: if a captcha flag persists for many consecutive instant-block sessions, don't
assume something broke — check whether unusual manual/live probing happened recently,
and avoid *further* live probing while a flag is active, since that's plausibly what
extends it.

## Update (2026-07-24): flag survived a fully fresh session — it's IP/account-level, not token-level

The flag from 2026-07-21 was still active ~55h later. Operator ran `--capture-session`
manually (visible browser, brand-new profile, fresh login, fresh cookies) specifically to
test whether the block was tied to the session token. It was not: the very first match
attempt on the fresh session hit the same instant reCAPTCHA challenge. This rules out
"stale/flagged cookie" as the mechanism and points to the flag living at the IP address
and/or account level on MyHeritage's side, independent of which browser session or cookie
jar makes the request. Re-capturing a session is therefore **not a working fix** for this
kind of flag — only elapsed time (and presumably ceasing all automated attempts) works.
