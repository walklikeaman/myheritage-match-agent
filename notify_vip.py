"""
Scan the live-captured graph_updates.jsonl for VIP ancestor surnames and print
findings. Run after every session. Exit code 1 if VIP hits found (for shell
alerting). Does NOT scan logs/session_*.log — see the 2026-09-11 incident note
below the SCAN_FILES definition for why.

VIP lineages:
  1. Ганущинер (one Н) — direct ancestor line, all spelling variants
  2. Рассадина / Рассадин — great-grandmother Maria Rassadina,
     mother of grandfather Yury Kolonov

Note: a hit here (including one from graph_updates.jsonl) only means the surname
appeared somewhere in a processed match — it is NOT generation-verified as direct
line. Treat every hit as "needs manual review," per the project's VIP alert rule.
"""
import re
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
        r"[Рр][аaоo]зс?с?[аa]ди[нн]?[аоыий]?",  # Разсадина (старая орф.), Рассадина, Росадина
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

all_hits = {}  # group -> list of (fname, lineno, line)
for group, patterns in VIP_GROUPS.items():
    combined = re.compile("|".join(patterns), re.IGNORECASE)
    hits = []
    for src in SCAN_FILES:
        text = src.read_text(errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            if combined.search(line):
                hits.append((src.name, lineno, line.strip()[:200]))
    if hits:
        all_hits[group] = hits

if all_hits:
    total = sum(len(v) for v in all_hits.values())
    print(f"\n🔴 VIP ANCESTOR ALERT — {total} hit(s) found:\n")
    for group, hits in all_hits.items():
        print(f"  [{group}] — {len(hits)} hit(s):")
        for fname, lno, line in hits:
            print(f"    {fname}:{lno}  {line}")
    print()
    sys.exit(1)
else:
    print("✓ No VIP ancestor hits (Ганущинер/Ганнущинер / Рассадина/Россадина/Росадина/Розсадина) "
          "in graph_updates.jsonl.")
    sys.exit(0)
