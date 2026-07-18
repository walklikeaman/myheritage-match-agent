---
type: concept
created: 2026-07-18
updated: 2026-07-18
sources: [live-recon-2026-07-18]
confidence: medium
status: active
relates_to: [smart-matches, selectors, session-economics]
staleness_window: 60d
tags: [graph, vip-alert, wizard, incremental]
---

# Concept: Incremental local graph accumulation

> **Bottom line:** the confirming bot now captures each wizard's navigator (name +
> relation-to-match) and raw field text into `data/graph_updates.jsonl`, so the local
> family graph grows automatically as matches get confirmed — no manual GEDCOM
> re-export required per update. `graph_accumulate.py` merges these into
> `data/family_graph.json` under a separate `harvested_people` key.

## Why this exists

`data/family_graph.json` used to update only when someone manually exported a fresh
GEDCOM from MyHeritage and ran `gedcom_graph.py` against it — a real chore at this
volume (12,000+ confirmed matches and counting), and the operator asked for it to stop
being their problem. See the operator's 2026-07-18 request: exporting the tree
constantly is too heavy a lift; the agent should accumulate on its own from what it's
already touching during confirmation.

## What gets captured, and from where

Recon on a live wizard (`_await_wizard_ready` state `'control'`) found two reliable,
low-risk-of-breakage sources:

| Element | Selector | Gives |
|---------|----------|-------|
| Navigator sidebar item | `li.individual_navigator_item` (class `main_true`/`main_false`) | one entry per person the extraction touches |
| Person name | `.individual_full_name` inside the navigator item | full name as MyHeritage renders it |
| Relation to main | `.individual_relationship` inside the navigator item | e.g. "Жена Torild", "Дочь Torild" — relative to the matched person, NOT to Nikita |
| All structured fields | `.extract_record_row` (flat list, DOM order) | Имя/Фамилия/Рождение/Смерть/Родители/Брак/Захоронение as plain innerText, per person, in order |

`_capture_graph_snapshot` (in `browser/smart_matches.py`) reads both, wrapped in a
try/except that can never raise — a capture failure must never affect the real
confirm/extract/save flow, which is the entire point of the automation. It's called
once per successful match, right after the field count check and before the photo
transfer step, and appended (one JSON object per line) to `data/graph_updates.jsonl`
via `_append_graph_update`.

## The generation-depth limitation (read before trusting a "VIP hit")

**This is the one thing to get right when using this data**: `relation` is relative to
the *matched person* in that specific wizard, not to Nikita (the tree root). A hit like
`"Жена Torild"` tells you the harvested name is Torild's wife — it tells you nothing
about how many generations that whole family sits from Nikita. The GEDCOM-derived
`ancestors`/`vip_hits` keys in `family_graph.json` carry verified generation depth
(`is_direct_ancestor`, `generation`); `harvested_people` does not and never will
without walking the tree's actual parent-child edges, which this capture doesn't do.

Practical consequence: `notify_vip.py` now also scans `data/graph_updates.jsonl` (in
addition to session logs), so a VIP surname appearing anywhere in harvested data still
surfaces as a hit — same as it already did for anything printed to a session log. But
per the project's VIP alert rule ("do NOT notify for collateral relatives — only direct
line"), **treat every harvested-source hit as needing manual review**, not as a
confirmed direct-ancestor alert. Only the GEDCOM-based `vip_hits` with
`is_direct_ancestor: true` are generation-verified.

## Files

- `browser/smart_matches.py` — `_NAVIGATOR_PEOPLE`, `_EXTRACT_ROWS_TEXT`,
  `_capture_graph_snapshot`, `_append_graph_update`
- `config.py` — `GRAPH_UPDATES_FILE = data/graph_updates.jsonl`
- `graph_accumulate.py` — merges the JSONL into `family_graph.json`'s
  `harvested_people` key (additive only, never touches GEDCOM-derived keys)
- `notify_vip.py` — extended to scan `data/graph_updates.jsonl` alongside session logs

## Verified live (2026-07-18)

Ran the full pipeline against a real, previously-unconfirmed Smart Match (Torild
Blot-Sven Totilsson Kol family, 3 people): `process_one_match` → `graph_updates.jsonl`
gained a record with all 3 navigator entries + ~10KB of raw field text →
`graph_accumulate.py` merged 3 new `harvested_people` entries without touching the
existing `ancestors`/`vip_hits` →`notify_vip.py` ran clean (no VIP hit, exit 0).

## Runner integration

`/tmp/mh_runner_v3.sh` now runs `graph_accumulate.py` and `notify_vip.py` after every
`main.py` invocation (regardless of clean/crash/captcha exit), before applying the
backoff. Output goes to the same session log. See [selectors](selectors.md) for the
wizard-state polling this builds on.
