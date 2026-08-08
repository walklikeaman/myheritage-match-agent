# Wiki Log — MyHeritage Automation Agent

> Append-only. Newest entries first within each day. One entry per meaningful operation.

---

## [2026-08-08] incident | Stuck inter-session sleep (Mac sleep), runner restarted

**Object**: `/tmp/mh_runner_v3.sh` (screen session `myheritage`)
**Scenario**: incident (routine hourly monitoring caught it)
**Outcome**: ✅ resolved — killed and relaunched, new session confirmed running

**What happened**: Last successful `--confirm-by-source` session finished 17:33,
sleeping the nominal 8085s (~135min, expected next run ~19:53). By the 20:55 check
no new session had started; by 21:57 (two checks later) still nothing, ~2h+ past
nominal. Runner's bash process was still alive (`ps` showed it sleeping,
uninterrupted), consistent with the known gap that only the inner `python3 main.py`
call is wrapped in `caffeinate` — the outer `sleep "$PAUSE"` between sessions is
not, so a Mac sleep/suspend during that window pauses the shell's sleep too and it
resumes later than intended once the Mac wakes. Same pattern seen earlier in this
project's history with the old `--smart-only` runner.

Killed the stuck process tree (`screen -X quit` + explicit `kill` on the orphaned
bash loop, same two-step needed before since `screen -X quit` alone doesn't always
reap the inner process) and relaunched via the same `screen -dmS myheritage bash
/tmp/mh_runner_v3.sh` command. New session confirmed started immediately
(`main.py --confirm-by-source --max-sources 8` running under `caffeinate`).

**Code changes**: none — this is an operational restart, not a code fix. Wrapping
the inter-session `sleep` in `caffeinate` too would prevent this outright; not done
yet, worth doing next time the runner script is touched.
**Updated**: `wiki/log.md`.

---

## [2026-08-05] update | Graph accumulation catch-up (backlog from smart-only/extract-confirmed tests)

**Object**: `data/family_graph.json` (`harvested_people`), `graph_updates.jsonl`
**Scenario**: regular (ran alongside the confirm-by-source runner, per Nikita's request)
**Outcome**: ✅ success — 20,340 harvested people (3,627 new), 0 VIP hits

**What happened**: `graph_updates.jsonl` had grown to 2,220 records (up from 1,900 at
the last accumulate) from the `--wait-for-captcha`/`--extract-confirmed` test
sessions run 2026-08-02/03 — those flows go through the per-match wizard and DO
capture navigator/relative data, unlike `--confirm-by-source`, which only confirms
links and captures nothing (no wizard is ever opened in that path). Ran
`graph_accumulate.py` to merge the backlog: 3,627 new harvested people, 20,340
total. `notify_vip.py` found no Ганущинер/Рассадина hits. `data/family_graph.json`
and `graph_updates.jsonl` are both gitignored (session/local data) — nothing to
commit for this entry, logged here for the record per the auto-logging rule.

**Code changes**: none.
**Updated**: `wiki/log.md`.

---

## [2026-08-05] update | Cleared remaining source trees + confirm-by-source is now the standing runner

**Object**: `/tmp/mh_runner_v3.sh` (screen session `myheritage`), `browser/source_confirm.py`
**Scenario**: regular (operator-directed rollout of the 2026-08-05 confirm-by-source mode)
**Outcome**: ✅ success — 21 source trees confirmed total today, zero captchas, runner switched over

**What happened**: Per Nikita, after the first `--confirm-by-source --max-sources 5`
batch (see earlier entry today) worked cleanly, ran a second batch with
`--max-sources 20` to sweep the remaining trees: all 16 remaining sources
confirmed successfully, 0 errors, 0 skips, ~44,160 matches reported. Combined with
the earlier 5-tree batch, that's **21 source trees, ~61,850 matches reported
confirmed today, zero reCAPTCHA/Incapsula challenges** across every run.

Before this second batch, added WAF detection + circuit breaker to
`confirm_all_for_source`/`run_bulk_source_confirm_session` (previously absent —
this endpoint had never needed it, but "previous experience" with the per-match
flow looking WAF-safe for months before it wasn't is exactly why this was added
defensively rather than assumed unnecessary going forward).

Rewrote `/tmp/mh_runner_v3.sh`: the standing loop now runs `--confirm-by-source
--max-sources 8` instead of `--smart-only`. The old headless Smart Match loop is
**dropped from unattended running** — it has instant-blocked on the first match
every time since 2026-07-21 (client-fingerprint WAF gate, see
[rate-limiting](concepts/rate-limiting.md)), so running it unattended only wasted
cycles. It and `--extract-confirmed` remain available as manual commands
(`--visible --wait-for-captcha`) for when the operator is present to solve a
captcha by hand. Pacing for the new loop: 30-150min between sessions (moderate,
not the old flow's multi-hour caution — this path has shown no WAF sensitivity so
far, but the sample is still small, so deliberately not unthrottled either), 6h
backoff if the captcha grep ever fires (it hasn't yet).

**Code changes**: `browser/source_confirm.py`, `main.py` (WAF detection — see
prior commit `8f69c2e`). Runner script itself is `/tmp`-ephemeral, not tracked —
full content documented here so it survives the next `/tmp` wipe.
**Updated**: `wiki/log.md`.

---

## [2026-08-05] update | New mode: `--confirm-by-source` — headless bulk confirm, zero captchas

**Object**: new `browser/source_confirm.py`, `main.py`
**Scenario**: regular (operator strategy decision, formalizing the 2026-08-02 manual finding)
**Outcome**: ✅ shipped and verified live — real progress, no WAF challenge, fully headless

**What happened**: Per Nikita 2026-08-05, the per-match Smart Match flow (even
`--wait-for-captcha`) kept surfacing captchas the operator had to solve by hand,
too disruptive to run unattended. Operator explicitly decided to make the
2026-08-02 "Совпадения по источнику" bulk-confirm the standing strategy for the
bulk of matches — accepting that these are almost all very distant/collateral
relatives, so skipping per-match review is an acceptable tradeoff (data is not
extracted by this action anyway, only the link is confirmed; see
`concepts/priority-list.md`/`entities/smart-matches.md` for the confirm-vs-save split).

Built `run_bulk_source_confirm_session()`: scrapes `matches-by-source`, filters to
individual family-site trees (`tree-...` hrefs) — the large aggregator collections
(Filae, Geni World, FamilySearch, GenealogieOnline catalog: `collection-...` hrefs)
do not expose the bulk "Дополнительные действия" menu and are skipped rather than
failing per-source. For each of the top `--max-sources` (default 5) by pending
count: open the dropdown, click "Подтвердить все N совпадения(-й)", confirm the
modal.

**Implementation snag**: the dropdown items are plain Angular-bound `<div>`s, not
real `<button>`/`<a>` elements. The `window.angular.element(el).triggerHandler
('click')` pattern used everywhere else in this codebase for wizard buttons did
NOT reliably work here — clicks silently no-op'd. Switched to real Playwright
locator clicks (`page.get_by_text(...).click()`, auto-waiting for actionability)
for these three steps specifically; the source-list scrape itself stays pure JS
`evaluate()` since it's just reading, not clicking.

**Live verification** (`--confirm-by-source --max-sources 1`, fully headless): PARKER
TREE Web Site, 4073 pending → confirmed via one script run → re-checked minutes
later at 2916 pending (~1150 confirmed). Zero reCAPTCHA/Incapsula challenges
across the whole run. This generalizes the 2026-08-02 finding across a THIRD
source tree and, more importantly, across our own real headless Playwright client
(not just the Claude Browser tool) — strong evidence the bulk-source-confirm
GraphQL endpoint genuinely isn't gated by the same WAF rule as the per-match
confirm/wizard flow, not just an artifact of which browser tool was used.

**Code changes**: `browser/source_confirm.py` (new), `main.py` (`--confirm-by-source`,
`--max-sources` flags).
**Updated**: `wiki/log.md`.

---

## [2026-08-03] update | New mode: `--extract-confirmed` — pull data from bulk-confirmed matches

**Object**: `browser/smart_matches.py`, `main.py`
**Scenario**: regular (new feature, operator request following the 2026-08-02 source-tree bulk-confirm discovery)
**Outcome**: ✅ shipped; mechanically verified live, still WAF-gated in headless mode

**What happened**: The 2026-08-02 "Совпадения по источнику" → "Подтвердить все N совпадения" bulk action (see that day's entries) confirms links but never extracts field data — MyHeritage's own two-step design ("Confirming and saving data are TWO separate actions", per `entities/smart-matches.md`). Operator manually found, via a live confirmed match's compare page, that it shows an **"Извлечь информацию вручную"** link instead of "Подтвердить совпадение", pointing at the same `...&action=showExtractWizard&itemId=...` URL our existing wizard-extraction code already handles.

Built `run_extract_confirmed_session()`: same per-match extraction path as `run_smart_matches_session`, but sourced from `matchStatus=8` (confirmed) instead of `32` (pending), entering each match via the manual extract link instead of a confirm click. `get_person_match_urls()` and `get_people_sorted_by_count()` gained a `match_status` parameter to support this (default unchanged at 32). `process_one_match()` gained an `extract_confirmed` flag that branches at the "already confirmed" check — previously an instant skip, now follows `_FIND_MANUAL_EXTRACT_LINK` into the same Step-3-onward wizard code, shared with the normal flow.

**Design question from Nikita** ("сколько людей нужно проитерировать" — how many people do we need to iterate): extracting one "hub" person's match pulls in their whole visible family (spouse, children) from the matched tree, so many other confirmed matches nearby in the same cluster are often already redundant by the time we'd reach them — there's no way to know the right stopping point in advance. Implemented a "dry streak" heuristic instead of a fixed count: track consecutive people who add zero new fields; stop early after `_EXTRACT_CONFIRMED_DRY_STREAK` (5) in a row, on the theory the reachable cluster is already covered. Same "loop until dry" shape used for unknown-size discovery elsewhere, applied per-person.

**Live test** (`--extract-confirmed --max 5 --scroll 4`, headless): mechanically correct — found confirmed people via `matchStatus=8`, followed the extract link on the first match, reached the wizard state check, and got the same instant reCAPTCHA block as ever. Confirms the 2026-07-29 finding generalizes: the WAF fingerprints the headless automation client itself, not the specific action (confirm vs. extract) — so `--extract-confirmed` needs the same `--visible --wait-for-captcha` combo as the normal flow, not a way around it.

**Code changes**: `browser/smart_matches.py` (`run_extract_confirmed_session`, `_FIND_MANUAL_EXTRACT_LINK`, `match_status` params), `main.py` (`--extract-confirmed` flag).
**Updated**: `wiki/log.md`. `wiki/entities/smart-matches.md` could use a follow-up note on the matchStatus=8/32 split — not yet done.

---

## [2026-08-01] update | Human-in-the-loop captcha solving: `--wait-for-captcha`

**Object**: `main.py`, `browser/smart_matches.py`
**Scenario**: regular (new feature, operator request)
**Outcome**: ✅ shipped, not yet tested live

**What happened**: Per Nikita 2026-08-01, after clarifying the difference between
"the agent bypasses/solves the captcha" (refused — off-limits regardless of
authorization) and "a human solves it, automation resumes after" (legitimate,
buildable): added a `--wait-for-captcha` flag. Only meaningful with `--visible`
(headless has no window for a human to look at). When the WAF challenge is detected
— either on the compare page before confirming, or in place of the extract wizard
after confirming — instead of immediately aborting the session, the script now pauses
and blocks on terminal input, asking the operator to solve the captcha in the visible
Chromium window and press Enter. Up to 2 solve attempts per challenge before falling
back to the existing "blocked" circuit-breaker behavior. New helper:
`_wait_for_human_captcha_solve()` in `browser/smart_matches.py`, threaded through
`process_one_match()` → `run_smart_matches_session()` → `main.py`'s `run()`.

**Important**: this must be run by the operator directly in their own terminal
(`python3 main.py --visible --wait-for-captcha --smart-only --max 100 --scroll 8
--verbose`), not launched via the agent's Bash tool — the Enter-keypress-to-continue
needs a human at the actual keyboard, same constraint as `--capture-session`.

**Why headful might succeed where headless never does**: headless=True launches
Playwright's `chrome-headless-shell` binary (a stripped build with a more
recognizable fingerprint); headless=False launches full Chromium. Combined with a
human actually present to solve any challenge, this hasn't been tested yet as of this
entry — the 2026-07-29 finding only tested full automation (headless) vs. a
completely separate ordinary-Chrome session, not this specific hybrid.

**Code changes**: `main.py`, `browser/smart_matches.py` (see commit).
**Updated**: `wiki/log.md`. Follow-up entry once the operator has actually run it.

---

## [2026-08-01] update | Resumed runner on slower cadence + new manual-triage priority list

**Object**: `mh_runner_v3.sh`, new `priority_list.py`
**Scenario**: regular (operator decision after 2026-07-29 fingerprint finding)
**Outcome**: ✅ both shipped; runner test still instant-blocked (expected)

**What happened**: Per Nikita 2026-08-01 (after declining to build any bot-detection
evasion into the automation): (1) resumed the existing runner unchanged in logic, just
with a much slower cadence — clean-exit pauses widened from ~40min-2.5h to 3-12h
(~3-6 sessions/day instead of near-continuous), and the captcha backoff lengthened
from 2h to 6h, since hammering a client-fingerprint block doesn't help and may have
contributed to how long the 2026-07-21 flag lasted. (2) Built `priority_list.py`, a
read-only script that lists pending Smart Matches people (safe — this step alone has
never triggered the WAF challenge) and cross-references names against direct-ancestor
and VIP-surname records, so manual confirmation time in a real browser goes to the
highest-value people first instead of randomly. First run found no VIP/ancestor
overlap in the top 160 (an unrelated English-nobility branch dominates by raw count) —
see [priority-list](concepts/priority-list.md) for the known limitation.

A manual test run right after relaunching the runner still hit the instant reCAPTCHA
block on the first match, consistent with the 2026-07-29 client-fingerprint finding —
slower cadence doesn't change that, it's just lower-cost to keep trying.

**Code changes**: `priority_list.py` (new), `/tmp/mh_runner_v3.sh` (ephemeral, not
tracked — cadence change documented here and in rate-limiting.md so it survives the
next `/tmp` wipe).
**Updated**: `wiki/concepts/priority-list.md` (new), `wiki/index.md`, `wiki/log.md`

---

## [2026-07-29] verify | Real Chrome manual pass succeeds, automated script still instant-blocked — reframes the flag as client-fingerprint, not account/IP reputation

**Object**: WAF flag from 2026-07-21 (now ~8 days), circuit breaker
**Scenario**: verification test — most conclusive so far
**Outcome**: ✅ hypothesis clarified (previous "IP/account-level" theory was incomplete)

**What happened**: Operator manually logged into MyHeritage in their own everyday
Chrome (not any Claude tool), opened Smart Matches, hit a captcha once, solved it
themselves, and successfully confirmed a couple of matches by hand — no further
issues on their end, just generally slow page loads. Immediately after, ran the
automated Playwright script (`--max 5`, same account, same session file, same
machine/IP): instant reCAPTCHA block on the very first match confirm, identical to
every attempt since 2026-07-21
(`logs/session_test_20260729_030822_post-manual-captcha-check.log`).

**Why this matters**: same account, same IP, same day — a genuine human in an
ordinary browser sails through, while the Playwright-driven script is blocked
immediately. That rules out a pure account/IP-level timeout (the 2026-07-24 fresh
session test used Playwright too, just headless=False, so it was never a clean
control). The block tracks the automation client's own fingerprint (headless/CDP
signals, webdriver flags, etc.), not a reputation score on the account that a human
pass could reset. This means **waiting longer, or having a human solve captchas,
will not un-block the automated script** — the script itself is what gets detected,
every time, regardless of account standing.

**Implication for next steps**: continuing the automated runner as-is will likely
keep hitting instant blocks indefinitely rather than this being a temporary flag that
clears. Real options going forward are (a) keep the script for occasional
lower-frequency attempts in case scoring is probabilistic rather than absolute, (b)
lean more on manual confirmation in a real browser (slower but reliably works), or
(c) accept that full automation may not be reliably sustainable against this WAF
without changes to the automation approach itself that would cross into deliberate
bot-detection evasion, which the operator's agent should not pursue.

**Code changes**: none.
**Updated**: `wiki/concepts/rate-limiting.md`, `wiki/log.md`

---

## [2026-07-28] verify | Manual browse via embedded Claude Browser tool did not clear the flag; test may be invalid

**Object**: WAF flag from 2026-07-21 (still active, now ~7 days)
**Scenario**: verification test
**Outcome**: ⚠️ partial — inconclusive, likely tainted test

**What happened**: Operator manually logged into MyHeritage inside the *embedded Claude
Browser tool* (`mcp__Claude_Browser__*`, a CDP-driven Chromium instance) and browsed
the Smart/Record Matches list pages themselves, reporting pages loaded very slowly
(minutes) but did eventually load — no captcha screen was reported during that manual
browsing, and no match confirm was actually clicked by the operator in that session.

Immediately after, ran a small automated test (`--max 5`) via the normal Playwright
script to check whether the flag had cleared: it did not — instant reCAPTCHA block on
the very first match confirm, identical to every prior attempt since 2026-07-21 (log:
`logs/session_test_20260728_214521_manual-recovery-check.log`).

**Important caveat**: the embedded Claude Browser tool is itself a Chromium instance
driven via an automation protocol (CDP), similar in fingerprint terms to Playwright.
It is likely not a clean "ordinary human browser" control for this test even though
the operator's own clicks drove it. A fair test of the "human solving the challenge
resets reputation" hypothesis needs the operator's actual everyday browser (Safari or
normal Chrome, opened outside any Claude tool), with the operator personally clicking
Confirm on a match and solving any captcha shown — not yet attempted.

**Code changes**: none.
**Updated**: `wiki/concepts/rate-limiting.md`, `wiki/log.md`

---

## [2026-07-25] incident | Full 28h stop of the runner — WAF flag now ~76h old

**Object**: `mh_runner_v3.sh` (screen session `myheritage`), WAF flag from 2026-07-21
**Scenario**: incident (operator decision, no code change)
**Outcome**: ✅ runner stopped cleanly

**What happened**: The captcha flag from 2026-07-21 evening had not cleared after ~76
hours of hourly 2h-backoff retries (every retry hit an instant block on the first
match, zero new confirms across dozens of sessions since 2026-07-21). Fresh-session
test on 2026-07-24 already ruled out a token-level cause. Operator asked why the
retries kept happening, then chose to stop the automation entirely for roughly a day
plus 4 hours (~28h) rather than keep probing every 2h, on the theory that continued
attempts might be extending the flag rather than helping clear it. Before the full
stop, operator also raised trying a manual human-solved captcha pass (open the site in
a normal browser, confirm a match by hand, solve the challenge if shown) as a
lower-cost alternative — worth trying alongside or before further automated attempts,
not yet executed as of this entry.

Runner was killed (`screen -X quit` orphaned the inner bash loop; killed directly by
PID). No sessions will run until manually restarted or the scheduled resume fires
around 2026-07-26 06:46 local time.

**Code changes**: none — `/tmp/mh_runner_v3.sh` is unchanged, just not running.
**Updated**: `wiki/concepts/rate-limiting.md`, `wiki/log.md`

---

## [2026-07-24] verify | Fresh session capture does NOT clear the WAF flag — it's IP/account-level

**Object**: WAF flag from 2026-07-21, still active
**Scenario**: verification test
**Outcome**: ✅ hypothesis tested and disproven; flag is not token-bound

**What happened**: The captcha flag from 2026-07-21 evening was still blocking every
session on the first match ~55 hours later. To test whether it was tied to the stored
session cookie, operator manually ran `python3 main.py --capture-session` (visible
browser, brand-new profile, fresh login). Restarted the runner on the new session --
the very first match still hit an instant reCAPTCHA block. This rules out a stale/flagged
session token as the mechanism; the flag lives at the IP and/or account level on
MyHeritage's side. Re-capturing a session is confirmed **not** a working remedy for this
kind of block -- only waiting (and not generating further flagged attempts) works.

**Code changes**: none.
**Updated**: `wiki/concepts/rate-limiting.md`, `wiki/log.md`

---

## [2026-07-22] log | Unusually long WAF flag — 9 consecutive instant-block sessions, ~19h

**Object**: Session monitoring, WAF flag duration
**Scenario**: incident (observation only, no code change)
**Outcome**: ✅ resolved by waiting; circuit breaker behaved correctly throughout

**What happened**: Starting the evening of 2026-07-21, nine consecutive runner
sessions each hit a reCAPTCHA/Incapsula challenge on the very first match, with zero
new confirms across roughly 19 hours — far longer than the normal one-or-two-cycle
flag duration seen over weeks of prior monitoring. No intervention was taken (correctly
identified as not a code issue); the circuit breaker detected and backed off cleanly
every single time. Likely cause: the prior day's live UI investigation (Vitkin
relationship lookup, several manual page loads, one extra live match-confirm outside
normal cadence) probably pushed the account's WAF reputation score higher than usual.
Documented as a reference point so a future long flag isn't mistaken for a regression.

**Code changes**: none.
**Updated**: `wiki/concepts/rate-limiting.md`, `wiki/log.md`

---

## [2026-07-19] fix | notify_vip.py false-triggered on its own "no hits" log line

**Object**: `notify_vip.py` VIP surname scan
**Scenario**: bugfix, found while re-wiring `/tmp/mh_runner_v3.sh` after a `/tmp` wipe
**Outcome**: ✅ fixed and verified; ephemeral runner script re-synced with graph-accumulation.md

**What happened**: Recreating `/tmp/mh_runner_v3.sh` from scratch after another macOS
`/tmp` wipe, I found it was missing the `graph_accumulate.py` + `notify_vip.py`
integration documented in [graph-accumulation](concepts/graph-accumulation.md) (that
feature — already shipped in `22d3e8d` earlier — never made it into the ephemeral
runner script's actual running instance because the wipe hit before I'd re-added it).
Re-added both calls, then ran `notify_vip.py` manually to process the backlog and hit
a **false** `🔴 VIP ANCESTOR ALERT — 2 hit(s)`. The "hits" were the script's own prior
"✓ No VIP ancestor hits (Ганущинер/... / Рассадина/...)" success line, which had been
appended into a session log by the runner and then re-scanned as if it were extracted
genealogy data — the message spells out the exact surnames its own regexes hunt for.
Same failure shape as the `429`/`503` runner-backoff false-positive from 2026-07-08:
a detector matching noise it produced itself. Fixed by filtering out any line
containing `"vip ancestor hit"` before applying the surname regexes. Verified: exit 0,
clean, no false alarm.

Also ran `graph_accumulate.py` on the session that was live when I stopped the runner
for probing: 10 records → 151 harvested people total (41 new). No genuine VIP hits.

**Code changes**: `notify_vip.py` (self-output filter). `/tmp/mh_runner_v3.sh`
re-synced with the graph-accumulate + notify-vip integration (ephemeral, not
repo-tracked — see graph-accumulation.md's new "ephemeral runner" note).
**Updated**: `wiki/concepts/graph-accumulation.md`, `wiki/log.md`

---

## [2026-07-18] update | Incremental local graph accumulation — no more manual GEDCOM re-export

**Object**: `data/family_graph.json` freshness
**Scenario**: feature (operator request)
**Outcome**: ✅ built and verified live end-to-end

**What happened**: Operator asked why the local graph doesn't reflect the ~9,000+ new
confirmed matches, and said manually re-exporting a fresh GEDCOM every time is too much
of a chore — asked the agent to accumulate the graph on its own instead. Recon on a live
wizard found `li.individual_navigator_item` (name + relation-to-match-person per person
in the wizard) and `.extract_record_row` (all structured fields as plain text, DOM
order) as stable, low-risk capture points. Added `_capture_graph_snapshot` /
`_append_graph_update` to `browser/smart_matches.py` — runs once per successful match,
wrapped so a capture failure can never affect the real save flow — appending to the new
`data/graph_updates.jsonl`. Built `graph_accumulate.py` to merge those into
`family_graph.json`'s new `harvested_people` key, additive-only, never touching the
GEDCOM-derived `ancestors`/`vip_hits`. Extended `notify_vip.py` to also scan
`graph_updates.jsonl`. Verified the full pipeline live against a real, previously
unconfirmed match (Torild Blot-Sven Totilsson Kol family, 3 people) — capture, merge,
and VIP scan all worked cleanly. Important caveat documented: harvested relations are
relative to the matched person, not to Nikita, so harvested VIP hits are NOT
generation-verified the way GEDCOM-based `vip_hits` are — they need manual review, per
the project's direct-line-only alert rule. See
[graph-accumulation](concepts/graph-accumulation.md) for the full design and the
generation-depth limitation.

**Code changes**: `6b9a2c8` — `browser/smart_matches.py`, `config.py`,
`graph_accumulate.py` (new), `notify_vip.py`.
**Updated**: `wiki/concepts/graph-accumulation.md` (new), `wiki/index.md`, `wiki/log.md`

---

## [2026-07-17] fix | Second undetected WAF vendor (Imperva Incapsula) causing silent 0%-yield sessions

**Object**: `_IS_BOT_CHALLENGE` in `browser/smart_matches.py`
**Scenario**: bugfix, root-cause via live recon
**Outcome**: ✅ fixed and verified live; runner stopped mid-burn, restarted after fix

**What happened**: Noticed a session at 0 OK / 84 SKIP across 7 different people — every
single match "wizard-empty" with zero successes. Stopped the runner immediately (it was
confirming matches without enriching them, at 100% failure, with no backoff since "empty"
isn't the circuit-breaker path). Probed live: an initial check against just-confirmed match
URLs showed "match no longer exists" (expected — those had already been confirmed by our own
Step 2 before the wizard failed, so revisiting them post-hoc is a dead end). Re-probed
correctly with a fresh, never-confirmed match and full diagnostics (iframe list, body length,
HTML length, Angular node count) and found a **second bot-challenge vendor**: Imperva
Incapsula (`iframe[src*="_Incapsula_Resource"]`, 0-char body, ~886-byte HTML, 0 Angular
nodes) — completely different signature from the documented Google reCAPTCHA Enterprise
challenge, so neither existing check matched it. Added the Incapsula iframe selector to
`_IS_BOT_CHALLENGE` and verified live: the same scenario (confirm → poll wizard) now returns
`status: 'blocked'` instead of `'empty'`, correctly triggering the abort + `captcha`-token
backoff. Runner restarted after the fix landed. See
[selectors](concepts/selectors.md) → "Second WAF vendor: Imperva Incapsula".

**Code changes**: `fa62484` — `browser/smart_matches.py` (`_IS_BOT_CHALLENGE` selector).
**Updated**: `wiki/concepts/selectors.md`, `wiki/log.md`

---

## [2026-07-08] fix | Runner backoff grep false-positive on `429`/`503` inside person IDs

**Object**: `/tmp/mh_runner_v3.sh` auto-runner backoff logic
**Scenario**: bugfix (operational script, not repo-tracked)
**Outcome**: ✅ fixed and runner restarted

**What happened**: A perfectly clean session (99/100 confirmed, 0 errors, no reCAPTCHA)
still triggered the runner's 2h captcha backoff. Root cause: the backoff grep
`captcha\|429\|503` matched the substring `429` inside a MyHeritage internal person ID
(`5515429`) that appeared in the log, not an actual rate-limit signal. Confirmed via
`grep -n "reCAPTCHA\|HTTP 429\|HTTP 503"` in `browser/smart_matches.py` that the codebase
never logs bare HTTP status codes — the circuit breaker only ever emits the literal token
`captcha`. Narrowed the grep to `captcha` only, killed and relaunched the runner
(new screen PIDs 98347/98349/98350) so the fake 2h wait doesn't cost throughput. This
likely explains some of the shorter-than-expected clean run lengths seen over the past
few days' monitoring (any session touching a person/match ID containing `429` or `503`
would false-trigger a 2h stall).

**Code changes**: `6f5634b` (wiki docs only — the actual fix lives in `/tmp/mh_runner_v3.sh`,
which is ephemeral and gets recreated from this session's memory whenever macOS wipes `/tmp`).
See [session-economics](concepts/session-economics.md) → "Fixed (2026-07-08)".
**Updated**: `wiki/concepts/session-economics.md`, `wiki/log.md`

---

## [2026-06-27] verify | reCAPTCHA fix confirmed live; runner restarted + self-throttling

**Object**: Production validation of the circuit-breaker fix
**Scenario**: verification
**Outcome**: ✅ fix works end-to-end; account currently WAF-flagged; runner self-throttling

**What happened**: Restarted the runner (screen `3133`) from `main` (fix 710af0f). First
session ([session_auto_20260627_014440](../../logs/)): 3 matches saved cleanly (73 / 57 /
40 fields), then match 4 hit a reCAPTCHA challenge → status `blocked` → session aborted
after 4 matches with a `captcha` token. The runner's backoff grep caught it → now in ~2h
backoff. This confirms two things: (a) the fix behaves exactly as designed in production,
and (b) the account is **actively WAF-flagged right now**. Only **1** confirmed-but-empty
match this session (the post-confirm challenge) vs ~53/100 before the fix. The runner is
now self-throttling — it retries every ~2h, grabs a handful of matches until it hits a
challenge, backs off each time, and will naturally speed up as the reCAPTCHA reputation
decays. Independent corroboration: a poll-retry probe recovered 0 of 7 failures (a render
race would recover some), matching the bot-challenge root cause.

**Code changes**: none (operational verification).
**Updated**: `wiki/log.md`

---

## [2026-06-27] fix | Root cause = reCAPTCHA WAF challenge, not a render bug; circuit breaker shipped

**Object**: "saveButton not found" / "empty wizard" extract failures
**Scenario**: live recon + root-cause fix
**Outcome**: ✅ fixed + verified (0 errors); committed to `main` (710af0f); runner stopped, safe to restart

**What happened**: Two live headless probes (reusing `data/myheritage_session.json`, run in
the gap after the 00:11 session ended) settled the root cause. The "empty wizard" failures
are **not** a render bug and **not** a stale selector — the documented `Извлечь всю информацию`
control renders fine (real wizards show 46-54 field checkboxes, body 17k-33k chars). On the
failing matches the WAF serves a **Google reCAPTCHA Enterprise challenge in place of the
wizard**: `iframe[src*="/FP/recaptcha-challenge.php"]`, body "возможно, Вы - робот … докажите,
что Вы человек", ~578 chars, no Angular, HTTP 200. That HTTP-200-with-body-evidence is exactly
why the 2026-06-26 postmortem's `grep captcha|429|503` found nothing and wrongly concluded
"not throttling." A reload does not clear it; a 25s backoff + re-nav stays blocked. Confirmed
the data-loss path the prior entry suspected: Confirm fires *before* the wizard is walled off,
so a challenged match is left **confirmed-but-unenriched** (~75% of a plateaued session).

**Action**: With operator approval (circuit-breaker, keep pacing), implemented in
[smart_matches.py](../../browser/smart_matches.py): poll for the wizard
(`_await_wizard_ready`) classifying render as control/challenge/empty; detect the challenge
(`_IS_BOT_CHALLENGE`) → status `blocked`; on first `blocked` **abort the session** and log a
`captcha` token so the runner's existing 2h backoff fires; `skip` (not `error`) for an empty
wizard or 0 fields; defensive `saveButton` poll. Base delays + MAX unchanged. Verified with a
real `--max 20` run: 2 saved, **0 errors**, 1 challenge cleanly blocked + abort (was a ~75%
error plateau). Corrected [selectors](concepts/selectors.md) (cleared SUSPECT, documented the
bot-challenge) and [session-economics](concepts/session-economics.md) (the "not throttling"
verdict was wrong). Probes deleted.

**Runner status**: the autonomous `screen` runner is **stopped** (torn down during recon).
The fix is committed directly on `main` (710af0f) and the main checkout is clean at that
commit, so restarting runs the fixed code. Restart: `screen -dmS myheritage bash
/tmp/mh_runner_v3.sh`. Caveat: the WAF was flagged during recon, so the first session after
restart will likely hit a challenge and trigger the 2h backoff — consider waiting ~1h for the
reCAPTCHA reputation to cool first.

**Code changes**: `browser/smart_matches.py`, `main.py` (commit `710af0f`)
**Updated**: `wiki/log.md`, `wiki/concepts/selectors.md`, `wiki/concepts/session-economics.md`

---

## [2026-06-27] incident | Extract bug worsened — MAX=100 ran 14% OK; runner PAUSED

**Object**: Smart-matches extract failure — escalation to a data-quality stop
**Scenario**: incident
**Outcome**: ⚠️ runner paused pending the extract-selector fix

**What happened**: The first full MAX=100 session after the postmortem (00:11) ran only
**14% OK** (14 saved / 53 errors / 33 skips of 100). MAX=100 did NOT help — the extract
bug now bites from match 2, not match 25-43, and the OK% is *worse* than the daytime
MAX=300 runs. This points to a genuine MyHeritage wizard DOM change rolling out over
calendar time, not a session-length effect.

Worse, confirmed the data-quality impact: in `process_one_match`
([smart_matches.py:156](../../browser/smart_matches.py)) the "Подтвердить совпадение"
click commits the match server-side BEFORE the extract step. So every extract error =
a match confirmed on MyHeritage with **0 fields/photos** transferred, and once confirmed
it leaves the pending queue (`matchStatus=32`) — our automation won't revisit it. At 14%
OK each session was confirming ~53 matches/100 without extracting their data (recoverable
later via the confirmed-matches view, but not by the current pending-queue pass).

**Action**: PAUSED the runner (killed screen `87432` + session) to stop creating
confirmed-but-empty matches. The extract-selector recon+fix (see [session-economics](concepts/session-economics.md))
is now the critical path, not a deferral. Resume only after the fix lands and a test
session shows OK% back near the clean baseline.

**Code changes**: none (operational + diagnosis).
**Updated**: `wiki/log.md`

---

## [2026-06-27] incident | Postmortem: "saveButton not found" is an EXTRACT bug; set MAX=100

**Object**: Smart-matches session throughput + the 747 "saveButton not found" errors
**Scenario**: incident / rule-change
**Outcome**: ✅ root cause found, mitigation shipped (MAX=100), code fix flagged for recon

**What happened**: Overnight the auto-runner escalated MAX 30 → 100 → 150 → 200 → 250 → 300
with randomized inter-session gaps. Throughput looked higher but the success rate
collapsed: MAX=100 sessions ran ~98% OK (~98 confirmed), while MAX=250-300 ran ~33% OK
with ~200 errors each. A four-lens postmortem (position-in-session, render-timing/code,
throughput-economics, safety) over 14 finished sessions found:

1. **Root cause is the EXTRACT step, not the save button.** All 751 "saveButton not found"
   errors are downstream of `_CLICK_EXTRACT_ALL` returning `clicked:None` — the wizard's
   extract control never appears in the DOM, so there is nothing to save. Counts line up
   one-to-one (saveButton=751, "No extract button"=751, Fields:0=751).
2. **Not browser aging.** Error rate is a step function (sticky "wizard-empty" plateau at
   ~75% that flips on around match 25-43), not a ramp; working saves succeed to match ~298
   in 3-hour sessions.
3. **MAX=100 is the optimum** — the discovery-hub list only yields ~100 confirmable matches
   per pass. MAX=300 bought +3 confirmed for +400 errors. Escalation was net-negative.
4. **Safety verdict: efficiency bug, not detection.** Zero throttling/captcha/auth signals;
   account stayed logged in and accepted 2,346 saves all day. The "429/403" grep hits were
   Python line numbers and timestamps. No PushNotification warranted.

Shipped now: `config.py` MAX default 30→100 (+ rationale comment); runner switched to
fixed MAX=100; new concept page `session-economics.md`; `selectors.md` flags the extract
control as SUSPECT (re-derive before editing); `rate-limiting.md` reconciled to real
delays (8-18s/15-30s, was 15-45s/120-300s) and the MAX=100 vs 500-ceiling distinction.
Deferred: the `browser/smart_matches.py` poll-and-retry fix needs a live recon to confirm
whether the extract selector is stale — flagged as a follow-up task.

**Code changes**: commit 7ad64e6.
**Updated**: `config.py`, `wiki/concepts/session-economics.md` (new), `wiki/concepts/selectors.md`, `wiki/concepts/rate-limiting.md`, `wiki/index.md`, `wiki/log.md`, `.obsidian/`

---

## [2026-06-23] update | Speed: reduce inter-match delay 30s→13s avg; add progress.py + auto-runner

**Object**: Session throughput optimization
**Scenario**: refactor + tuning
**Outcome**: ✅ success

**What happened**: After 399 matches with zero rate-limit signals, reduced `MATCH_DELAY_MIN/MAX` from 15-45s (avg 30s) to 8-18s (avg 13s). Estimated savings: ~2.3x speedup on inter-match sleep, ~1.5h per session (from 3.5h to 2.0h). Added `progress.py` for at-a-glance cumulative stats. Updated `run_sessions.sh` to print progress after each session and loop until "Found 0 people". Set up watcher (PID 25863) to auto-chain sessions when session 3 finishes. Current stats: 539/57817 confirmed (0.9%), 525h estimated remaining at new rate.

**Code changes**: this commit.
**Updated**: `config.py`, `progress.py` (new), `run_sessions.sh`

---

## [2026-06-23] update | Add photo transfer + relatives expansion to wizard flow; update selectors wiki

**Object**: Wizard automation — completeness improvement
**Scenario**: refactor
**Outcome**: ✅ success

**What happened**: Live probe (3 scripts) confirmed wizard structure on 2026-06-23. Found two missing actions:
1. **"Извлечь информацию еще об N родственниках"** — optional expansion link that adds more relatives beyond the main extraction. Now clicked after `extractAllInfoFromAllPeople()`.
2. **`uploadPhoto()` elements** — 35+ per wizard page. Each click imports one photo from matched tree. Now clicked in a loop after field extraction.
Also updated `wiki/concepts/selectors.md` from confidence=low/unverified to confidence=high with complete verified selector table covering all pages and Angular ng-click patterns. Deleted probe scripts.

**Findings on "Перенести все"**: No single "accept all matches" button exists on the matches-for-person page. "Перенести все" in MyHeritage UX = "Извлечь всю информацию" (`extractAllInfoFromAllPeople()`) on the wizard — already implemented. Slowness is structural: 273 matches for one person = 273 separate wizard sessions × 35s each ≈ 2.7h for one person.

**Code changes**: this commit — hash filled in.
**Updated**: `browser/smart_matches.py`, `wiki/concepts/selectors.md`, `wiki/log.md`

---

## [2026-06-23] update | Sessions 1+2 complete (399/400 OK); session 3 live

**Object**: Combined SM+RM processing — cumulative totals
**Scenario**: live run
**Outcome**: ✅ success

**What happened**:
- **Session 1** (03:33–06:53): 200 matches, 199 OK (108 SM + 91 RM), 6 people, 1 error. Top person: ציפורה לובנוב (SM:106 RM:107). 1 saveButton NOT_FOUND error → fixed with `saveAndNavigateTo` fallback.
- **Session 2** (09:57–13:16): 200 matches, **200 OK** (128 SM + 72 RM), 8 people, 0 errors. Top person: חיילה מלכה Kunshtadt קונשטאדט (SM:273 RM:274). With scroll=20 discovered 508 unique people vs 391 previously.
- **Session 3** started 16:12. Cumulative: 399 confirmed, 0 errors after fix.

**Known gaps** (not automated yet):
- Photo transfer — requires separate `uploadPhoto()` clicks per photo; not in current wizard flow
- Family-level "перенести всё" bulk-accept — each person's matches processed individually; family-level bulk confirm not yet researched
- `wiki/concepts/selectors.md` still marked NOT YET RECONNED — should update with live selectors

**Code changes**: 19d6e46 (saveButton fix), 466a829 (combined runner)
**Updated**: `wiki/log.md`

---

## [2026-06-23] update | Session 1 done (199/200 OK), session 2 live, auto-runner added

**Object**: Combined SM+RM processing
**Scenario**: live run
**Outcome**: ✅ success

**What happened**: Session 1 completed: 200 matches, 199 OK (108 SM + 91 RM), 6 people, 1 error (saveButton NOT_FOUND — fixed with fallback to saveAndNavigateTo). Session 2 launched with scroll=20: found 508 unique people, top person חיילה מלכה Kunshtadt קונשטאדט (SM:273 RM:274 = 547 total). Added `run_sessions.sh` bash auto-runner that chains sessions until exhaustion with 120-180s pause. Fixed saveButton fallback in `process_one_match`.

**Code changes**: 19d6e46
**Updated**: `browser/smart_matches.py`, `run_sessions.sh` (new)

---

## [2026-06-23] update | Combined SM+RM session: largest-families-first with infinite-scroll sort

**Object**: Smart Matches + Record Matches combined runner
**Scenario**: refactor + adoption
**Outcome**: ✅ success

**What happened**: Implemented `--combined` mode (now the default) in `main.py`. `get_people_sorted_by_count()` in `smart_matches.py` now uses infinite-scroll (up to N scroll rounds) to load all people, extracts match counts from "Просмотрите X совпадения(-й)" text, and sorts descending. Combined runner merges Smart + Record people lists, sorts by total count (SM+RM), then processes each person's Smart Matches first, Record Matches second. Smoke test confirmed: ציפורה לובנוב tops the list with SM:106 RM:107. First live run started, confirmed [1/24] SM match for ציפורה לובנוב (55 fields extracted).

**Code changes**: 466a829094bbea2ee2f2059257e13efed926f9f4.
**Updated**: `browser/smart_matches.py` (get_people_sorted_by_count + run_combined_session + run_smart_matches_session rewritten), `main.py` (--combined default, --smart-only, --record-only flags)

---

## [2026-06-23] update | Phase 3 live run + headless Playwright agent built

**Object**: Smart Matches (19 confirmed) + Record Matches automation
**Scenario**: adoption + implementation
**Outcome**: ✅ success

**What happened**: Completed Phase 3 live processing of Smart Matches via Chrome MCP for אסתר Kirzon (6 matches), איצ'ה-אלי לובנוב (3 matches) — total 22 matches confirmed this session (19 + 3), on top of Emma Breitenbach×4 and דבורה יענטא שיפמן×9 from prior sessions. Discovered AngularJS requires `window.angular.element(el).triggerHandler('click')` — native click/dispatchEvent don't update Angular model. Two-step wizard flow: confirm → extract-all → save (25s wait).

Switched to headless Playwright: wrote `browser/smart_matches.py` and `browser/record_matches.py`, full `main.py` CLI entry point with `--headless/--visible/--record-matches/--capture-session` flags. One-time session capture probe launched Chromium, detected auto-login, saved `data/myheritage_session.json`. Verified headless auth works (authenticated as Nikita Nakonechnyi). Record Matches recon: 5135 people / 31,722 matches, `matchType=1`, simpler flow — single "Сохранить в Вашем дереве" button saves all new facts + relatives in-page (no wizard). Initialized git repo and published to GitHub as public repo.

**Code changes**: `9398292` — initial public commit.
**Updated**: `browser/smart_matches.py` (new), `browser/record_matches.py` (new), `main.py` (new), `wiki/log.md`

---

## [2026-06-23] ingest | Initial briefing + framework bootstrap
**Object**: `Context/myheritage-agent-briefing.md` → wiki graph; Universal Agent Framework adopted.
**Scenario**: ingest + bootstrap
**Outcome**: ✅ success
**What happened**: Ingested full project briefing (Nikita + Claude Chat conversation) into wiki knowledge graph. Created source page, 4 entity pages (MyHeritage, Smart Matches, Record Matches, Family Graph API), 6 concept pages (match evaluation, browser auth, rate limiting, data extraction, agent architecture, selectors). Adopted Universal Agent Framework: CLAUDE.md, wiki structure, .loops/, .claude/commands/ (ship + 6 loops), .claude/settings.json hooks, .obsidian/ config, .github/workflows/ CI. Phase 1 code was already written in the same session: auth/browser_auth.py, recon.py, storage/db.py, config.py. Project is blocked on cookie export from Nikita before recon can run.
**Code changes**: commit — initial framework bootstrap (hash to be filled by /ship)
**Updated**: `wiki/index.md`, `wiki/overview.md`, `wiki/sources/agent-briefing.md`, `wiki/entities/*`, `wiki/concepts/*`
