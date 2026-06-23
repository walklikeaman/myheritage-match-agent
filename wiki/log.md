# Wiki Log — MyHeritage Automation Agent

> Append-only. Newest entries first within each day. One entry per meaningful operation.

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
