"""
Build data/conflict_review.md: the manual-review queue for matches the agent refused
to save (name/year conflicts) plus every VIP-surname hit, as clickable links.

Run after every session (scripts/mh_runner_smart.sh does). The house rule stands:
conflicting data is never auto-saved — this file is how Nikita reviews it on the site.

Per Nikita 2026-10-12: conflicts still have to be looked at and resolved, even though
only VIP hits raise a notification.
"""
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from browser.smart_matches import _CONFLICT_RECHECK_DAYS, _RULES_CHANGED_AT
from config import DATA_DIR, MERGE_CONFLICTS_FILE

OUT_FILE = DATA_DIR / "conflict_review.md"
VIP_SEEN_FILE = DATA_DIR / "vip_seen.json"
# match-compare/I-<tree>-5-<tree person>-I-<other tree>-<n>-<other person>
TREE_PERSON_RE = re.compile(r"match-compare/I-[A-Z0-9]+-\d+-(\d+)-")


def load_conflicts() -> dict[str, dict]:
    """Latest conflict record per match URL, flagged under the current rules."""
    cutoff = max(
        datetime.fromisoformat(_RULES_CHANGED_AT),
        datetime.now(timezone.utc) - timedelta(days=_CONFLICT_RECHECK_DAYS),
    )
    latest: dict[str, dict] = {}
    try:
        with open(MERGE_CONFLICTS_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if datetime.fromisoformat(rec["ts"]) >= cutoff:
                        latest[rec["match_url"]] = rec
                except (ValueError, KeyError):
                    continue
    except OSError:
        pass
    return latest


def load_vip() -> list[tuple[str, str]]:
    try:
        keys = json.loads(VIP_SEEN_FILE.read_text())
    except (OSError, ValueError):
        return []
    return [tuple(k.split("|", 1)) for k in keys if "|" in k]


def main() -> None:
    conflicts = load_conflicts()
    groups: dict[str, list[dict]] = defaultdict(list)
    for url, rec in conflicts.items():
        m = TREE_PERSON_RE.search(url)
        groups[m.group(1) if m else "?"].append(rec)

    after_confirm = sum(1 for r in conflicts.values() if not r.get("pre_confirm"))
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Очередь ручной проверки MyHeritage",
        "",
        (f"Обновлено {now}. Конфликтов: **{len(conflicts)}** "
         f"(уже подтверждены, но не сохранены: **{after_confirm}**). "
         "Агент такие совпадения в дерево не сохраняет: открой ссылку, сравни и реши сам."),
        "",
    ]

    vip = load_vip()
    lines += ["## VIP-фамилии", ""]
    if vip:
        for group, url in sorted(vip):
            lines.append(f"- [ ] **{group}** · [открыть совпадение]({url})")
    else:
        lines.append("Пока нет.")
    lines.append("")

    lines += [
        "## Конфликты по людям твоего дерева",
        "",
        "⚠️ = совпадение уже подтверждено, но данные не сохранены (проверить в первую очередь).",
        "",
    ]
    for person, recs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        recs.sort(key=lambda r: (r.get("pre_confirm", False), r["ts"]))
        lines.append(f"### Человек {person} · {len(recs)}")
        for r in recs:
            pairs = "; ".join(f"{c['source']} ≠ {c['suggested']}" for c in r["conflicts"])
            mark = "" if r.get("pre_confirm") else "⚠️ "
            lines.append(f"- [ ] {mark}{pairs} · [открыть]({r['match_url']})")
        lines.append("")

    OUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"conflict_review: {len(conflicts)} conflicts ({after_confirm} after confirm), "
          f"{len(vip)} VIP hits -> {OUT_FILE}")


if __name__ == "__main__":
    main()
