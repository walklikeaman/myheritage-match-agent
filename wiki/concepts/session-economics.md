---
type: concept
created: 2026-06-27
updated: 2026-06-27
sources: [postmortem-2026-06-26]
confidence: high
status: active
relates_to: [rate-limiting, selectors, smart-matches, data-extraction]
staleness_window: 60d
tags: [throughput, tuning, postmortem, max-matches]
---

# Concept: Session economics — how big should a session be?

> **Bottom line:** `MAX=100` per session. The site only surfaces ~100 confirmable
> matches per pass, so anything above 100 adds error volume, not confirmed saves.
> Verified by a four-lens postmortem of 14 finished sessions on 2026-06-26.

> 🔴 **CORRECTION (2026-06-27, live recon).** The postmortem's central root-cause claim
> below — "client-render bug, not throttling" — is **WRONG**. Live headless probes against
> the real wizard showed the "empty wizard" / "saveButton not found" failures are a **Google
> reCAPTCHA Enterprise bot-challenge** that MyHeritage FraudProtection serves *in place of*
> the wizard (`/FP/recaptcha-challenge.php`, HTTP 200, ~578-char body). It IS throttling /
> bot-detection. The log greps found nothing because the challenge is a 200 with the evidence
> only in the DOM body, which the agent never logged. There is also a hidden cost: the
> Confirm click fires **before** the wizard is walled off, so each challenged match is left
> **confirmed-but-unenriched** and won't resurface as pending. Fix shipped 2026-06-27:
> detect the challenge, mark it `blocked`, abort the session, and emit a `captcha` token so
> the auto-runner backs off (circuit breaker). The economics table and the MAX=100 verdict
> still stand — fewer matches also means less WAF pressure. See
> [selectors](selectors.md) → "Bot-challenge interstitial". Corrections inline below.

## The finding in one table

Per MAX tier, across today's finished smart-matches sessions:

| MAX | confirmed / session | OK% | errors / session | errors per confirmed |
|-----|---------------------|-----|------------------|----------------------|
| 100 (clean, early) | ~98 | ~98% | ~2.5 | 0.03 |
| 150 | ~69 | ~46% | ~9 | 0.13 |
| 250 | ~60 | ~24% | ~165 | 2.75 |
| 300 | ~100 | ~34% | ~200 | 1.99 |

Going from MAX=100 to MAX=300 bought about **+3 confirmed** for about **+400 errors**
(~133 wasted errors per extra confirmed). The confirmed count plateaus near 100
because that is roughly how many confirmable matches the discovery-hub list yields
in one pass. Every slot past 100 becomes a failed wizard attempt.

The 30 → 100 → 150 → 200 → 250 → 300 escalation we ran overnight was net-negative.
It optimized for the wrong metric: "did we reach the cap" instead of
"confirmed-per-session at an acceptable error rate."

## What the escalation logic should optimize

Raise MAX only while **both** hold:
1. marginal confirmed-per-session is still climbing, and
2. errors-per-confirmed stays below ~0.2.

The moment confirmed flattens (it flattens at ~100) or errors-per-confirmed crosses
the floor, stop. Under that rule the optimizer never leaves 100. MAX should only be
revisited *after* the extract bug below is fixed and re-measured.

## The real bug behind the "saveButton not found" errors

747 "saveButton not found" errors on 2026-06-26 were a **downstream symptom**, not
the cause. Every single one followed the same chain:

```
Confirm click: OK
  → Extract click: {clicked: None}        # _CLICK_EXTRACT_ALL found no control
  → "No extract button found on wizard"
  → Fields: 0
  → Save click: NOT_FOUND
  → "saveButton not found"
```

Counts line up one-to-one (751 each across all logs). The save button is absent
because **the wizard never rendered at all** — the WAF returned a reCAPTCHA challenge page
(HTTP 200) in its place, so `_CLICK_EXTRACT_ALL` found no control. The selectors are fine;
see [selectors](selectors.md) → "Bot-challenge interstitial". Deeper cost: the Confirm in
step 1 already succeeded, so each of these matches is left **confirmed but never enriched**.

### It is not browser aging — it is a WAF reputation budget
The error rate is a **step function, not a ramp**. In MAX=300 sessions it sits near
0% for the first ~25-43 saves, jumps to a flat ~72-80% plateau, then holds flat to
match 300 with no further climb. Saves that *do* extract keep succeeding all the way
to match ~298 in 3-hour sessions. That is the opposite of memory/resource decay.
**Corrected reading (2026-06-27):** this is a rolling reputation/rate budget at the WAF.
Early in a session the budget is intact (clean matches); once request velocity depletes it
(~match 25-43) reCAPTCHA challenges dominate the rest, with the occasional match still let
through (the interleaved ~25%). Not a "UI/DOM trap" — a bot-detection gate.

### It is not a photo-render race
High photo counts save fine (successful saves carry up to 187 photos). The
Confirm→Extract gap is identical for failures and successes (~11.6s mean). The race
is at the **first wizard read** ([smart_matches.py:201](../../browser/smart_matches.py)),
not the save step.

## Fix shipped (2026-06-27)

In `browser/smart_matches.py`:
1. **Poll for the wizard** before reading it (`_await_wizard_ready`, ~10s) — fixes any
   Angular paint race AND classifies what rendered: `control` / `challenge` / `empty`.
2. **Detect the reCAPTCHA challenge** (`_IS_BOT_CHALLENGE`) and return status `blocked`;
   a wizard that renders no control after the poll is `skip` (`wizard-empty`), not `error`.
3. **Circuit breaker** in the session runners: on the first `blocked`, abort the session
   and log a `captcha` token so the auto-runner's existing 2h backoff fires (it greps for
   `captcha|429|503`). This stops the confirmed-but-unenriched bleed and de-escalates the flag.
4. **Defensively poll `getElementById('saveButton')`** (`_poll_save_click`, ~10s) before
   NOT_FOUND, for the rare genuine re-render lag.

Verified 2026-06-27 (`--max 20`): 2 saved, **0 errors**, 1 challenge cleanly `blocked` +
abort. Error rate fell from the ~75% plateau to ~0%. Base delays and MAX were left unchanged
(operator decision): the fix responds to the challenge rather than trying to out-pace it.

## Safety verdict — CORRECTED (2026-06-27): it IS detection

The original verdict ("no throttling, efficiency not detection") was wrong, reached by
grepping logs for `captcha|429|503` and CDN signatures — none of which appear, because the
challenge is a **reCAPTCHA Enterprise interstitial served as HTTP 200** with the only evidence
in the page body (which the agent never logged). Live recon found it at once:
`/FP/recaptcha-challenge.php` + "докажите, что Вы человек". The interleaved successes are not
proof of "no block" — they are the ~25% the WAF reputation budget still lets through; the
account stays authenticated because it is a *soft* challenge, not a hard ban. **MAX is both an
efficiency lever and a safety lever** (fewer matches = less WAF pressure), and the agent now
treats a challenge as a stop-and-back-off signal. See [rate-limiting](rate-limiting.md) and
[selectors](selectors.md).

## Fixed (2026-07-08): runner backoff grep false-positive on `429`/`503`

The auto-runner's backoff check (`grep -q "captcha\|429\|503" "$LOG"`) matched **substrings
inside MyHeritage internal IDs**, not just real signals — a person ID like `5515429` contains
the literal digits `429`. A session that finished 99/100 confirmed with zero errors and zero
reCAPTCHA challenges still tripped the 2h captcha backoff because its log happened to contain
an ID ending in 429. The codebase never actually emits bare `429`/`503` — the circuit breaker
(`browser/smart_matches.py`) only ever logs the literal token `captcha` inside `(captcha)` when
a real reCAPTCHA challenge is detected (see "Bot-challenge interstitial" in
[selectors](selectors.md)). Fixed by narrowing the grep to `captcha` only — no HTTP status
codes ever appear in this Playwright-driven log format, so the `429`/`503` checks were pure
false-positive risk with no matching real signal to protect against.
