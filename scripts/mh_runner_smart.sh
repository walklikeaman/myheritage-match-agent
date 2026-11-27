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
# Smart sessions also read the MyHeritage inbox at the end (read only, at most
# INBOX_MAX_THREADS threads; Nikita 2026-11-27, see wiki/concepts/inbox.md). 0 = off.
INBOX=1
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
    EXTRA=""
    if [ "$INBOX" -eq 1 ] && [ "$KIND" = smart ]; then EXTRA="--inbox"; fi
    LOG="logs/session_${KIND}_$(date +%Y%m%d_%H%M%S).log"

    # A reboot or OS reset can wipe ~/Library/Caches/ms-playwright (2026-09-22),
    # and a playwright upgrade can need a newer build. Idempotent; no-op when current.
    python3 -m playwright install chromium >> "$LOG" 2>&1 || true

    caffeinate -is python3 main.py "$MODE" --sort-by-relationship --background --max "$MAX_MATCHES" --scroll 8 --verbose $EXTRA >> "$LOG" 2>&1
    EXIT=$?

    # Notifies (macOS) only on NEW VIP hits; conflict_review.py rebuilds the manual
    # review queue in data/conflict_review.md.
    python3 notify_vip.py --notify >> "$LOG" 2>&1
    # Notifies (macOS) when the login failed or a captcha blocked the session, once per
    # problem + a daily reminder + "works again" (2026-11-09: two silent hCaptcha streaks).
    python3 notify_health.py "$LOG" >> "$LOG" 2>&1
    python3 conflict_review.py >> "$LOG" 2>&1
    # Sorts data/inbox.jsonl into data/inbox_review.md with draft replies; notifies (macOS)
    # only when a new letter needs Nikita (a kinship question, a person, a VIP surname).
    python3 inbox_triage.py --notify >> "$LOG" 2>&1
    # Fold captured relatives into data/family_graph.json, then publish the graph and the
    # person index to the NAS (Archive/Родословная/граф), see nas_export.py.
    python3 graph_accumulate.py >> "$LOG" 2>&1
    python3 nas_export.py >> "$LOG" 2>&1 || echo "[runner] NAS export failed (NAS offline?)" >> "$LOG"

    # 2026-11-28: the family-sites "?popup=4" redirect is MyHeritage's "Доступ был временно
    # отключен ... повторите через 24 часа" rate-limit block, not a captcha. A 6 h pause
    # kept hitting it (2026-11-25..28), so wait a full day.
    if grep -q "popup=4" "$LOG" 2>/dev/null; then
        PAUSE=90000
        echo "[runner] MyHeritage 24 h activity block (popup=4) -- sleeping ${PAUSE}s" >> "$LOG"
    elif grep -qi "(captcha)\|Incapsula" "$LOG" 2>/dev/null; then
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
