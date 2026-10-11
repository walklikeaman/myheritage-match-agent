#!/bin/bash
# Standing runner for `main.py --smart-only --sort-by-relationship`.
# Started at login by launchd (scripts/com.walklikeaman.myheritage-runner.plist);
# see wiki/log.md 2026-10-12. Runs --visible: headless is blocked by the WAF.
cd "$(dirname "$0")/.." || exit 1
MAX_MATCHES=100

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
    LOG="logs/session_smart_$(date +%Y%m%d_%H%M%S).log"

    # A reboot or OS reset can wipe ~/Library/Caches/ms-playwright (2026-09-22),
    # and a playwright upgrade can need a newer build. Idempotent; no-op when current.
    python3 -m playwright install chromium >> "$LOG" 2>&1 || true

    caffeinate -i python3 main.py --smart-only --sort-by-relationship --background --max "$MAX_MATCHES" --scroll 8 --verbose >> "$LOG" 2>&1
    EXIT=$?

    python3 notify_vip.py >> "$LOG" 2>&1

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

    caffeinate -i sleep "$PAUSE"
done
