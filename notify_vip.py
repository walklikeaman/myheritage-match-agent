"""
Scan the live-captured graph_updates.jsonl for VIP ancestor surnames and print
findings. Run after every session. Exit code 1 if NEW VIP hits found (for shell
alerting); --notify also raises a macOS notification for them. Does NOT scan
logs/session_*.log — see the 2026-09-11 incident note below the SCAN_FILES
definition for why.

VIP lineages:
  1. Ганущинер (one Н) — direct ancestor line, all spelling variants
  2. Рассадина / Рассадин — great-grandmother Maria Rassadina,
     mother of grandfather Yury Kolonov

Note: a hit here (including one from graph_updates.jsonl) only means the surname
appeared somewhere in a processed match — it is NOT generation-verified as direct
line. Treat every hit as "needs manual review," per the project's VIP alert rule.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

VIP_GROUPS = {
    "Ганущинер": [
        r"[Гг]анн?у[щш][иi]н[еeё]р",      # Ганущинер / Ганнущинер (1 или 2 Н)
        r"[Гг]анн?у[щш][еe]н[еeё]р",       # Ганущенер / Ганнущенер
        r"Gann?u[sc]h?ch?in[eo]r",          # Ganushchiner / Gannushchiner
        r"Hann?u[sc]h?ch?in[eo]r",          # Hanushchiner / Hannushchiner
        r"Gann?u[sc]h?[ck]in",             # Ganuchin / Gannuchin
        r"גאנ[וו]?שינ",                    # Hebrew
    ],
    "Рассадина": [
        # 2026-10-12: the old form required "з", so plain Рассадина/Россадина/Росадина never matched
        r"[Рр][аaоo](?:зс?с?|сс?)[аa]ди[нн]?[аоыий]?",  # Разсадина (старая орф.), Рассадина, Росадина
        r"[Рр]озс?[аa]ди[нн]?[аоыий]?",          # Розсадина (укр.)
        r"R[oa]ss?adi[nн][aoiy]?",               # Rassadin(a), Rosadin(a)
        r"Rozs?adi[nн][aoiy]?",                  # Rozsadina
    ],
}

GRAPH_UPDATES = Path("data/graph_updates.jsonl")
SCAN_FILES = [GRAPH_UPDATES] if GRAPH_UPDATES.exists() else []

# 2026-09-11 incident: this used to also scan logs/session_*.log. The runner
# appends this script's own stdout into the session log right after it runs
# (`python3 notify_vip.py >> "$LOG"`), and each hit line it prints
# ("    session_smart_X.log:1234  <surname-containing text>") itself contains
# the surname — so the NEXT run, which scans that now-larger log again, found
# its own prior hit listing as "new" hits and re-printed an even bigger
# listing into that session's log, which the run after that scanned in turn.
# This is a self-reinforcing feedback loop: hit counts and session log sizes
# both grew explosively (one session log hit 2.1GB; a `notify_vip.py` run
# reported "6315707 hit(s) found" and effectively hung). The
# SELF_OUTPUT_MARKER guard below only ever caught the summary header line
# ("VIP ANCESTOR ALERT"), not the per-hit detail lines that actually caused
# the snowball. Fixed by dropping session-log scanning entirely — every real
# hit is already captured in graph_updates.jsonl (that's where the actual
# match/relative data lives), which this script never writes to, so it can't
# feed on its own output.

# 2026-10-12 (per Nikita): notify only on NEW hits. Every hit already reported is
# remembered in SEEN_FILE by its match URL, so the old 2026-09-08 hits stop being
# re-printed every session. With --notify, new hits also raise a macOS notification;
# no hits means no notification. The first run seeds SEEN_FILE silently (those older
# hits are listed in data/conflict_review.md instead).
SEEN_FILE = Path("data/vip_seen.json")
URL_RE = re.compile(r'"match_url":\s*"([^"]+)"')


def _hit_key(group: str, line: str) -> str:
    m = URL_RE.search(line)
    return f"{group}|{m.group(1) if m else line[:200]}"


all_hits = {}  # group -> list of (fname, lineno, line)
for group, patterns in VIP_GROUPS.items():
    combined = re.compile("|".join(patterns), re.IGNORECASE)
    hits = []
    for src in SCAN_FILES:
        with open(src, encoding="utf-8", errors="ignore") as f:
            for lineno, line in enumerate(f, 1):
                if combined.search(line):
                    hits.append((src.name, lineno, line.strip()))
    if hits:
        all_hits[group] = hits

first_run = not SEEN_FILE.exists()
seen: set[str] = set() if first_run else set(json.loads(SEEN_FILE.read_text()))
new_hits = {}
for group, hits in all_hits.items():
    fresh = [h for h in hits if _hit_key(group, h[2]) not in seen]
    if fresh:
        new_hits[group] = fresh
    seen.update(_hit_key(group, h[2]) for h in hits)
SEEN_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False))
if first_run:
    new_hits = {}

total = sum(len(v) for v in all_hits.values())
if new_hits:
    n_new = sum(len(v) for v in new_hits.values())
    print(f"\n🔴 VIP ANCESTOR ALERT — {n_new} NEW hit(s) ({total} total):\n")
    for group, hits in new_hits.items():
        print(f"  [{group}] — {len(hits)} new hit(s):")
        for fname, lno, line in hits:
            print(f"    {fname}:{lno}  {line[:200]}")
    print()
    if "--notify" in sys.argv:
        groups = ", ".join(new_hits)
        subprocess.run([
            "osascript", "-e",
            (f'display notification "{n_new} новых совпадений: {groups}. Проверь data/conflict_review.md" '
             'with title "MyHeritage: VIP-предок" sound name "Glass"'),
        ], check=False)
    sys.exit(1)
elif all_hits:
    print(f"✓ No new VIP hits ({total} already reported earlier, see data/vip_seen.json).")
    sys.exit(0)
else:
    print("✓ No VIP ancestor hits (Ганущинер/Ганнущинер / Рассадина/Россадина/Росадина/Розсадина) "
          "in graph_updates.jsonl.")
    sys.exit(0)
