"""
Merge browser/smart_matches.py's live-captured graph_updates.jsonl into
data/family_graph.json under a separate `harvested_people` section — additive only,
never touches the GEDCOM-derived `ancestors`/`vip_hits`/root keys (those carry verified
generation depth; harvested data only has relation-to-match-person, not depth from
Nikita, so it must not be conflated with confirmed direct-ancestor status).

Run after any session that produced new confirmed matches. See
wiki/concepts/session-economics.md for why this exists (manual GEDCOM re-export was
too heavy a lift to run per-session).
"""
import json
from pathlib import Path

from config import GRAPH_UPDATES_FILE, DATA_DIR

FAMILY_GRAPH_FILE = DATA_DIR / "family_graph.json"


def load_updates() -> list[dict]:
    if not GRAPH_UPDATES_FILE.exists():
        return []
    records = []
    for line in GRAPH_UPDATES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def merge(records: list[dict], harvested: dict) -> int:
    """Update `harvested` in place. Returns count of newly-seen names."""
    new_count = 0
    for rec in records:
        for person in rec.get("navigator", []):
            name = (person.get("name") or "").strip()
            if not name:
                continue
            entry = harvested.get(name)
            if entry is None:
                entry = {"sightings": 0, "relations": [], "first_seen": rec["ts"]}
                harvested[name] = entry
                new_count += 1
            entry["sightings"] += 1
            entry["last_seen"] = rec["ts"]
            relation = person.get("relation")
            tag = f"{relation} (via {rec['match_url'].rsplit('/', 1)[-1][:40]})" if relation else None
            if tag and tag not in entry["relations"]:
                entry["relations"].append(tag)
    return new_count


def main() -> None:
    records = load_updates()
    if not records:
        print("No graph_updates.jsonl records to accumulate.")
        return

    graph = json.loads(FAMILY_GRAPH_FILE.read_text(encoding="utf-8")) if FAMILY_GRAPH_FILE.exists() else {}
    harvested = graph.get("harvested_people", {})

    new_count = merge(records, harvested)
    graph["harvested_people"] = harvested
    graph["harvested_updated"] = records[-1]["ts"]
    graph["harvested_record_count"] = len(records)

    FAMILY_GRAPH_FILE.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Accumulated {len(records)} captured records → {len(harvested)} harvested "
          f"people total ({new_count} new this run). Saved to {FAMILY_GRAPH_FILE}")
    print("Run notify_vip.py to check the harvested names for VIP surname hits.")


if __name__ == "__main__":
    main()
