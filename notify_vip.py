"""
Scan session logs AND the live-captured graph_updates.jsonl for VIP ancestor
surnames and print findings. Run after every session. Exit code 1 if VIP hits
found (for shell alerting).

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

LOGS = sorted(Path("logs").glob("session_*.log"))
GRAPH_UPDATES = Path("data/graph_updates.jsonl")
SCAN_FILES = LOGS + ([GRAPH_UPDATES] if GRAPH_UPDATES.exists() else [])

# The runner appends this script's own stdout into the same session logs it scans
# next time round. Its own status lines spell out the tracked surnames verbatim
# ("No VIP ancestor hits (Ганущинер/... / Рассадина/...)"), so without this guard the
# script would match its own prior "no hits" message forever, every single run.
# "VIP ancestor hit" is a stable marker distinct from any real extracted genealogy
# text — filter it out before regex-matching, regardless of message wording changes.
SELF_OUTPUT_MARKER = "vip ancestor hit"

all_hits = {}  # group -> list of (fname, lineno, line)
for group, patterns in VIP_GROUPS.items():
    combined = re.compile("|".join(patterns), re.IGNORECASE)
    hits = []
    for src in SCAN_FILES:
        text = src.read_text(errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            if SELF_OUTPUT_MARKER in line.lower():
                continue
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
          "in session logs or graph_updates.jsonl.")
    sys.exit(0)
