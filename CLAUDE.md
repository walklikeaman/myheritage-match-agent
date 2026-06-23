# MyHeritage Automation Agent — Project Schema

## Behavioral guidelines
Apply the `karpathy-guidelines` skill on every non-trivial task: think before
coding, surface assumptions, surgical changes, define verifiable success.

When drafting any reply to a MyHeritage message (incoming letters from potential relatives, DNA matches, researchers), apply the `humanizer` skill before finalizing the text. No em dashes, no AI vocabulary, warm and direct tone.

## First-run behaviour
If `wiki/sources/` is empty (no ingested sources yet), say: "Drop raw files
into `Context/` and tell me to ingest — I'll build the graph under `wiki/`." Then wait.

## Session-startup ritual (read before doing anything)
1. This file.
2. Operator memory: `cat ~/.claude/projects/-Users-walklikeaman-GitHub-My-Heritage/memory/MEMORY.md 2>/dev/null`
3. Knowledge graph: `cat graphify-out/GRAPH_REPORT.md 2>/dev/null | head -80`
4. Recent log: `grep "^## \[" wiki/log.md | head -20`
5. Active guardrails: `cat .loops/guardrails.md 2>/dev/null`
6. Available commands: `ls .claude/commands/`
7. Recent commits: `git log --oneline -10 2>/dev/null && git status --short 2>/dev/null`
8. `wiki/index.md` if the task touches domain knowledge.

If an existing wiki/log/graph entry covers the request, CITE it before acting.

## Per-task operating loop
Surface assumptions → check prior work → state plan → probe (throwaway `_probe_*.py`) → run → verify by re-reading the actual resource → clean up probe scripts → log it → `/ship`.

## Auto-fire the loops (don't wait to be told)

| Trigger | Command |
|---------|---------|
| After any code/wiki/config change | `/loop-docs-sync` |
| After every `/ship` | `/loop-changelog` |
| Same failure twice | `/loop-guardrails` |
| Bug resisted one fix | `/loop-debug` |
| Post-impl, pre-commit | `/loop-de-sloppify` |
| Lint errors | `/loop-lint` |

## /ship
When work is ready to persist, type `/ship` — surgical stage, auto-log, commit, push, verify remote. See `.claude/commands/ship.md`.

## Wiki layer (agent-owned) — the GRAPH knowledge base
`Context/` is raw & immutable (never edit it). `wiki/` is yours to write and cross-link.
- `wiki/index.md` — catalog. READ FIRST before any domain question.
- `wiki/log.md` — append-only journal, newest-first.
- `wiki/overview.md` — living synthesis.
- `wiki/sources/` — one page per ingested raw source.
- `wiki/entities/` — MyHeritage, Smart Matches, Record Matches, Family Graph API.
- `wiki/concepts/` — match evaluation, auth, rate limiting, selectors, extraction.

## Operations
**Ingest**: read source → discuss → `wiki/sources/<slug>.md` → create/update `entities/` + `concepts/` (cross-link `[[…]]`) → prepend `wiki/log.md` entry → update `wiki/index.md`.
**Query**: read `wiki/index.md` first → drill in → answer with citations.
**Lint**: contradictions, stale claims, orphans, missing concept pages, broken links.

## Auto-logging rule (no exceptions)
After EVERY meaningful operation, prepend a `wiki/log.md` entry and commit — without being asked. Unsure if meaningful? Default YES. Cite the commit hash in the log entry.

## Page conventions
YAML frontmatter: `type / created / updated / sources` (required) + `confidence / status / relates_to / staleness_window / tags` (optional). Today's date absolute (YYYY-MM-DD). Paraphrase — no long quotes. Relative links so Obsidian + GitHub both resolve.

## House rules (non-negotiable)
- **Never `git add -A` / `git add .`** — explicit paths only.
- **`wiki/log.md` newest-first within a day.** (Guardrail.)
- **Read `wiki/index.md` before any domain question.** (Guardrail.)
- **Never touch selectors in code without reading `wiki/concepts/selectors.md` first.**
- **After any recon run, update `wiki/concepts/selectors.md`.**
- **Never auto-save conflicting genealogy data** (name conflicts, date conflicts, relationship restructures) — flag for manual review.
- **Max 500 matches per agent session.** (Safety guardrail — raised from 200 after 539 clean runs, zero rate-limit events.)
- **Probe scripts are `_probe_*.py`** — delete before commit; productize on 2nd repeat.
- **Verify by re-reading reality** — never report success off stdout alone.
- **Language: follow the source** — RU/EN both fine in wiki.

## VIP ancestor alert (auto-notify)
If any confirmed match contains a **direct paternal/maternal ancestor** — send a PushNotification immediately and log the finding in `wiki/log.md`. Run `python3 notify_vip.py` after every session to check. Exit code 1 = hit found. Do NOT notify for collateral relatives — only direct line.

VIP surnames (all variants tracked in `notify_vip.py`):
- **Ганущинер / Ганнущинер** (1 или 2 Н — оба варианта) — variants: Ганушинер, Ganushchiner, Gannushchiner, Hanushchiner, גאנושינר
- **Рассадина / Рассадин** — прабабушка Мария Рассадина, мать деда Юрия Колонова; variants: Россадина, Росадина, Розсадина, Rassadina, Rossadina, Rozsadina

## What NOT to do
Never edit `Context/`. Never `git add -A`. Don't pre-create empty pages (born on first ingest). Don't duplicate across pages (cross-link instead). Don't bury domain knowledge in code comments — put it in wiki.
