# Wiki Log — MyHeritage Automation Agent

> Append-only. Newest entries first within each day. One entry per meaningful operation.

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
