---
description: Persist all work — surgical git add, auto-log, commit, push, verify. Run after any meaningful change is ready to ship.
---

Run the `/ship` flow for the MyHeritage automation agent repo.

**Step 1 — Diagnose**
Run `git status`, `git diff --cached`, and `git log --oneline -5`.
Spot any dangerous content (`.env`, `data/`, `logs/`, session cookies in any `.json` inside `data/`). If found → STOP and ask Nikita.

**Step 2 — Auto-log**
If no `wiki/log.md` entry exists for today's work, prepend one now (newest-first format from CLAUDE.md § auto-logging rule). Include what changed and why.

**Step 3 — Update wiki/index.md**
If any new `wiki/{sources,entities,concepts}/` pages were created, add them to the index table.

**Step 3b — Wiki test**
`python3 -m pytest -q tests/test_wiki.py` (frontmatter, index coverage, newest-first log, links, secrets). Red → fix, don't ship.

**Step 4 — Stage surgically**
`git add` only the specific files that changed. Never `-A` or `.`. Run `git diff --cached --stat` to confirm what's staged.

Check staged files don't include:
- `data/` (cookies, session state, `agent.db*`, `graph_updates.jsonl`, `merge_conflicts.jsonl`)
- `logs/`
- `.env`
- `recon/*.png` or `recon/*.html` (these are local recon artifacts)

**Step 5 — Commit**
```bash
git commit -m "$(cat <<'EOF'
<subject line ≤72 chars, present tense>

<body: WHY this change, not what — the diff shows what>

<attribution lines the session asks for>
EOF
)"
```

**Step 6 — Push**
`git push -u origin <branch>`. If on a non-main branch, note the branch name. Base new branches on the branch the live runner uses (today: PR #1's branch), not blindly on `main`.

**Step 7 — Verify**
Run `git log --oneline -3` and compare `git rev-parse HEAD` with `git ls-remote origin <branch>`: the remote sha must match.

**Step 7b — PR**
No open PR for this branch → open a draft PR (base = the branch it was cut from).

**Step 8 — Backfill commit hash**
Update the `wiki/log.md` entry for this session with the real commit hash. No `<hash>` placeholder should remain.

**Step 9 — Memory**
A new fact or decision → a pointer in project memory (one line, topic file ≤ 4 KB).

**Step 10 — Report**
Done (hash) / Logged (which wiki page updated) / Staged (list of files) / Left (what's open).
