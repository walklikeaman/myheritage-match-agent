---
type: concept
created: 2026-06-23
updated: 2026-09-08
sources: [agent-briefing]
confidence: high
status: active
relates_to: [smart-matches, record-matches, data-extraction, selectors]
staleness_window: none
tags: [decision-logic, core]
---

# Concept: Match Evaluation

The decision engine that determines what happens to each match.

## Decision rules

```
confidence ≥ 80%  → decision = "accepted"  → proceed to confirmation + extraction
confidence < 80%  → decision = "skipped"   → log, move on (NEVER auto-reject)
new_info_count = 0 AND accepted → confirm only, skip extraction
has conflicts     → decision = "flagged"   → write to flagged_matches, manual review
error during processing → decision = "error" → log error, move on
```

**Why never auto-reject?** Nikita may want to manually review borderline matches later. Logging as "skipped" preserves that option.

## Conflict detection (auto-save is BLOCKED for these)
- Name differs from existing tree data → flag `name_mismatch`
- Date conflicts with existing data → flag `date_conflict`
- Relationship would restructure tree hierarchy → flag `relationship_restructure`

These go to `flagged_matches` table with full match JSON for human review.

**Status (2026-09-12): `_names_conflict()` upgraded to handle spelling/transliteration variants.**
Per Nikita 2026-09-12, after one family cluster (Orenstein/Klonsky/Radzyner)
sustained a 90-100% conflict rate for days, re-tested against that cluster's
history showed most of it was false positives, not real name mismatches:
nicknames ("Sam"/"Samuel"), transliteration spelling ("Eliashiv"/"Elyashiv",
"Raifman"/"Reifman"), slash-alternative lists MyHeritage itself lists
("Yosef/Yoseph"), hyphenated compounds ("משה-יהודה-לייב"), a person's name
recorded as only one of several given names they had ("Haim" vs "Joseph
Haim"), a Spanish "nacida" maiden-name marker the code didn't recognize
(only "born"/"née"/"לבית" were), and untitled Hebrew scholarly honorifics
("הגאון") stacking after "הרב" and getting compared as if they were the name.
`_names_conflict()` now splits each name into a given-name pool and a surname
pool (`_name_pools()`) — sets of acceptable spellings, not one positional
value — and requires overlap in BOTH pools to clear a pair; a shared surname
alone is deliberately not enough, since that's the exact shape of a real
wrong-person mismatch within one large family. A parenthetical aside is
routed to the surname pool only if it resembles the surname (`(ORENSTEIN)`
for "Oren") and to the given-name pool otherwise (`(Jacob)` glossing
"Yaakov") — guessing "both pools" for every aside was tried first and
backfired: an unrelated given-name gloss sitting in the surname pool could
out-vote a legitimate cross-script surname match. `_trailing_surname_run()`
walks backward from the last word to catch a surname repeated across several
alternate spellings/scripts in a row (e.g. "...Orenstein אורנשטיין Urstein"),
but only trusts a chain of 3+ (2 confirmed hops) — a single cross-script hop
turned out to be indistinguishable from a given name simply sitting next to
a Hebrew surname ("Joseph **Haim** אורנשטיין"), so a 2-long chain falls back
to the plain last-word guess. Re-run against the full `merge_conflicts.jsonl`
history (568 unique pairs): flagged conflicts dropped from 316 to 142 (55%);
on the most recent live batch from the Orenstein cluster, 55 of 74 previously
blocked pairs now clear automatically. Known remaining gaps, left alone
deliberately rather than risk over-fitting: (1) a bare English/Hebrew
name-translation pair with no shared spelling at all (e.g. "Isaac" for
"Yitzhak") isn't recognized — that's a translation-equivalence table, a
different feature than spelling-variant matching; (2) when a surname's only
same-script comparable form sits one position before the tree's literal last
word with no maiden-name marker to route it (e.g. "Rose Bloom" vs "Rose /
Raisel **Lubanov** לובנוב"), the comparable Latin surname can still be missed.
Both fail safe (stay flagged for manual review), not silently cleared.

**Status (2026-09-10): checked BEFORE confirming, not just before saving.**
The 2026-09-08 version below caught conflicts only after `Confirm` had already
been clicked — the match link on MyHeritage's side was already created by the
time a conflict was found, even though Save was skipped. Per Nikita 2026-09-10
("сначала посмотри, тот человек или нет, а не постфактум"), moved the check
earlier: the compare page already renders a full relatives comparison (see
[selectors](selectors.md#match-compare-page--pre-confirm-relatives-comparison-2026-09-10))
before Confirm is clicked, so `_pre_confirm_conflicts()` now runs on that data
first and skips the match entirely (never clicks Confirm) when it finds a clear
mismatch. The original post-confirm check (`_extract_merge_conflicts()`) stays
in place as a second safety net, since the wizard's "expand additional
relatives" step can surface people not shown on the initial compare page.

**Status (2026-09-08): `name_mismatch` implemented, the other two are not.**
This design was written 2026-06-23 and stayed unimplemented for months — the
`--smart-only` flow shipped without any conflict check at all, and it took a
live incident (operator spotted a wrong confirm on screen — see wiki/log.md
2026-09-08) to surface that gap; an audit of already-confirmed matches then
found 265 pre-existing conflicts going back to 2026-07-19. The actual
implementation lives in `browser/smart_matches.py`
(`_extract_merge_conflicts()`/`_names_conflict()`), not a separate
`agent/evaluator.py`, and writes to `data/merge_conflicts.jsonl`
(`MERGE_CONFLICTS_FILE`), not a `flagged_matches` table — it works by parsing
the extract wizard's own "Выберите X в Вашем семейном дереве: Y"
disambiguation text (present when MyHeritage itself isn't sure two profiles
are the same) and comparing X vs Y, rather than comparing against a
structured record of the tree's existing data. Date-conflict and
relationship-restructure detection are still unimplemented — this page's
original design for those two remains the intended direction, not yet built.

## Extraction priority (when saving data)
1. Birth date + place (high value, often missing)
2. Death date + place
3. Photos (very hard to find manually — grab everything)
4. Additional relatives (parents, siblings — tree expansion)
5. Source citations (links to original records — critical for genealogy integrity)
6. Newspapers / obituaries (rich narrative context)

## Implementation location
`agent/evaluator.py` — not yet written (Phase 2).

## Confidence score source
The confidence score is displayed on the match card in the MyHeritage UI. Exact selector TBD pending recon — see [[selectors]].
