---
type: concept
created: 2026-06-23
updated: 2026-06-23
sources: [agent-briefing, live-probe-2026-06-23]
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
