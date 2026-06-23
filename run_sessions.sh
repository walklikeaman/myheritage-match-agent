#!/bin/bash
# Chains sessions back-to-back until no matches remain.
# Usage: nohup bash run_sessions.sh > logs/auto.log 2>&1 &
# Or:    nohup bash run_sessions.sh 500 > logs/auto.log 2>&1 &  (500 per session)

MAX=${1:-200}
SCROLL=${2:-20}
SESSION=1

echo "[$(date '+%H:%M:%S')] Auto-runner started (max=$MAX scroll=$SCROLL)"

while true; do
    LOG="logs/session_auto_$(date +%Y%m%d_%H%M%S)_s${SESSION}.log"
    echo "[$(date '+%H:%M:%S')] === Session #${SESSION} → ${LOG} ==="

    python3 main.py --max "$MAX" --scroll "$SCROLL" --verbose > "$LOG" 2>&1
    EXIT=$?

    # Show last 8 lines (summary table)
    tail -10 "$LOG"

    # Stop if no people found (all done)
    if grep -q "Found 0 people\|Total: 0 unique" "$LOG" 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] All matches exhausted — done."
        python3 progress.py
        break
    fi

    # Stop on Python crash (not empty-queue)
    if [ "$EXIT" -ne 0 ] && ! grep -q "Session cap" "$LOG" 2>/dev/null; then
        echo "[$(date '+%H:%M:%S')] Session crashed (exit=$EXIT) — stopping."
        break
    fi

    python3 progress.py 2>/dev/null

    # Short breather between sessions (avoid session cookie expiry)
    PAUSE=$(( RANDOM % 30 + 30 ))
    echo "[$(date '+%H:%M:%S')] Pause ${PAUSE}s before next session…"
    sleep "$PAUSE"

    SESSION=$(( SESSION + 1 ))
done
