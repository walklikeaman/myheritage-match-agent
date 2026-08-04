"""
Bulk confirm-by-source-tree for MyHeritage Smart Matches.

Confirms ALL pending matches against one external "source" tree in a single action
(the "Совпадения по источнику" -> "Дополнительные действия" -> "Подтвердить все N
совпадения" UI flow), instead of clicking through each match individually. This
registers the match links only -- it does NOT extract/save any field data, since
confirming and saving are separate steps on MyHeritage (see
wiki/entities/smart-matches.md). Use --extract-confirmed separately to enrich
specific people afterward.

Per Nikita 2026-08-03: for very distant/collateral matches, the accuracy risk of
skipping per-match review is acceptable, and this path did NOT trigger the
reCAPTCHA/Incapsula WAF challenge in live testing (2026-08-02, two source trees,
~2100+ confirms, zero challenges -- see wiki/log.md). The confirm request itself
often returns a 504 Gateway Timeout because MyHeritage's server can't finish
thousands of confirms within one HTTP request window, but processing continues
server-side regardless -- a 504 here is expected, not a failure.
"""

import asyncio
import random

from loguru import logger
from playwright.async_api import Page

from config import BASE_URL
from browser.smart_matches import _IS_BOT_CHALLENGE

TREE_ID = "OYYV6BL4NPB77IAKQQ65RX6Q4GAV5KA"
SOURCES_URL = f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-by-source?lang=RU"

_EXTRACT_SOURCES = """
() => {
    // Multiple <a> wrap one card (image, title, button) sharing the same href — only
    // the "Просмотрите N совпадения(-й)" button anchor carries a digit, so anchors
    // without one (image/title wrappers) must be skipped rather than counted as 0.
    // Only individual family-site trees ("tree-..." hrefs) exposed the bulk-confirm
    // dropdown in testing — the large aggregator collections (Filae, Geni World,
    // FamilySearch, GenealogieOnline catalog: "collection-..." hrefs) did not, so
    // those are filtered out here rather than failing per-source at confirm time.
    const links = [...document.querySelectorAll('a[href*="matches-for-source/tree-"]')];
    const byHref = new Map();
    for (const a of links) {
        const text = a.textContent.trim();
        const m = text.match(/(\\d+)/);
        if (!m) continue;
        const count = parseInt(m[1], 10);
        if (!byHref.has(a.href) || count > byHref.get(a.href)) {
            byHref.set(a.href, count);
        }
    }
    return [...byHref.entries()].map(([href, count]) => ({href, count}));
}
"""


async def _sleep(lo: float, hi: float) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


async def get_source_trees(page: Page, scroll_rounds: int = 8) -> list[dict]:
    """Scrape the matches-by-source list with infinite-scroll, sorted by pending count desc."""
    await page.goto(SOURCES_URL, wait_until="networkidle", timeout=60000)
    await _sleep(8, 12)

    seen_hrefs: set[str] = set()
    all_sources: list[dict] = []

    for round_n in range(scroll_rounds):
        batch = await page.evaluate(_EXTRACT_SOURCES)
        new = [s for s in batch if s["href"] not in seen_hrefs]
        for s in new:
            seen_hrefs.add(s["href"])
            all_sources.append(s)

        if not new and round_n > 0:
            logger.debug(f"  Scroll {round_n}: no new sources — stopping scroll")
            break

        logger.debug(f"  Scroll {round_n}: +{len(new)} sources (total {len(all_sources)})")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await _sleep(3, 5)

    all_sources.sort(key=lambda s: s["count"], reverse=True)
    return all_sources


async def confirm_all_for_source(page: Page, source: dict) -> dict:
    """
    Navigate to one source tree's detail page and click through
    "Дополнительные действия" -> "Подтвердить все N совпадения(-й)" -> confirm modal.
    Returns {"href", "reported_count", "status": "ok"|"skip"|"error"}.
    """
    result = {"href": source["href"], "reported_count": source["count"], "status": "error"}
    url = source["href"] if "lang=RU" in source["href"] else source["href"] + "&lang=RU"

    try:
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await _sleep(6, 9)
    except Exception as e:
        logger.error(f"  Navigation failed: {e}")
        return result

    # This endpoint has never shown the reCAPTCHA/Incapsula challenge in testing
    # (2026-08-02 through 2026-08-05), but the per-match flow looked safe for months
    # before it didn't — check anyway rather than assume, and use "blocked" (not
    # "skip") so the runner's captcha grep and backoff pick it up correctly if this
    # ever changes.
    if await page.evaluate(_IS_BOT_CHALLENGE):
        logger.error("  reCAPTCHA/Incapsula challenge on source page (captcha) — unexpected here, blocking session")
        result["status"] = "blocked"
        return result

    # Real Playwright locator clicks (auto-waits for visibility/actionability) — the
    # dropdown items here are plain Angular-bound divs, not <button>/<a>, and did not
    # respond reliably to a simulated triggerHandler('click') the way the wizard's
    # buttons do. A genuine pointer-event click is what actually opens/advances this UI.
    try:
        await page.get_by_text("Дополнительные действия", exact=False).first.click(timeout=15000)
    except Exception as e:
        logger.warning(f"  'Дополнительные действия' not clickable — skipping ({e})")
        result["status"] = "skip"
        return result
    await _sleep(1.5, 2.5)

    try:
        await page.get_by_text("Подтвердить все", exact=False).first.click(timeout=15000)
    except Exception as e:
        logger.warning(f"  'Подтвердить все' menu item not clickable — skipping ({e})")
        result["status"] = "skip"
        return result
    await _sleep(2, 3)

    # Modal's confirm button — exact text "Подтвердить совпадения" (no dynamic count),
    # distinct from the dropdown item's "Подтвердить все N совпадения(-й)".
    try:
        await page.get_by_role("button", name="Подтвердить совпадения").click(timeout=15000)
    except Exception as e:
        logger.warning(f"  Confirm-modal button not clickable — skipping ({e})")
        result["status"] = "skip"
        return result

    # The request commonly 504s server-side after thousands of confirms, but keeps
    # processing regardless (see module docstring) — just give it time to be sent,
    # don't wait for a response before moving on.
    await _sleep(8, 12)
    result["status"] = "ok"
    return result


async def run_bulk_source_confirm_session(page: Page, max_sources: int = 5) -> dict:
    """Confirm all pending matches for the top `max_sources` source trees by pending count."""
    summary = {"sources_processed": 0, "ok": 0, "skip": 0, "error": 0, "total_reported": 0}

    logger.info("Loading Совпадения по источнику (sorted by pending count)…")
    sources = await get_source_trees(page)
    logger.info(f"Found {len(sources)} source trees" if sources else "Found 0 source trees")

    for source in sources[:max_sources]:
        logger.info(f"\n{'='*60}\n{source['href'].split('matches-for-source/')[-1][:60]} (~{source['count']} pending)")
        result = await confirm_all_for_source(page, source)
        summary["sources_processed"] += 1
        summary[result["status"]] = summary.get(result["status"], 0) + 1
        logger.info(f"  {result['status'].upper()} (~{result['reported_count']} matches)")
        if result["status"] == "blocked":
            summary["aborted"] = "captcha"
            logger.error(f"reCAPTCHA challenge (captcha) — aborting session after {summary['sources_processed']} sources to back off")
            return summary
        if result["status"] == "ok":
            summary["total_reported"] += result["reported_count"]
        await _sleep(15, 30)

    return summary
