from datetime import datetime, timedelta

from notify_health import classify, decide

T0 = datetime(2026, 11, 8, 16, 48)


def test_classify():
    assert classify("ERROR | Bot challenge instead of the matches list (captcha): x") == "captcha"
    assert classify("Auth failed. Run: python main.py --capture-session") == "auth"
    assert classify("INFO | Found 240 people | top: X") == "ok"
    assert classify("INFO | Found 0 people") is None
    assert classify("TimeoutError: Page.goto: Timeout 45000ms exceeded.") is None


def test_first_failure_notifies_then_quiet_then_reminds():
    s, k = decide({}, "captcha", T0)
    assert k == "captcha"
    s, k = decide(s, "captcha", T0 + timedelta(hours=6))
    assert k is None
    s, k = decide(s, "captcha", T0 + timedelta(hours=24))
    assert k == "captcha"


def test_switch_and_recovery():
    s, _ = decide({}, "captcha", T0)
    s, k = decide(s, "auth", T0 + timedelta(hours=1))
    assert k == "auth"
    s, k = decide(s, None, T0 + timedelta(hours=2))
    assert k is None and s["status"] == "auth"
    s, k = decide(s, "ok", T0 + timedelta(hours=3))
    assert k == "ok"
    s, k = decide(s, "ok", T0 + timedelta(hours=4))
    assert k is None
