#!/bin/bash
# Standing runner for `main.py --smart-only|--record-only --sort-by-relationship`.
# Started at login by launchd (scripts/com.walklikeaman.myheritage-runner.plist);
# see wiki/log.md 2026-10-12. Runs --background (new headless Chromium, passes the WAF).
# Every RECORD_EVERY-th session works Record Matches instead of Smart Matches
# (per Nikita 2026-10-12: both kinds in the background loop). 0 = off.
# Records go through the record viewer + record wizard flow (pilot 5/5, 2026-10-13);
# Nikita picked every 3rd session on 2026-10-17 (wiki/concepts/selectors.md).
cd "$(dirname "$0")/.." || exit 1
MAX_MATCHES=100
RECORD_EVERY=3
SESSION=0

rand_pause() {
    TIER=$(( RANDOM % 20 ))
    if   [ "$TIER" -lt 10 ]; then BASE=$(( 2700 + RANDOM % 1800 ))   # 45-75min
    elif [ "$TIER" -lt 17 ]; then BASE=$(( 4500 + RANDOM % 1800 ))   # 75-105min
    else                          BASE=$(( 6300 + RANDOM % 3600 ))  # 105-165min
    fi
    echo $(( BASE + RANDOM % 47 ))
}

mkdir -p logs

while true; do
    SESSION=$(( SESSION + 1 ))
    if [ "$RECORD_EVERY" -gt 0 ] && [ $(( SESSION % RECORD_EVERY )) -eq 0 ]; then
        MODE="--record-only"; KIND=record
    else
        MODE="--smart-only"; KIND=smart
    fi
    LOG="logs/session_${KIND}_$(date +%Y%m%d_%H%M%S).log"

    # A reboot or OS reset can wipe ~/Library/Caches/ms-playwright (2026-09-22),
    # and a playwright upgrade can need a newer build. Idempotent; no-op when current.
    python3 -m playwright install chromium >> "$LOG" 2>&1 || true

    caffeinate -is python3 main.py "$MODE" --sort-by-relationship --background --max "$MAX_MATCHES" --scroll 8 --verbose >> "$LOG" 2>&1
    EXIT=$?

    # Notifies (macOS) only on NEW VIP hits; conflict_review.py rebuilds the manual
    # review queue in data/conflict_review.md.
    python3 notify_vip.py --notify >> "$LOG" 2>&1
    python3 conflict_review.py >> "$LOG" 2>&1

    if grep -qi "(captcha)\|Incapsula" "$LOG" 2>/dev/null; then
        PAUSE=21600
        echo "[runner] captcha/WAF block detected -- sleeping ${PAUSE}s" >> "$LOG"
    elif [ "$EXIT" -ne 0 ]; then
        PAUSE=300
        echo "[runner] crash (exit $EXIT) -- sleeping ${PAUSE}s" >> "$LOG"
    else
        PAUSE=$(rand_pause)
        echo "[runner] clean exit -- sleeping ${PAUSE}s" >> "$LOG"
    fi

    caffeinate -is sleep "$PAUSE"
done
