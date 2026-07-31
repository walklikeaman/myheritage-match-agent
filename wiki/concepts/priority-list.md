---
type: concept
created: 2026-08-01
updated: 2026-08-01
sources: [live-note-2026-08-01]
confidence: high
status: active
relates_to: [myheritage, rate-limiting, family-graph-api]
staleness_window: 60d
tags: [manual-workflow, triage]
---

# Concept: Priority list for manual match review

`priority_list.py` is a read-only helper for splitting the workload between the
automated runner and manual confirmation in a real browser (see
[rate-limiting](rate-limiting.md) — the WAF flag turned out to be a client-fingerprint
block on the automation tool itself, not something a human pass or waiting fixes, so
manual review in an ordinary browser is currently the only reliable path for the
people it can't get through).

## What it does
1. Calls the same `get_people_sorted_by_count()` used by the runner to list pending
   Smart Matches people (no confirm clicks — this step alone has never triggered the
   WAF challenge, only the confirm action does).
2. Cross-references each pending person's name against `data/family_graph.json`'s
   `ancestors` (48 direct-line people) and the VIP surname patterns (Ганущинер/
   Ганнущинер, Рассадина/Рассадин and variants).
3. Sorts VIP hits first, then ancestor-name hints, then by raw pending-match count.
4. Writes `data/priority_list.md` — a table the operator can work down manually.

## Known limitation (2026-08-01)
The cross-reference is a crude shared-surname-token match against the 48 saved
ancestors, not a full family-graph relationship check. On the first real run, none of
the top 160 pending Smart Match people matched — the highest-count matches are all
from an unrelated medieval English nobility branch (Fitzalan, Talbot, Beauchamp),
which doesn't share tokens with the Ukrainian/Belarusian direct line. The list still
works as a plain count-sorted triage in that case, just without the VIP/ancestor
markers doing anything.

## Usage
```bash
python3 priority_list.py --top 60
```
