"""
Read-only pass over the MyHeritage inbox (messages from other members).

Why (Nikita, 2026-11-27): relatives write to him after Smart Matches are confirmed,
asking how the trees connect. He has no time to read them all. Stage 1 only READS:
it saves each message to data/inbox.jsonl (deduplicated) so inbox_triage.py can sort
them and prepare drafts. Nothing is ever sent from here (docs/RULES.md §3.1, §3.10).

Runs inside the same browser session as the matches run (main.py --inbox), after the
matches loop, only when that loop was not blocked. One list page plus at most
INBOX_MAX_THREADS thread pages per session, with human-like pauses.

Selectors are NOT verified yet (no live recon before 2026-11-27). The list parser is
deliberately generic (links whose href points into the inbox), and every run whose
parse finds nothing, or a run with recon=True, saves the page HTML, text and the JSON
responses the page loaded to recon/inbox/ (git-ignored) so the selectors can be fixed
from a real page. See wiki/concepts/inbox.md and wiki/concepts/selectors.md "Inbox".

Side effect to know about: opening a thread on MyHeritage usually marks it as read.
"""

import asyncio
import hashlib
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PWTimeoutError

from browser.smart_matches import _IS_BOT_CHALLENGE
from config import BASE_DIR, BASE_URL, INBOX_FILE, INBOX_MAX_THREADS

INBOX_URL = f"{BASE_URL}/inbox?lang=RU"
RECON_DIR = BASE_DIR / "recon" / "inbox"

# Generic thread-list parser: every link that points into the inbox and is not the
# inbox root itself or a folder tab. Returns href + the visible row text around it.
_EXTRACT_THREADS = r"""
() => {
    const out = [], seen = new Set();
    const folder = /[?&](folder|tab|filter)=|\/(sent|trash|archive|drafts)(\b|\/)/i;
    for (const a of document.querySelectorAll('a[href]')) {
        const href = a.href || '';
        if (!/myheritage\.[a-z.]+\/(inbox|mail|messages?|conversation)/i.test(href)) continue;
        if (/\/inbox\/?(\?|#|$)/i.test(href) || folder.test(href)) continue;
        if (seen.has(href)) continue;
        seen.add(href);
        let row = a;
        for (let i = 0; i < 4 && row.parentElement; i++) {
            if ((row.innerText || '').length > 40) break;
            row = row.parentElement;
        }
        const text = (row.innerText || a.innerText || '').trim().slice(0, 600);
        const unread = /unread|new|bold/i.test(row.className || '') ||
                       !!row.querySelector('[class*="unread"], [class*="Unread"]');
        out.push({href, text, unread});
    }
    return out;
}
"""

# The thread page: take the main content, falling back to the body.
_THREAD_TEXT = r"""
() => {
    const main = document.querySelector('main, [role="main"], #content, .content') || document.body;
    return (main.innerText || '').trim().slice(0, 20000);
}
"""

_THREAD_ID_RE = re.compile(r"(?:thread|conversation|message|mail)[^0-9A-Za-z]*(?:id=)?([0-9A-Za-z_-]{4,})", re.IGNORECASE)


def thread_key(href: str) -> str:
    """Stable id for a thread: the id in its URL, else a hash of the URL without query noise."""
    m = _THREAD_ID_RE.search(href)
    if m:
        return m.group(1)
    base = re.sub(r"[?&](lang|utm_[a-z]+)=[^&#]*", "", href)
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def text_hash(text: str) -> str:
    return hashlib.sha1(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()[:16]


def load_seen(path: Path = INBOX_FILE) -> dict[str, str]:
    """thread_key -> text hash of the last saved version of that thread."""
    seen: dict[str, str] = {}
    if not path.exists():
        return seen
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        seen[rec["thread"]] = rec["hash"]
    return seen


def pick_threads(threads: list[dict], seen: dict[str, str], limit: int) -> list[dict]:
    """New or changed threads first (preview text differs from what we saved), unread first."""
    fresh = []
    for t in threads:
        key = thread_key(t["href"])
        if key in seen and seen[key] == t.get("preview_hash"):
            continue
        fresh.append({**t, "thread": key})
    fresh.sort(key=lambda t: not t.get("unread"))
    return fresh[:limit]


def _append(rec: dict, path: Path = INBOX_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


async def _save_recon(page: Page, tag: str, responses: list[dict]) -> None:
    RECON_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005 (local file names)
    (RECON_DIR / f"{stamp}_{tag}.html").write_text(await page.content(), encoding="utf-8")
    (RECON_DIR / f"{stamp}_{tag}.txt").write_text(
        f"{page.url}\n\n" + await page.evaluate("() => document.body.innerText || ''"), encoding="utf-8")
    if responses:
        (RECON_DIR / f"{stamp}_{tag}_xhr.json").write_text(
            json.dumps(responses, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info(f"  [inbox] recon saved to {RECON_DIR}/{stamp}_{tag}.*")


async def _sleep(lo: float, hi: float) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


async def run_inbox_session(page: Page, max_threads: int = INBOX_MAX_THREADS, recon: bool = False) -> dict:
    """Read new inbox threads into data/inbox.jsonl. Never writes anything on MyHeritage."""
    summary = {"threads_listed": 0, "threads_read": 0, "new_messages": 0, "aborted": None}
    responses: list[dict] = []

    async def _on_response(resp) -> None:
        if len(responses) >= 40 or not re.search(r"inbox|mail|message|conversation|thread", resp.url, re.IGNORECASE):
            return
        if "json" not in (resp.headers.get("content-type") or ""):
            return
        try:
            responses.append({"url": resp.url, "body": (await resp.text())[:50000]})
        except Exception as e:  # noqa: BLE001 (best effort, recon only)
            logger.debug(f"  [inbox] could not read response body: {e!r}")

    page.on("response", _on_response)
    try:
        logger.info("[inbox] Opening the MyHeritage inbox (read only)…")
        try:
            await page.goto(INBOX_URL, wait_until="domcontentloaded", timeout=45000)
        except PWTimeoutError:
            logger.warning("[inbox] inbox page did not load in 45 s — skipping this session")
            summary["aborted"] = "timeout"
            return summary
        await _sleep(8, 12)

        if await page.evaluate(_IS_BOT_CHALLENGE):
            # Same token the runner greps for: it then pauses 6 h (docs/RULES.md §3.3).
            logger.error(f"[inbox] Bot challenge on the inbox (captcha): {page.url}")
            summary["aborted"] = "captcha"
            return summary
        if not re.search(r"inbox|mail|message", page.url, re.IGNORECASE):
            logger.warning(f"[inbox] inbox redirected to {page.url} — saving recon, reading nothing")
            await _save_recon(page, "redirect", responses)
            summary["aborted"] = "redirect"
            return summary

        threads = await page.evaluate(_EXTRACT_THREADS)
        for t in threads:
            t["preview_hash"] = text_hash(t["text"])
        summary["threads_listed"] = len(threads)
        logger.info(f"[inbox] {len(threads)} thread link(s) on the list page")
        if recon or not threads:
            await _save_recon(page, "list", responses)
        if not threads:
            return summary

        seen = load_seen()
        todo = pick_threads(threads, seen, max_threads)
        logger.info(f"[inbox] {len(todo)} new or changed thread(s) to read (cap {max_threads})")

        for i, t in enumerate(todo):
            await _sleep(8, 18)
            try:
                await page.goto(t["href"], wait_until="domcontentloaded", timeout=45000)
            except PWTimeoutError:
                logger.warning(f"[inbox] thread did not load: {t['href']}")
                continue
            await _sleep(4, 7)
            if await page.evaluate(_IS_BOT_CHALLENGE):
                logger.error(f"[inbox] Bot challenge on a thread page (captcha): {page.url}")
                summary["aborted"] = "captcha"
                break
            body = await page.evaluate(_THREAD_TEXT)
            if recon and i == 0:
                await _save_recon(page, "thread", responses)
            summary["threads_read"] += 1
            _append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "thread": t["thread"],
                "url": t["href"],
                "unread": bool(t.get("unread")),
                "preview": t["text"],
                # Matches the list preview, so an unchanged thread is skipped next time.
                "hash": t["preview_hash"],
                "text": body,
            })
            summary["new_messages"] += 1
        logger.info(f"[inbox] read {summary['threads_read']} thread(s), saved to {INBOX_FILE}")
        return summary
    finally:
        page.remove_listener("response", _on_response)
