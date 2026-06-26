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
because the wizard DOM was never populated, so there was nothing to save. See
[selectors](selectors.md) for the extract-control selectors that need re-derivation.

### It is not browser aging
The error rate is a **step function, not a ramp**. In MAX=300 sessions it sits near
0% for the first ~25-43 saves, jumps to a flat ~72-80% plateau, then holds flat to
match 300 with no further climb. Saves that *do* extract keep succeeding all the way
to match ~298 in 3-hour sessions. That is the opposite of memory/resource decay.
The page enters a sticky "wizard-empty" state and stays there. Likely a UI/DOM
trap: a changed or locale-dependent "copy all" control, an unhandled modal, or
already-extracted matches rendering a different layout.

### It is not a photo-render race
High photo counts save fine (successful saves carry up to 187 photos). The
Confirm→Extract gap is identical for failures and successes (~11.6s mean). The race
is at the **first wizard read** ([smart_matches.py:201](../../browser/smart_matches.py)),
not the save step.

## Recommended code fix (needs a recon first)

In `browser/smart_matches.py`:
1. **Poll for the extract control** before reading it (around line 201) instead of a
   single `page.evaluate(_CLICK_EXTRACT_ALL)` — bounded ~10s loop, click once ready.
2. **Classify a never-rendered wizard as `skip`, not `error`** — when `fields == 0` /
   `clicked:None`, the wizard never loaded; logging it as a save error poisons the
   metric.
3. **Defensively poll `getElementById('saveButton')`** (line 253) so a slow Angular
   re-render after a real extract gets up to ~10s before NOT_FOUND.

House rule applies: re-derive the extract/wizard selectors against live DOM and
update [selectors](selectors.md) **before** editing extract code. The sticky
`clicked:None` state suggests one of the three `_CLICK_EXTRACT_ALL` selectors may be
stale or locale-dependent — a blind poll papers over it without fixing it.

## Safety verdict: this is efficiency, not detection

No throttling. Across ~20.5k log lines plus the 2.6 MB daily log: no captcha, no real
HTTP 429/403/503 (the grep hits were Python line numbers like `:403` and millisecond
timestamps like `.429`), no Cloudflare/DataDome/PerimeterX signatures, no `net::ERR`,
never a bounce to login. The account stayed authenticated all day and the server
accepted 2,346 saves interleaved with the errors — a real block produces uniform
failure, not interleaved success. Treat MAX as an efficiency lever, **not** a
rate-limit safeguard. See [rate-limiting](rate-limiting.md).
