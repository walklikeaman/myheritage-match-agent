#!/bin/bash
# Автоматически запускает сессии одна за другой до исчерпания совпадений.
# Использование: bash run_sessions.sh [max_per_session] [scroll_rounds]
# Пример: bash run_sessions.sh 200 20

MAX=${1:-200}
SCROLL=${2:-20}
SESSION=1

while true; do
    LOG="logs/session_auto_$(date +%Y%m%d_%H%M%S)_s${SESSION}.log"
    echo "[$(date)] Запуск сессии #${SESSION} (max=${MAX}, scroll=${SCROLL}) → ${LOG}"

    python3 main.py --max "$MAX" --scroll "$SCROLL" --verbose > "$LOG" 2>&1
    EXIT=$?

    echo "[$(date)] Сессия #${SESSION} завершена (exit=$EXIT)"
    tail -15 "$LOG"

    # Если нет совпадений — стоп
    if grep -q "Found 0 people" "$LOG" 2>/dev/null; then
        echo "[$(date)] Все совпадения обработаны — останавливаемся."
        break
    fi

    # Пауза между сессиями (120-180s) перед следующей
    PAUSE=$(( RANDOM % 60 + 120 ))
    echo "[$(date)] Пауза ${PAUSE}s перед следующей сессией…"
    sleep "$PAUSE"

    SESSION=$(( SESSION + 1 ))
done
