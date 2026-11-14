# Guardrails — MyHeritage Agent

> Permanent hard constraints. Written when a failure repeated twice. Read at session startup. Treated as law.

## Guardrail: Never git add -A or git add .
**Written**: 2026-06-23 (Per universal-agent-framework)
Explicit paths only in all `git add` commands. Never use `-A` or `.` — these can accidentally include `data/` (contains session cookies), `.env`, or `logs/`.

## Guardrail: wiki/log.md entries newest-first within a day
**Written**: 2026-06-23 (Per universal-agent-framework)
Prepend new entries at the top of the file, not append at the bottom.

## Guardrail: Read wiki/index.md before any domain question
**Written**: 2026-06-23 (Per universal-agent-framework)
Don't answer questions about match flow, API limits, selectors, or extraction rules from memory — check the wiki first.

## Guardrail: Never touch selectors without reading wiki/concepts/selectors.md first
**Written**: 2026-06-23 (Per house rules in CLAUDE.md)
Selectors in MyHeritage UI change. The wiki page tracks verified vs. candidate selectors. Reading it first avoids coding against stale selector assumptions.

## Guardrail: Never auto-save conflicting genealogy data
**Written**: 2026-06-23 (Per house rules in CLAUDE.md)
Name mismatches, date conflicts, and relationship restructures always go to `flagged_matches` table for manual review. This protects tree integrity.

## Guardrail: Max 500 matches per agent session
**Written**: 2026-06-23 (Per briefing risk table). **Updated**: 2026-11-13 — the ceiling was raised from 200 to 500 after 539 clean runs (`CLAUDE.md`); this line had kept the old 200.
Hard ceiling 500; working cap is `MAX_MATCHES_PER_SESSION=100` in `config.py` (why: `wiki/concepts/session-economics.md`). Never raise either without explicit instruction from Nikita.

## Guardrail: The runner lives in launchd from the repo, never in /tmp or screen
**Written**: 2026-11-13 (repeated 7× in Sep–Oct 2026: every Mac reboot wiped the `/tmp` runner, longest gap ~16 days; see `wiki/log.md` 2026-09-08 … 2026-10-12)
Start and stop only via `launchctl` and `scripts/com.walklikeaman.myheritage-runner.plist`. One runner per account: Mac Mini. The MacBook runner stays unloaded.

## Guardrail: On captcha/WAF, pause — never retry in a loop or try to get around it
**Written**: 2026-11-13 (repeated: crash-loop of 395 sessions 2026-10-16…19, then 10 days of captcha 2026-10-22…11-03)
A session that sees `(captcha)` or Incapsula ends and the runner sleeps 6 h. A streak that survives several pauses needs a fresh login by Nikita (`wiki/concepts/captcha-and-waf.md`). The agent never types the password.
