"""
Record Match (matchType=1) automation for MyHeritage.

Flow per match (no wizard — all on one compare page):
  1. Navigate to match-compare page
  2. Click "Подтвердить совпадение" via AngularJS triggerHandler
  3. Wait for in-page update (no navigation)
  4. Click "Сохранить в Вашем дереве" — saves all new facts + relatives
  5. Confirm success ("подтверждено" text appears)

Key difference from Smart Matches:
  - matchType=1 in URLs
  - No separate wizard page
  - A single "Сохранить в Вашем дереве" button saves everything
  - NEW RELATIVES are added from НОВАЯ ИНФОРМАЦИЯ sections
"""

import asyncio
import random
from loguru import logger
from playwright.async_api import Page, TimeoutError as PWTimeoutError

from config import (
    BASE_URL,
    ACTION_DELAY_MIN,
    ACTION_DELAY_MAX,
    MATCH_DELAY_MIN,
    MATCH_DELAY_MAX,
)

TREE_ID = "OYYV6BL4NPB77IAKQQ65RX6Q4GAV5KA"
RECORD_MATCHES_URL = (
    f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-by-people"
    "?matchType=1&matchStatus=32&lang=RU"
)

_IS_CONFIRMED = "() => document.body.innerText.includes('подтверждено')"


async def _sleep(lo: float, hi: float) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


async def _angular_click(page: Page, selector: str) -> str:
    """Click an element via AngularJS triggerHandler. Returns 'OK' | 'NOT_FOUND' | 'ERR:...'"""
    return await page.evaluate("""
    (selector) => {
        let el;
        if (selector.startsWith('text:')) {
            const text = selector.slice(5);
            el = [...document.querySelectorAll('a.mh_button,button.mh_button,.mh_button,a,button')]
                    .find(e => e.textContent.trim().startsWith(text));
        } else {
            el = document.querySelector(selector);
        }
        if (!el) return 'NOT_FOUND';
        try {
            window.angular.element(el).triggerHandler('click');
            return 'OK';
        } catch(e) {
            return 'ERR:' + e.message;
        }
    }
    """, selector)


async def _count_new_info(page: Page) -> dict:
    """Count new facts and relatives marked НОВАЯ ИНФОРМАЦИЯ."""
    return await page.evaluate("""
    () => {
        const bodyText = document.body.innerText;
        const newInfoCount = (bodyText.match(/НОВАЯ ИНФОРМАЦИЯ/g) || []).length;
        // Relatives are in the body too
        const relativeTerms = (bodyText.match(/Его (отец|мать|сын|дочь|жена|муж|брат|сестра)/g) || []).length;
        const photos = document.querySelectorAll('[ng-click*="uploadPhoto"]').length;
        return {newInfoCount, relativeTerms, photos};
    }
    """)


async def process_one_record_match(page: Page, match_url: str) -> dict:
    """
    Process a single Record Match compare URL end-to-end.
    Returns {"status": "ok"|"skip"|"error", "new_info": int, "url": str}
    """
    result = {"url": match_url, "status": "error", "new_info": 0}
    lang_url = match_url if "lang=RU" in match_url else match_url + "?lang=RU"

    # --- Load compare page ---
    try:
        logger.info(f"→ {lang_url.split('match-compare/')[-1][:60]}")
        await page.goto(lang_url, wait_until="networkidle", timeout=45000)
        await _sleep(4, 6)
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        return result

    # Already confirmed?
    if await page.evaluate(_IS_CONFIRMED):
        logger.info("  Already confirmed — skipping")
        result["status"] = "skip"
        return result

    # Count what's new
    counts = await _count_new_info(page)
    logger.info(
        f"  New info: {counts['newInfoCount']} fields, "
        f"{counts['relativeTerms']} relative refs, "
        f"{counts['photos']} photos"
    )
    result["new_info"] = counts["newInfoCount"]

    # --- Step 1: Click confirm button ---
    res = await _angular_click(page, "text:Подтвердить совпадение")
    if res == "NOT_FOUND":
        logger.warning("  Confirm button not found")
        result["status"] = "skip"
        return result
    logger.debug(f"  Confirm click: {res}")
    await _sleep(3, 5)

    # --- Step 2: Click save button (stays on same page) ---
    # Try primary text match first, then fallback to class-based search
    save_res = await _angular_click(page, "text:Сохранить в Вашем дереве")
    if save_res == "NOT_FOUND":
        # Fallback: look for mh_button_type_inverse (the save action button style)
        save_res = await page.evaluate("""
        () => {
            const el = document.querySelector('.mh_button_type_inverse,[class*="save"],[ng-click*="invokeAction"]');
            if (!el) return 'NOT_FOUND';
            try { window.angular.element(el).triggerHandler('click'); return 'OK_fallback'; }
            catch(e) { return 'ERR:' + e.message; }
        }
        """)
    logger.debug(f"  Save click: {save_res}")

    if save_res.startswith("NOT_FOUND"):
        logger.warning("  Save button not found")
        result["status"] = "error"
        return result

    # --- Wait for confirmation ---
    await _sleep(4, 7)
    confirmed = await page.evaluate(_IS_CONFIRMED)

    if not confirmed:
        # Sometimes takes longer — wait more
        await _sleep(8, 12)
        confirmed = await page.evaluate(_IS_CONFIRMED)

    if confirmed:
        logger.info(f"  ✓ Saved — {counts['newInfoCount']} new info fields")
        result["status"] = "ok"
    else:
        logger.warning("  No 'подтверждено' after save — may have failed")
        result["status"] = "error"

    return result


async def get_record_match_urls(page: Page, person_id: str) -> list[str]:
    """Return all pending Record Match compare URLs for a person."""
    url = (
        f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-for-person/{person_id}"
        "?matchType=1&matchStatus=32&lang=RU"
    )
    await page.goto(url, wait_until="networkidle", timeout=45000)
    await _sleep(4, 6)

    urls = await page.evaluate("""
        () => [...new Set(
            [...document.querySelectorAll('a[href*="match-compare"]')]
            .map(a => a.href)
        )]
    """)
    return urls


async def get_people_with_record_matches(page: Page) -> list[dict]:
    """Scrape matches-by-people for Record Matches and return [{id, name}]."""
    await page.goto(RECORD_MATCHES_URL, wait_until="networkidle", timeout=45000)
    await _sleep(4, 6)

    people = await page.evaluate("""
        () => {
            const seen = new Set();
            return [...document.querySelectorAll('a[href*="matches-for-person"]')]
                .map(a => {
                    const m = a.href.match(/matches-for-person\\/([^?]+)/);
                    if (!m || seen.has(m[1])) return null;
                    seen.add(m[1]);
                    const nameEl = a.querySelector('[class*="name"],[class*="title"]') || a;
                    return {id: m[1], name: nameEl.textContent.trim().substring(0, 60)};
                })
                .filter(Boolean);
        }
    """)
    return people


async def run_record_matches_session(
    page: Page,
    max_matches: int = 200,
    start_person_index: int = 0,
) -> dict:
    """
    Main session loop for Record Matches.
    Returns summary dict.
    """
    summary = {"processed": 0, "ok": 0, "skip": 0, "error": 0, "people": 0}

    logger.info("Loading Record Matches by-people list…")
    people = await get_people_with_record_matches(page)
    logger.info(f"Found {len(people)} people with pending Record Matches")

    for person in people[start_person_index:]:
        if summary["processed"] >= max_matches:
            logger.info(f"Reached session cap ({max_matches}) — stopping")
            break

        logger.info(f"\n{'='*60}\n{person['name']} (ID: {person['id']})")
        match_urls = await get_record_match_urls(page, person["id"])
        logger.info(f"  {len(match_urls)} pending matches")

        for i, url in enumerate(match_urls):
            if summary["processed"] >= max_matches:
                break

            result = await process_one_record_match(page, url)
            status = result["status"]
            summary["processed"] += 1
            summary[status] = summary.get(status, 0) + 1

            logger.info(
                f"  [{i+1}/{len(match_urls)}] {status.upper()} "
                f"({result['new_info']} new fields) | total: {summary['processed']}"
            )

            if i < len(match_urls) - 1:
                await _sleep(MATCH_DELAY_MIN, MATCH_DELAY_MAX)

        summary["people"] += 1
        await _sleep(ACTION_DELAY_MIN, ACTION_DELAY_MAX)

    return summary
