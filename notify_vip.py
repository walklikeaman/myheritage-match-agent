"""
Scan session logs for VIP ancestor surnames and print findings.
Run after every session. Exit code 1 if VIP hits found (for shell alerting).

VIP surnames: Ганнущинер and transliteration variants.
"""
import re
import sys
from pathlib import Path

# Name variants across RU/EN/HE logs
VIP_PATTERNS = [
    r"[Гг]анн?[уy]щ[иi]н[еeё]р",   # Ганнущинер, Ганущинер
    r"Gann?[ou]sh?ch?in[eo]r",        # Gannushchiner, Gannouchin
    r"Hann?[ou]sh?ch?in[eo]r",        # Hannushchiner
    r"Gann?[ou]chin",
    r"גאנ[וו]שינ",                    # Hebrew rough
]
VIP_RE = re.compile("|".join(VIP_PATTERNS), re.IGNORECASE)

LOGS = sorted(Path("logs").glob("session_*.log"))

hits = []
for log in LOGS:
    text = log.read_text(errors="ignore")
    for lineno, line in enumerate(text.splitlines(), 1):
        if VIP_RE.search(line):
            hits.append((log.name, lineno, line.strip()))

if hits:
    print(f"\n🔴 VIP ANCESTOR ALERT — {len(hits)} hit(s) found:\n")
    for fname, lno, line in hits:
        print(f"  {fname}:{lno}  {line}")
    print()
    sys.exit(1)
else:
    print("✓ No Ганнущинер hits in session logs.")
    sys.exit(0)
