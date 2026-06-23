"""
Scan session logs for VIP ancestor surnames and print findings.
Run after every session. Exit code 1 if VIP hits found (for shell alerting).

VIP lineages:
  1. Ганущинер (one Н) — direct ancestor line, all spelling variants
  2. Рассадина / Рассадин — great-grandmother Maria Rassadina,
     mother of grandfather Yury Kolonov
"""
import re
import sys
from pathlib import Path

VIP_GROUPS = {
    "Ганущинер": [
        r"[Гг]ану[щш][иi]н[еeё]р",        # Ганущинер, Ганушинер
        r"[Гг]ану[щш][еe]н[еeё]р",         # Ганущенер
        r"Ganu[sc]h?ch?in[eo]r",            # Ganushchiner, Ganuchinер
        r"Hanu[sc]h?ch?in[eo]r",            # Hanushchiner
        r"Ganu[sc]h?[ck]in",               # Ganuchin, Ganushin
        r"גאנ[וו]?שינ",                    # Hebrew
    ],
    "Рассадина": [
        r"[Рр]ассади[нн]?[аоыий]?",        # Рассадина, Рассадин, Рассадиной
        r"[Рр]асади[нн]?[аоыий]?",         # Расадина (one С variant)
        r"Rassadi[nн][aoiy]?",             # Rassadina, Rassadin
        r"Rasadi[nн][aoiy]?",              # Rasadina
        r"Расcаді[нн]",                    # Ukrainian spelling
    ],
}

LOGS = sorted(Path("logs").glob("session_*.log"))

all_hits = {}  # group -> list of (fname, lineno, line)
for group, patterns in VIP_GROUPS.items():
    combined = re.compile("|".join(patterns), re.IGNORECASE)
    hits = []
    for log in LOGS:
        text = log.read_text(errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            if combined.search(line):
                hits.append((log.name, lineno, line.strip()))
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
    print("✓ No VIP ancestor hits (Ганущинер / Рассадина) in session logs.")
    sys.exit(0)
