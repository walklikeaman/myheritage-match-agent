# Wiki Log — MyHeritage Automation Agent

> Append-only. Newest entries first within each day. One entry per meaningful operation.

---

## [2026-09-08] update | VIP direct-ancestor hit — Мария Михайловна Колонова (Разсадина) confirmed and saved

**Object**: `data/graph_updates.jsonl`, VIP alert rule (see CLAUDE.md, `notify_vip.py`)
**Scenario**: regular (VIP surname check after routine `myheritage-smart` sessions)
**Outcome**: ✅ direct-line VIP ancestor confirmed with real field data, saved to tree

**What happened**: `notify_vip.py` flagged 5 **Разсадина** hits (old spelling of
Рассадина) for the first time in this whole project's history — every prior
check across dozens of sessions came back 0. Verified the actual data (not just
the surname string) by reading `data/graph_updates.jsonl` navigator/raw_text
directly: **Мария Михайловна Колонова (Разсадина)**, wife of Георгий Тимофеевич
Колонов, is the mother of **Юрий Георгиевич Колонов**, whose daughter is
**Марина Юрьевна Наконечная (Колонова)** — this exactly matches CLAUDE.md's VIP
description ("прабабушка Мария Рассадина, мать деда Юрия Колонова"), i.e. this
is confirmed **direct maternal-line** ancestry, not a collateral relative.

Cross-checked against the actual session logs (not just the extracted
snapshot): both matches for Раиса Васильевна Кузьмина/Скороходова (ID 5000012,
5520201) that surfaced this family were **saved successfully** — 46 fields + 21
photos, and 22 fields + 15 photos — not blocked by the merge-conflict detector,
so this data is genuinely in the tree now, not just captured raw and pending.

Per CLAUDE.md's VIP alert rule, attempted `PushNotification` — not delivered
("Mobile push not sent — Remote Control inactive"), so flagging prominently
here and in the live chat instead.

**Code changes**: none.
**Updated**: `wiki/log.md`.

---

## [2026-09-08] fix | Treat bare "?" tree-side placeholders as non-conflicts too

**Object**: `browser/smart_matches.py` (`_UNKNOWN_PLACEHOLDER_RE`)
**Scenario**: bugfix (found during routine hourly monitoring of live output)
**Outcome**: ✅ fixed and shipped

**What happened**: The 12:26-13:42 session showed an elevated conflict rate
(20/100 vs the typical 1-9 seen in prior sessions) — spot-checking the actual
`Conflicting merge suggestion` log lines found most of the spike was one
repeating false positive: source `"אבא/אמא של זונדל זוננברג"` ("father/mother of
Zundel Zonnenberg") being flagged against tree-side `"? ?"`. `"?"` is the same
kind of empty-name placeholder as `"Неизвестно"`/`"Unknown"` (already exempted
2026-09-08 earlier today), just a different UI rendering MyHeritage uses for it
— `_UNKNOWN_PLACEHOLDER_RE` didn't cover it. The other conflicts in that same
session (e.g. Hebrew `אברהם סברדלוב` vs `דוד סברדלוב` — different first names,
same surname) looked like genuine catches, so the elevated count was mostly
noise from this one gap, not a new problem with the detector itself.

**Code changes**: `browser/smart_matches.py`.
**Updated**: `wiki/log.md`.

---

## [2026-09-08] update | Resumed `myheritage-smart` runner after the conflict-detection fix

**Object**: `screen` session `myheritage-smart`
**Scenario**: regular (operator confirmed the fix is sufficient to resume)
**Outcome**: ✅ running — screen session confirmed alive

**What happened**: Per Nikita 2026-09-08, after the merge-conflict fix (previous
log entry) and the delivered audit of 265 historical conflicts, relaunched
`/tmp/mh_runner_smart_v1.sh` via `SCREENDIR=/tmp/screendir-mh screen -dmS
myheritage-smart bash /tmp/mh_runner_smart_v1.sh`. Confirmed alive via
`screen -ls` and `ps aux`. No code changes since the fix commit — this is the
same script whose canonical content is pasted in the previous log entry.

**Code changes**: none.
**Updated**: `wiki/log.md`.

---

## [2026-09-08] fix | Stop auto-confirming conflicting merge suggestions in the extract wizard

**Object**: `browser/smart_matches.py` (`process_one_match`), `config.py`
**Scenario**: incident (operator caught a wrong confirm live on screen)
**Outcome**: ✅ fixed and shipped — audit of existing data delivered to operator

**What happened**: Nikita watched the `myheritage-smart` runner (launched earlier
today) confirm a match for **Владимир Иванович Корнієнко (ID 5500110)** and
recognized the source profile as a different real person. Investigated using
already-captured `data/graph_updates.jsonl` (no live site check needed) and found
the mechanism: the extract wizard's own "Выберите X в Вашем семейном дереве: Y"
disambiguation dialog — used when it isn't sure a source person matches an
existing tree person — had suggested merging source **Анна Корниенко (Стоцкая)**
with the tree's existing **Ганна Герасімовна Корнієнко (Зозуля)**, and separately
source **Иван Корниенко** with tree's **Григорий Корниенко** — different people,
different maiden names, different birth/death years. `process_one_match()`'s
"extract all" click accepted whatever the wizard pre-selected by default, with
zero verification. This directly violated CLAUDE.md's "never auto-save
conflicting genealogy data — flag for manual review" rule, which had never
actually been implemented for this flow.

**Fix**: added `_extract_merge_conflicts()` / `_names_conflict()` to
`browser/smart_matches.py` — parses the wizard's "Выберите X в Вашем семейном
дереве:\nY" pattern out of the already-captured raw extract text, and flags a
conflict when X and Y clearly aren't the same person (different maiden name in
parentheses, or different first name), while excluding the two known-benign
cases: "Y = Добавить как новую/нового ..." (no existing candidate, adding new —
correct default) and "Y = Неизвестно/Unknown ..." (enriching a bare placeholder,
not overwriting a real conflicting record). Normalizes Ukrainian/Russian letter
variants (і/и, є/е, ї/и, **ё/е** — this one caused a real false positive on "Шлём
Гланц" vs "Шлем Гланц" during testing) before comparing. Deliberately biased
toward over-flagging: a false positive costs the operator a couple minutes of
review, a false negative silently corrupts the tree.

Wired into `process_one_match()` right after the existing graph-snapshot capture
(Step 3b2) and before the photo-transfer/Save steps: if any conflict is found,
the match is **not saved** (Confirm already happened server-side by this point
and can't be undone from here, but Save — the step that actually writes the
wrong family into the tree — is skipped), a `status="conflict"` result is
returned instead of `"ok"`, and the conflict is appended to the new
`data/merge_conflicts.jsonl` (`MERGE_CONFLICTS_FILE` in `config.py`) for a
durable, discoverable trail.

**Audit of already-confirmed data**: ran the same detector across all of
`data/graph_updates.jsonl` (validated first against 1754 real "Выберите..."
dialogs — 282 flagged before the ё/Неизвестно fixes, 265 after, with spot-checked
samples looking like genuine conflicts, e.g. distinct English royal-lineage
people and distinct Finnish `Kähkönen`/`Kuokkanen` families being merged).
**5 people / 8 confirmed matches** from the two most recent sessions (2026-09-07
manual run, 2026-09-08 automated attempt) are affected, plus **72 people / 257
matches** historically (2026-07-19/20/21, 2026-08-02/03) — the July batch mostly
distant European nobility lines, which are especially conflation-prone. Delivered
the full breakdown to the operator as `data/conflict_audit_2026-09-08.md`
(gitignored — local data, not committed) for manual review/correction on the
site; the recent 8 are called out as priority.

**Also fixed while in the runner script**: `mh_runner_smart_v1.sh`'s captcha
detection grep (`captcha\|reCAPTCHA\|Incapsula`) was matching the literal
`--wait-for-captcha` parameter name inside an unrelated crash traceback (a
`Page.evaluate: Execution context was destroyed` navigation-race error hit
during today's automated run), sending a plain crash into the 6h captcha backoff
instead of the 300s crash backoff. Narrowed to the literal `(captcha)` tag the
code actually emits on a real WAF hit, plus `Incapsula`.

**Not yet resumed**: `myheritage-smart` runner was stopped when the bad confirm
was spotted and has not been restarted pending operator confirmation that the
fix is sufficient — see next log entry / conversation for the decision.

**Canonical `/tmp/mh_runner_smart_v1.sh` content** (the "feat" entry below never
pasted the actual script — filling that gap now, with the captcha-grep fix
included, so it can be recreated from this log alone if `/tmp` gets wiped by a
reboot):
```bash
#!/bin/bash
cd "/Users/walklikeaman/GitHub/My Heritage"
MAX_MATCHES=100

# Standing runner for --smart-only --sort-by-relationship (2026-09-08). Runs
# --visible (NOT headless) because headless instant-blocks on the WAF
# client-fingerprint gate since 2026-07-21 (see wiki/concepts/rate-limiting.md) --
# --visible does not, confirmed by a clean 100-match / 0-captcha manual run on
# 2026-09-07. Does NOT pass --wait-for-captcha since no human is present
# unattended: on a captcha hit, process_one_match() returns status="blocked" and
# run_smart_matches_session() aborts the session cleanly (see
# browser/smart_matches.py) instead of hanging on an Enter that will never come --
# this runner just backs off long and retries later, same pattern as the old
# confirm-by-source runner (wiki/log.md 2026-08-05).
rand_pause() {
    TIER=$(( RANDOM % 20 ))
    if   [ "$TIER" -lt 10 ]; then BASE=$(( 2700 + RANDOM % 1800 ))   # 45-75min
    elif [ "$TIER" -lt 17 ]; then BASE=$(( 4500 + RANDOM % 1800 ))   # 75-105min
    else                          BASE=$(( 6300 + RANDOM % 3600 ))  # 105-165min
    fi
    echo $(( BASE + RANDOM % 47 ))
}

while true; do
    LOG="logs/session_smart_$(date +%Y%m%d_%H%M%S).log"
    caffeinate -i python3 main.py --smart-only --sort-by-relationship --visible --max "$MAX_MATCHES" --scroll 8 --verbose > "$LOG" 2>&1
    EXIT=$?

    # Per CLAUDE.md: run notify_vip.py after every session. Appended to the same
    # log so the hourly monitoring check-in can surface VIP hits without a live
    # site check.
    python3 notify_vip.py >> "$LOG" 2>&1

    # Match only the literal "(captcha)" tag the code emits on a real WAF hit --
    # a bare "captcha" substring also matches the --wait-for-captcha flag name
    # inside an unrelated crash traceback (found live 2026-09-08), which wrongly
    # sent a genuine crash into the 6h captcha backoff instead of the 300s one.
    if grep -qi "(captcha)\|Incapsula" "$LOG" 2>/dev/null; then
        PAUSE=21600
        echo "[runner] captcha/WAF block detected -- sleeping ${PAUSE}s" >> "$LOG"
    elif [ "$EXIT" -ne 0 ]; then
        PAUSE=300
        echo "[runner] crash (exit $EXIT) -- sleeping ${PAUSE}s" >> "$LOG"
    else
        PAUSE=$(rand_pause)
        echo "[runner] clean exit -- sleeping ${PAUSE}s" >> "$LOG"
    fi

    # 2026-08-13 lesson (see wiki/log.md): wrap the inter-session pause in
    # caffeinate too, so macOS idle sleep can't stretch it past nominal duration.
    caffeinate -i sleep "$PAUSE"
done
```

**Code changes**: `browser/smart_matches.py`, `config.py`.
**Updated**: `wiki/log.md`.

---

## [2026-09-08] feat | Automated the close-relatives flow — new `myheritage-smart` background runner

**Object**: `/tmp/mh_runner_smart_v1.sh` (screen session `myheritage-smart`)
**Scenario**: regular (operator wants hands-off automation, not a manual command each time)
**Outcome**: ✅ launched — screen session confirmed alive, first cycle running

**What happened**: Per Nikita 2026-09-08, after the clean 100/0-captcha manual
`--sort-by-relationship` run on 2026-09-07, operator asked to stop launching it by
hand and automate it fully. Built a new standing runner analogous to the old
`--confirm-by-source` one (`/tmp/mh_runner_v3.sh`, retired 2026-09-01), but for
`--smart-only --sort-by-relationship`:

- Runs `--visible` (not headless) — headless instant-blocks on the WAF
  client-fingerprint gate since 2026-07-21 (see
  [rate-limiting](concepts/rate-limiting.md)); `--visible` does not, per the
  2026-09-07 clean run.
- Does **not** pass `--wait-for-captcha` — no human is present unattended, and
  confirmed in code (`browser/smart_matches.py:678-684`) that without it, a
  captcha hit sets `status="blocked"` and the session aborts cleanly (not a
  hang), same circuit-breaker the old runner relied on.
- On captcha/WAF signal in the log: 6h backoff. On crash: 300s backoff.
  Otherwise: same randomized 45-165min pause tiers as the old runner, wrapped in
  `caffeinate` for both the session and the pause (2026-08-13 lesson).
- Runs `python3 notify_vip.py` after every session per the CLAUDE.md rule,
  appending its output to the same session log so the hourly monitoring
  check-in can surface VIP hits without a live site check.
- `--max 100` per session (matches the validated manual run size).

Launched via `SCREENDIR=/tmp/screendir-mh screen -dmS myheritage-smart bash
/tmp/mh_runner_smart_v1.sh`. `screen -ls` confirms it alive; first session
already processing matches. Logs to `logs/session_smart_*.log` (new prefix,
distinct from the retired `session_source_*.log`).

**Caveat flagged to operator**: this pops a real (non-headless) Chromium window
periodically while the Mac is unattended — untested how it behaves if the
screen locks or sleeps despite `caffeinate -i`; will be visible in the next
sessions' exit codes if it's a problem, not silently broken.

**Code changes**: none in the repo — `/tmp/mh_runner_smart_v1.sh` is
`/tmp`-ephemeral (same resilience caveat as the old runner: wiped on reboot,
must be recreated from this log entry's canonical content if `screen -ls` for
`myheritage-smart` comes back empty).
**Updated**: `wiki/log.md`.

---

## [2026-09-07] update | First manual `--sort-by-relationship` run — 100 matches, VIP Ганущинер branch confirmed

**Object**: `--smart-only --sort-by-relationship` session (operator-run, 15:00-16:55)
**Scenario**: regular (first live run of the flow adopted 2026-09-01)
**Outcome**: ✅ success — 100/100 matches processed, session cap reached cleanly, no captcha

**What happened**: Nikita ran the manual close-relatives flow for the first time
since dropping `--confirm-by-source`:
```
python3 main.py --smart-only --sort-by-relationship --wait-for-captcha --visible --max 100 --scroll 8 --verbose
```
List load took ~68s (longer than the count-sort default, consistent with the
2026-08-28 finding that the relationship re-sort needs extra time), then processed
cleanly to the 100-match cap with only one `ERROR (0 fields)` outlier (`total: 17`,
no captcha involved) among 99 successful saves. Browser window closed on its own
once the cap was hit — expected behavior, not a crash.

`notify_vip.py` found 18 hits — all **Ганущинер**, no Рассадина. Checked
`graph_updates.jsonl` navigator context directly: the hits are the already-known
direct-line cluster documented 2026-08-28 — Лейб (Лев) Мордухович Ганущинер, his
parents Мордха Евсеевич Ганущинер and Хая Ганущинер, and siblings/children
(Хая/Клара Кузьмина, Рива Медведева, Голда Глуховская, Мириль Школьникова, etc.) —
surfacing as navigator/relative context on matches for their descendants. This is
the closeness-first sort working as intended (surfacing the direct VIP branch
early), not a newly discovered ancestor — no PushNotification sent (terminal was
active, and per `notify_vip.py`'s own docstring these hits still need manual
generation verification before treating any single one as a *new* direct-line find).

**Code changes**: none.
**Updated**: `wiki/log.md`.

---

## [2026-09-01] update | Switched priority from volume to closeness — stopped confirm-by-source runner

**Object**: `/tmp/mh_runner_v3.sh` (screen session `myheritage`), overall strategy
**Scenario**: regular (operator decision to reprioritize)
**Outcome**: ✅ done — background runner stopped, operator moving to manual close-relatives flow

**What happened**: Per Nikita 2026-09-01, after weeks of `--confirm-by-source`
running unattended and confirming purely by pending-count (with zero regard for
actual closeness — see [priority-list](concepts/priority-list.md)'s original
finding that raw pending count doesn't correlate with direct-ancestor overlap),
operator wants to prioritize close relatives over the distant/collateral matches
this mode has been grinding through. Since `--confirm-by-source` operates at the
whole-external-tree level (confirm all-or-nothing per source, no per-person
relationship data available at that granularity), there is no way to bias it toward
closeness — that dimension only exists in the per-match `--smart-only` flow via
`--sort-by-relationship` (MyHeritage's own "Родственной связи" sort, shipped
2026-08-28).

Given a straight choice between (a) keep the bulk runner going for volume while
doing sort-by-relationship manually on the side, or (b) drop the bulk runner
entirely and commit fully to the precise-but-slower per-match flow, operator chose
(b). Killed the `confirm-by-source` screen session. Going forward, progress comes
from the operator manually running:
```
python3 main.py --smart-only --sort-by-relationship --wait-for-captcha --visible --max 100 --scroll 8 --verbose
```
which needs the operator present to solve any captcha (this mode does extract full
field data per match, unlike confirm-by-source, so it's also strictly better for
data completeness on the people it does reach — just far slower per match).

**Monitoring implication**: the standing hourly check-in no longer has an unattended
background process to poll. It should instead check `logs/agent_*.log` (the
loguru sink main.py always writes to, regardless of mode) for activity since the
last check, and report whatever the operator's own manual runs produced — there is
nothing to restart automatically in this mode, since a stuck/dead process here just
means the operator hasn't started a session, not a bug.

**Code changes**: none. Runner script itself is `/tmp`-ephemeral and now
intentionally not running.
**Updated**: `wiki/log.md`.

---

## [2026-08-28] incident | Stuck inter-session sleep again despite caffeinate wrap, runner restarted

**Object**: `/tmp/mh_runner_v3.sh` (screen session `myheritage`)
**Scenario**: incident (caught by routine hourly monitoring)
**Outcome**: ✅ resolved — killed and relaunched, new session confirmed running

**What happened**: Session at 13:52 finished cleanly, went to sleep for the nominal
7422s (~124min, expected next run ~16:05). By 17:17 no new session had started (~72min
over); by 18:18 (next check) still nothing — same `caffeinate -i sleep 7422` PID
49634 still alive, ~2h13min past nominal, crossing the 1.5h restart threshold.
Unlike the 2026-08-08 incident, this is NOT the un-caffeinated-sleep bug (that was
fixed 2026-08-13 and the sleep here genuinely was wrapped) — `screen -ls` showed the
session alive the whole time, so this looks like a plain macOS App Nap / sleep
throttling a long-lived caffeinate child regardless of the `-i` flag, not the same
root cause. Not investigated further given the fix is identical either way (restart);
worth revisiting if it keeps recurring.

Killed (`screen -X quit` + explicit `kill` on the orphaned bash loop, same two-step
as prior incidents) and relaunched via `screen -dmS myheritage bash
/tmp/mh_runner_v3.sh`. New `--confirm-by-source` session confirmed started
immediately.

**Code changes**: none — operational restart, script content unchanged.
**Updated**: `wiki/log.md`.

---

## [2026-08-28] incident | Runner down ~8 days (likely Mac restart wiped the screen session)

**Object**: `/tmp/mh_runner_v3.sh` (screen session `myheritage`)
**Scenario**: incident (discovered while shipping the sort-by-relationship feature)
**Outcome**: ✅ resolved — recreated and relaunched, new session confirmed running

**What happened**: Last session before the gap ran cleanly 2026-08-19 21:32-21:41
(8/8 confirmed, 2542 matches), then went to sleep and never resumed — no further
`session_source_*.log` files until this entry, 2026-08-28. `screen -ls` found no
socket at all (not even a dead one), consistent with a Mac restart around
2026-08-19/20, which both wipes `/tmp` (killing the script file) and kills all
`screen` sessions outright — nothing survived to restart itself. The standing
hourly-report chain in the operator's session apparently also lapsed around the same
time (no reports were given for this whole window), so nobody caught it sooner.

Recreated `/tmp/mh_runner_v3.sh` from the last-known-good version (documented across
the 2026-08-05 and 2026-08-13 entries) and relaunched. New `--confirm-by-source`
session confirmed started immediately.

**Not fixed by this entry** (worth doing sometime): the runner has no self-healing
across a full Mac reboot — a LaunchAgent/launchd plist would survive restarts where
a bare `screen` session cannot. Flagging rather than building it now since it's out
of scope for today's actual request (the relationship-sort feature).

**Code changes**: none — operational restart. Runner script content unchanged from
the 2026-08-13 fix, just re-created since `/tmp` is ephemeral.
**Updated**: `wiki/log.md`.

---

## [2026-08-28] update | `--sort-by-relationship` — closest relatives first, using MyHeritage's own sort

**Object**: `browser/smart_matches.py`, `main.py`
**Scenario**: regular (operator request to prioritize by closeness instead of match count)
**Outcome**: ✅ shipped and verified live — top of list is now direct ancestors, including VIP surnames

**What happened**: Per Nikita 2026-08-28, wanted to go back to the per-match Smart
Matches flow but process close relatives before distant collateral ones, instead of
`run_smart_matches_session`'s existing largest-families-first (match count) order.
Found the matches-by-people page already has a native "Сортировать по:" dropdown
with a "Родственной связи" (relationship) option, alongside Значению/Количество
совпадений/Самые последние/Имя/Фамилия — MyHeritage computes this against the real
tree structure, which is far more accurate than approximating closeness from the
48-person `ancestors` list in `family_graph.json` (the earlier `priority_list.py`
approach found zero overlap for exactly this reason — see
[priority-list](concepts/priority-list.md)).

Added `sort_by` param to `get_people_sorted_by_count()`: `"count"` (default,
unchanged) or `"relationship"`, which clicks the dropdown to select "Родственной
связи" before scraping. **Needed a much longer wait than expected** — 3-5s produced
an empty list (page shell renders immediately but the relationship re-sort query is
slow server-side); 16-20s was needed before cards actually appeared, similar to the
`--confirm-by-source` source-list page's slow load. Threaded through
`run_smart_matches_session()` and exposed as `main.py --sort-by-relationship`.

**Verified live** (read-only list scrape, no confirms): top of the relationship-sorted
list is Раиса Кузьмина (Бабушка), Хая Ганущинер (Прабабушка), Василий Синчук
(Прадедушка), Лейб Ганущинер (Прапрадедушка), etc. — genuine close relatives,
several carrying the VIP Ганущинер surname. This is a read-only ordering check, not
a confirmed match, so no VIP-alert notification applies yet — that still fires per
the existing rule once an actual match for one of these people gets confirmed.

**Still applies**: this uses the per-match Smart Match flow (`--smart-only`), which
remains client-fingerprint WAF-gated in headless mode (see
[rate-limiting](concepts/rate-limiting.md)) — running it for real needs `--visible
--wait-for-captcha` with the operator present, same as before. `--sort-by-relationship`
only changes iteration order, not the WAF situation.

**Code changes**: `browser/smart_matches.py` (`sort_by` param, `_CLICK_TEXT_EXACT`),
`main.py` (`--sort-by-relationship` flag).
**Updated**: `wiki/log.md`.

---

## [2026-08-13] fix | Wrap inter-session sleep in caffeinate — was stretching hours past nominal

**Object**: `/tmp/mh_runner_v3.sh` (screen session `myheritage`)
**Scenario**: bugfix (Per Nikita 2026-08-13, after a ~6h unexplained gap between
sessions was observed and traced)
**Outcome**: ✅ fixed and applied — runner restarted, new session confirmed running

**What happened**: Flagged as a known gap in the 2026-08-08 stuck-sleep incident
entry but not fixed then. The runner's inter-session `sleep "$PAUSE"` was a bare
shell sleep, unlike the `python3 main.py` call which is wrapped in `caffeinate -i`.
If the Mac went to sleep during that window, the bash `sleep` paused along with it
and resumed only once the Mac woke — observed repeatedly stretching a nominal
30-150min pause to hours (most recently ~5h50min between the 10:30 and 18:27
sessions on 2026-08-13, self-recovered without intervention that time).

Fix: wrap the sleep too — `caffeinate -i sleep "$PAUSE"` instead of bare `sleep
"$PAUSE"`. Runner killed and relaunched with the fix; new `--confirm-by-source`
session confirmed started immediately.

**Code changes**: `/tmp/mh_runner_v3.sh` only — ephemeral, not tracked in git, full
content documented here (and in the 2026-08-05 entry for the rest of the script) so
it survives the next `/tmp` wipe.
**Updated**: `wiki/log.md`.

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
