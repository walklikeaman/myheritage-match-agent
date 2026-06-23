# Wiki Log — MyHeritage Automation Agent

> Append-only. Newest entries first within each day. One entry per meaningful operation.

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
