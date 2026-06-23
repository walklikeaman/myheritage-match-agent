"""
Quick progress summary across all session logs.
Usage: python3 progress.py
"""
import re
from pathlib import Path
from datetime import datetime

LOGS = sorted(Path("logs").glob("session_*.log"))

total_ok = total_skip = total_err = total_sessions = 0
smart_ok = record_ok = 0
first_ts = last_ts = None

for log in LOGS:
    text = log.read_text(errors="ignore")

    # Session summary table
    m_ok  = re.search(r"✓ Confirmed \+ saved\s*│\s*(\d+)", text)
    m_sm  = re.search(r"·\s*Smart Matches\s*│\s*(\d+)", text)
    m_rm  = re.search(r"·\s*Record Matches\s*│\s*(\d+)", text)
    m_skip= re.search(r"⚠ Skipped\s*│\s*(\d+)", text)
    m_err = re.search(r"✗ Errors\s*│\s*(\d+)", text)

    if m_ok:
        total_sessions += 1
        total_ok   += int(m_ok.group(1))
        total_skip += int(m_skip.group(1)) if m_skip else 0
        total_err  += int(m_err.group(1))  if m_err  else 0
        smart_ok   += int(m_sm.group(1))   if m_sm   else 0
        record_ok  += int(m_rm.group(1))   if m_rm   else 0
    else:
        # Session still running — count individual lines
        ok_lines = re.findall(r"\] OK \(\d+ fields\) \| total: (\d+)", text)
        if ok_lines:
            total_sessions += 1
            total_ok += int(ok_lines[-1])  # total= is cumulative within session

    # Timestamps
    ts_matches = re.findall(r"(\d{2}:\d{2}:\d{2})", text)
    if ts_matches:
        if first_ts is None:
            first_ts = ts_matches[0]
        last_ts = ts_matches[-1]

PENDING_SM = 26095
PENDING_RM = 31722
TOTAL_PENDING = PENDING_SM + PENDING_RM
REMAINING = max(0, TOTAL_PENDING - total_ok)

avg_per_session = total_ok / total_sessions if total_sessions else 0
# Estimated seconds per match with new delays: ~20s process + ~13s sleep avg
secs_per_match = 33
secs_per_session = 200 * secs_per_match
hours_remaining = REMAINING * secs_per_match / 3600

print(f"""
╔══════════════════════════════════════════╗
║     MyHeritage Agent — Progress Report   ║
╠══════════════════════════════════════════╣
║  Sessions completed:  {total_sessions:<4d}                 ║
║  Confirmed (OK):      {total_ok:<6d}               ║
║    · Smart Matches:   {smart_ok:<6d}               ║
║    · Record Matches:  {record_ok:<6d}               ║
║  Skipped:             {total_skip:<6d}               ║
║  Errors:              {total_err:<6d}               ║
╠══════════════════════════════════════════╣
║  Total pending orig:  {TOTAL_PENDING:<6d}               ║
║  Remaining estimate:  {REMAINING:<6d}               ║
║  Progress:            {total_ok/TOTAL_PENDING*100:5.1f}%                ║
╠══════════════════════════════════════════╣
║  Est. hours left:     {hours_remaining:<6.0f}               ║
║  (at ~{secs_per_match}s/match, continuous)            ║
╚══════════════════════════════════════════╝
""")
