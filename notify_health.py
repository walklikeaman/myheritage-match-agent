"""
Raise a macOS notification when a runner session could not work: the login
failed (session expired, password changed, no network) or MyHeritage showed a
bot challenge (hCaptcha / Incapsula) instead of the matches list.

Why: before 2026-11-09 only new VIP hits raised a notification. Two hCaptcha
streaks (2026-10-22..11-03 and from 2026-11-08 16:48) ran for days with 0 saves
and nobody knew.

Usage (from scripts/mh_runner_smart.sh, after each session):
    python3 notify_health.py <session-log>

State lives in data/runner_health.json, so one problem gives one notification,
then one reminder every REMIND_HOURS while it lasts, and one "works again"
notification when a session gets past the check.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

STATE_FILE = Path("data/runner_health.json")
REMIND_HOURS = 24
RELOGIN_CMD = 'cd ~/GitHub/"My Heritage" && .venv/bin/python3 main.py --capture-session'

AUTH_PATTERNS = [r"Auth failed", r"No auth found"]
CAPTCHA_PATTERNS = [r"Bot challenge", r"\(captcha\)", r"Incapsula"]
OK_PATTERNS = [r"Found [1-9]\d* people"]

MESSAGES = {
    "auth": ("MyHeritage: логин не прошёл",
             "Сессия протухла (или нет сети). Перелогинься: --capture-session"),
    "captcha": ("MyHeritage: hCaptcha",
                "Раннер упёрся в капчу и не работает. Помогает свежий логин: --capture-session"),
    "ok": ("MyHeritage: снова работает", "Раннер прошёл проверку и обрабатывает совпадения."),
}


def classify(text: str) -> str | None:
    """'auth', 'captcha', 'ok', or None when the log says nothing either way (e.g. a timeout crash)."""
    if any(re.search(p, text) for p in AUTH_PATTERNS):
        return "auth"
    if any(re.search(p, text) for p in CAPTCHA_PATTERNS):
        return "captcha"
    if any(re.search(p, text) for p in OK_PATTERNS):
        return "ok"
    return None


def decide(state: dict, status: str | None, now: datetime) -> tuple[dict, str | None]:
    """Return (new_state, kind_to_notify_or_None)."""
    prev = state.get("status", "ok")
    if status is None:
        return state, None
    if status == "ok":
        new = {"status": "ok", "since": now.isoformat()} if prev != "ok" else state
        return new, ("ok" if prev != "ok" else None)
    if status != prev:
        return {"status": status, "since": now.isoformat(), "notified": now.isoformat()}, status
    last = datetime.fromisoformat(state.get("notified", state.get("since", now.isoformat())))
    if now - last >= timedelta(hours=REMIND_HOURS):
        return {**state, "notified": now.isoformat()}, status
    return state, None


def notify(kind: str, since: str | None) -> None:
    title, body = MESSAGES[kind]
    if kind != "ok" and since:
        body = f"{body} (с {since[:16].replace('T', ' ')})"
    subprocess.run(["osascript", "-e",
                    f'display notification "{body}" with title "{title}" sound name "Basso"'],
                   check=False)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: notify_health.py <session-log>")
        return 2
    text = Path(sys.argv[1]).read_text(errors="replace")
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    new_state, kind = decide(state, classify(text), datetime.now())
    if new_state != state:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(new_state, ensure_ascii=False, indent=1))
    if kind:
        notify(kind, new_state.get("since"))
        print(f"[health] notified: {kind}")
        if kind != "ok":
            print(f"[health] relogin: {RELOGIN_CMD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
