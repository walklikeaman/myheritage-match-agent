---
type: concept
created: 2026-06-23
updated: 2026-07-17
sources: [agent-briefing, live-probe-2026-06-23, postmortem-2026-06-26, live-recon-2026-06-27, live-recon-2026-07-17]
confidence: high
status: active
relates_to: [smart-matches, record-matches, data-extraction]
staleness_window: 30d
tags: [selectors, verified]
---

# Concept: MyHeritage CSS Selectors

> **CONFIDENCE: HIGH** — verified via live probes on 2026-06-23 with full Playwright session.
> **STALENESS**: 30 days — MyHeritage updates their UI regularly.

## Verified selectors (2026-06-23)

### Matches-by-people page
URL: `/discovery-hub/{TREE_ID}/matches-by-people?matchType=2&matchStatus=32&lang=RU`

| Element | Selector | Notes |
|---------|----------|-------|
| Person links | `a[href*="matches-for-person"]` | Each link has `personId` in href |
| Match count text | `card.innerText` matching `/Просмотрите\s+(\d+)\s+совпадени/` | Text inside card container |
| Person name | `[class*="person_name"],[class*="fullname"],[class*="title"]` | Walk up from link |

### Matches-for-person page
URL: `/discovery-hub/{TREE_ID}/matches-for-person/{personId}?matchType=2&matchStatus=32&lang=RU`

| Element | Selector | Notes |
|---------|----------|-------|
| Match links | `a[href*="match-compare"]` | Each href has full match ID |
| Person info | `.innerText` of card | "НОВОЕ" prefix on new fields |

### Match-compare page (Smart Match)
URL: `/discovery-hub/{TREE_ID}/match-compare/{matchId}?lang=RU`

| Element | Selector/trigger | Notes |
|---------|----------|-------|
| Confirm button | `ng-click="vm.invokeAction(vm.actionButtons[0].action, $event)"` text=`Подтвердить совпадение` | Angular — use `triggerHandler('click')` |
| Save in tree | `ng-click="vm.invokeAction(item.action, $event)"` text starts `Сохранить в Вашем дереве` | Saves TEXT only, no photos |
| Reject | `ng-click="vm.rejectMatch()"` | NEVER call this |
| Photo circles | `ng-click="uploadPhoto()"` | 15-35 per page, transfers photo from match |
| Already confirmed | body text includes `подтверждено` | Skip check before confirm |

**After clicking "Подтвердить совпадение":** page navigates to `showExtractWizard` URL (15s+ wait needed for Angular render).

### Wizard page (showExtractWizard)
URL: `/research/collection-1/семейные-деревья-myheritage?action=showExtractWizard&itemId=...&indId=...&s=...`

| Element | Selector | Notes |
|---------|----------|-------|
| Extract all (family) | `ng-click="extractAllInfoFromAllPeople()"` class=`extract_record_row_copied_all_from_all` | Main extraction — ALL people in family |
| Extract-all toggle | class contains `copied_all_from_all_true` when active | Verify after click |
| Expand more relatives | Text starts `Извлечь информацию еще об N родственниках` | Optional deeper extraction |
| Save (Smart Match) | `id="saveButton"` text=`Сохранить в дерево` | Final save |
| Save (Record Match) | `ng-click="saveAndNavigateTo(false)"` text=`Сохранить в дерево` | Record Match alternative |
| Photo containers | `[class*="individual_photo_container"]` | 10-15 per person in family |
| Photo upload circles | `ng-click="uploadPhoto()"` | 35+ on wizard — trigger to import photo |
| Field copy buttons | `[class*="extract_record_row_copy_button_copied"]` | Count = number of copied fields |
| Single-field sign | `[class*="extract_record_row_copied_all_sign"]` | Shown when only 1 field exists |

**ng-click response pattern**: Always use `window.angular.element(el).triggerHandler('click')` — native `.click()` and `dispatchEvent` don't update Angular model state.

> ✅ **RESOLVED (2026-06-27, live recon): the extract-all selectors are NOT stale.**
> Live headless probes confirmed the documented controls render correctly — real wizards
> show the `Извлечь всю информацию` text node, 46-54 field checkboxes, and a working
> `saveButton`. The 751 "saveButton not found" failures were never a selector problem:
> `_CLICK_EXTRACT_ALL` returned `{clicked: None}` because the WAF served a **reCAPTCHA
> bot-challenge in place of the wizard** (see "Bot-challenge interstitial" below). The agent
> now polls for the control before reading, and classifies a challenge as `blocked` (abort +
> back off) instead of pressing on to a doomed save. See
> [session-economics](session-economics.md) for the corrected root-cause analysis.

### Bot-challenge interstitial (reCAPTCHA Enterprise) — 2026-06-27

When MyHeritage FraudProtection flags the session it serves a Google reCAPTCHA Enterprise
challenge **in place of** the requested page — as **HTTP 200**, not a 4xx/5xx, which is why
log greps for `429|503|captcha` never caught it. This is the real cause of the old
"saveButton not found" mass failures.

| Signal | Value on a challenge page |
|--------|---------------------------|
| Challenge iframe | `iframe[src*="recaptcha-challenge.php"]` (`/FP/recaptcha-challenge.php`) |
| Body text (RU) | `возможно, Вы - робот … докажите, что Вы человек` |
| Body length | ~578 chars (real wizard: 17k-33k) |
| Angular app | absent (`[ng-app]`/`[ng-controller]` count = 0) |
| Page title | generic `Nakonechnyi Web Site - MyHeritage` |

Detection lives in `_IS_BOT_CHALLENGE` (`browser/smart_matches.py`): the
`recaptcha-challenge.php` iframe, OR a <3000-char body containing the "Вы человек / докажите"
/ "prove you are human" phrases. A reload does **not** clear it; nor does a 25s backoff +
re-nav within the same session. The agent treats it as a **circuit breaker** — status
`blocked`, abort the session, emit a `captcha` log token so the auto-runner applies its long
backoff. **Do not click "Продолжить" / attempt the checkbox** — backing off is the safe
response.

### Second WAF vendor: Imperva Incapsula — 2026-07-17

Live recon during a session that showed 0 OK / 84+ SKIP across 7 different people (every
single match "wizard-empty") found a **second, distinct** bot-challenge, served by **Imperva
Incapsula**, not Google reCAPTCHA:

| Signal | Value |
|--------|-------|
| Challenge iframe | `iframe[src*="_Incapsula_Resource"]` (query params `SWUDNSAI`, `incident_id`, `cinfo`, `rpinfo`) |
| Body text | **empty** (0 chars) |
| HTML length | ~886 bytes |
| Angular app | absent (0 `[ng-app]`/`[ng-controller]` nodes) |
| URL | still the real `showExtractWizard` URL — only the response body is swapped |

Neither the old recaptcha-iframe selector nor the "докажите, что Вы человек" body-text regex
matches this variant, so `_await_wizard_ready` fell through to `'empty'` (skip) instead of
`'challenge'` (blocked) — the confirm-then-fail-to-enrich bleed the original fix was meant to
prevent, except this time **the runner never backs off**, so it burns through every match for
every person in the session at 0% yield. Fixed by adding the Incapsula iframe selector to
`_IS_BOT_CHALLENGE` (`browser/smart_matches.py`) — same circuit-breaker path as the reCAPTCHA
case. Verified live: a fresh confirmed match now returns `status: 'blocked'` immediately
instead of `'empty'` after the 10s poll.

**Takeaway**: MyHeritage's FraudProtection appears to rotate between at least two WAF
vendors. Any future "wizard-empty at scale, 0% success across multiple people" symptom should
be treated as a probable **third undetected challenge variant** — probe live with a fresh
unconfirmed match, dump `iframe` src list + body length + HTML length, and extend
`_IS_BOT_CHALLENGE` rather than assuming it's a render race or a stale-list issue.

### Success indicators

| State | Check |
|-------|-------|
| Match already confirmed | `document.body.innerText.includes('подтверждено')` |
| Extract-all toggled | `el.className.includes('copied_all_from_all_true')` |
| Wizard save complete | Page redirects to `match-compare/**#rm_*` |

### Infinite-scroll (matches-by-people)
- Scroll trigger: `window.scrollTo(0, document.body.scrollHeight)` + 3-5s wait
- Loads ~20 people per scroll round
- Stops when no new IDs appear (seen-set dedup)

## Key function names (Angular scope)
- `extractAllInfoFromAllPeople()` — extracts ALL fields for ALL people in wizard
- `uploadPhoto()` — imports one photo from matched tree to your tree
- `saveAndNavigateTo(false)` — saves and returns to match-compare (Record Match wizard)
- `vm.invokeAction(...)` — confirms/saves from match-compare page
- `vm.rejectMatch()` — **DO NOT CALL** — permanently rejects match

## Update procedure
1. Run a new probe against live pages
2. Update tables above with any changed selectors
3. Set `updated: <today>` in frontmatter
4. Run `/ship`
