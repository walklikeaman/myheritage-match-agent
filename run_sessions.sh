#!/bin/bash
# Stealth runner: one session per hour, 30 matches max per session.
# Looks like a human visiting the site for ~20-30 min, then leaving.
#
# Usage:
#   nohup bash run_sessions.sh > "logs/auto_$(date +%Y%m%d_%H%M%S).log" 2>&1 &
#   nohup bash run_sessions.sh 50 8 > "logs/auto_$(date +%Y%m%d_%H%M%S).log" 2>&1 &
#   (arg1 = max matches per session, arg2 = scroll rounds)

MAX=${1:-30}
SCROLL=${2:-8}
SESSION=1

echo "[$(date '+%H:%M:%S')] Auto-runner started (max=$MAX matches/session, 1h between sessions)"

while true; do
    LOG="logs/session_auto_$(date +%Y%m%d_%H%M%S)_s${SESSION}.log"
    echo "[$(date '+%H:%M:%S')] === Session #${SESSION} → ${LOG} ==="

    python3 main.py --max "$MAX" --scroll "$SCROLL" --verbose > "$LOG" 2>&1
    EXIT=$?

    tail -10 "$LOG"

    # Stop if queue is empty
    if grep -q "0 people with Smart Matches" "$LOG" 2>/dev/null && \
       grep -q "0 people with Record Matches" "$LOG" 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] Queue empty — stopping."
        python3 progress.py
        break
    fi

    # Stop on Python crash
    if [ "$EXIT" -ne 0 ] && ! grep -q "Session cap" "$LOG" 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] Session crashed (exit=$EXIT) — stopping."
        break
    fi

    python3 progress.py 2>/dev/null

    # 1-hour pause — looks like a human who logs out and comes back later
    # Slight jitter (+/- 5 min) so the timing isn't robotically exact
    JITTER=$(( RANDOM % 600 ))
    PAUSE=$(( 3600 + JITTER ))
    echo "[$(date '+%H:%M:%S')] Pause ${PAUSE}s (~1h) before session #$(( SESSION + 1 ))…"
    sleep "$PAUSE"

    SESSION=$(( SESSION + 1 ))
done
