"""
Smart Match automation for MyHeritage.

Flow per match:
  1. Navigate to match-compare page
  2. Click "Подтвердить совпадение" via AngularJS triggerHandler
  3. Page auto-navigates to extract wizard (or we follow the manual link)
  4. Click "Извлечь всю информацию" (or single-field sign fallback)
  5. Click Save — page redirects back to match-compare#rm_ with "подтверждено"
"""

import asyncio
import random
from typing import Optional

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
MATCHES_BY_PEOPLE_URL = (
    f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-by-people"
    "?matchType=2&matchStatus=32&lang=RU"
)


# ---------------------------------------------------------------------------
# AngularJS helpers
# ---------------------------------------------------------------------------

_ANGULAR_CLICK = """
(selector) => {
    let el;
    if (typeof selector === 'string') {
        if (selector.startsWith('text:')) {
            const text = selector.slice(5);
            el = [...document.querySelectorAll('a.mh_button,button.mh_button')]
                    .find(e => e.textContent.trim().startsWith(text));
        } else {
            el = document.querySelector(selector);
        }
    } else {
        el = selector;
    }
    if (!el) return 'NOT_FOUND';
    try {
        window.angular.element(el).triggerHandler('click');
        return 'OK';
    } catch(e) {
        return 'ERR:' + e.message;
    }
}
"""

_FIND_EXTRACT_ALL = """
() => {
    const d = [...document.querySelectorAll('*')]
                .find(e => e.children.length === 0 &&
                           e.textContent.trim() === 'Извлечь всю информацию');
    if (d) return {found: true, className: d.className};
    const s = document.querySelector('[class*="extract_record_row_copied_all_sign"]');
    if (s) return {found: true, single: true, className: s.className};
    return {found: false};
}
"""

_CLICK_EXTRACT_ALL = """
() => {
    // Smart Match wizard: "Извлечь всю информацию"
    const d = [...document.querySelectorAll('*')]
                .find(e => e.children.length === 0 &&
                           e.textContent.trim() === 'Извлечь всю информацию');
    if (d) {
        window.angular.element(d).triggerHandler('click');
        return {clicked: 'all', className: d.className};
    }
    // Single-field sign (Smart Match, 1 field)
    const s = document.querySelector('[class*="extract_record_row_copied_all_sign"]');
    if (s) {
        window.angular.element(s).triggerHandler('click');
        return {clicked: 'single', className: s.className};
    }
    // Record Match wizard: "Сохранить в дерево" (saveAndNavigateTo)
    const rmSave = [...document.querySelectorAll('a,button,[ng-click]')]
        .find(e => e.textContent.trim().startsWith('Сохранить в дерево') ||
                   (e.getAttribute('ng-click')||'').includes('saveAndNavigateTo'));
    if (rmSave) {
        window.angular.element(rmSave).triggerHandler('click');
        return {clicked: 'rm_save', className: rmSave.className};
    }
    return {clicked: null};
}
"""

_CHECK_EXTRACT_SUCCESS = """
() => {
    const d = [...document.querySelectorAll('*')]
                .find(e => e.children.length === 0 &&
                           e.textContent.trim() === 'Извлечь всю информацию');
    if (d) return d.className.includes('copied_all_from_all_true');
    const s = document.querySelector('[class*="extract_record_row_copied_all_sign"]');
    if (s) return s.className.includes('copied');
    // Record Match wizard: saveAndNavigateTo was already clicked — treat as success
    return true;
}
"""

_FIELD_COUNT = "() => document.querySelectorAll('input[type=\"checkbox\"]').length"

_IS_CONFIRMED = "() => document.body.innerText.includes('подтверждено')"


async def _sleep(lo: float, hi: float) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


# ---------------------------------------------------------------------------
# Core match processing
# ---------------------------------------------------------------------------

async def process_one_match(page: Page, match_url: str) -> dict:
    """
    Process a single match-compare URL end-to-end.
    Returns {"status": "ok"|"skip"|"error", "fields": int, "url": str}
    """
    result = {"url": match_url, "status": "error", "fields": 0}
    lang_url = match_url if "lang=RU" in match_url else match_url + "?lang=RU"

    # --- Step 1: Load compare page ---
    try:
        logger.info(f"→ {lang_url.split('match-compare/')[-1][:60]}")
        await page.goto(lang_url, wait_until="domcontentloaded", timeout=30000)
        await _sleep(4, 6)
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        result["status"] = "error"
        return result

    # Already confirmed?
    if await page.evaluate(_IS_CONFIRMED):
        logger.info("  Already confirmed — skipping")
        result["status"] = "skip"
        return result

    # --- Step 2: Click confirm button ---
    try:
        res = await page.evaluate(_ANGULAR_CLICK, "text:Подтвердить совпадение")
        if res == "NOT_FOUND":
            logger.warning("  Confirm button not found")
            result["status"] = "skip"
            return result
        logger.debug(f"  Confirm click: {res}")
    except Exception as e:
        logger.error(f"  Confirm click error: {e}")
        result["status"] = "error"
        return result

    # Wait for navigation to wizard (auto-redirect) or stay on compare
    await _sleep(7, 10)

    # If page navigated away (exception is swallowed), we're on the wizard
    current_url = page.url
    on_wizard = "showExtractWizard" in current_url

    if not on_wizard:
        # Try to find manual "Извлечь информацию вручную" link
        manual_link = await page.evaluate("""
            () => {
                const a = [...document.querySelectorAll('a')]
                    .find(el => el.textContent.includes('Извлечь информацию вручную'));
                return a ? a.href : null;
            }
        """)
        if manual_link:
            logger.debug("  Following manual wizard link")
            await page.goto(manual_link, wait_until="domcontentloaded", timeout=30000)
            await _sleep(3, 5)
            on_wizard = "showExtractWizard" in page.url

        if not on_wizard:
            # Already confirmed via link-only flow?
            if await page.evaluate(_IS_CONFIRMED):
                result["status"] = "ok"
                result["fields"] = 0
                return result
            logger.warning("  Could not reach wizard")
            result["status"] = "skip"
            return result

    # --- Step 3: Extract all info ---
    await _sleep(2, 4)
    click_res = await page.evaluate(_CLICK_EXTRACT_ALL)
    logger.debug(f"  Extract click: {click_res}")

    if not click_res.get("clicked"):
        logger.warning("  No extract button found on wizard")
        # Try to save anyway (might have 0 fields)
        pass
    else:
        await _sleep(1.5, 3)
        # Check that Angular model updated
        success = await page.evaluate(_CHECK_EXTRACT_SUCCESS)
        if not success and click_res.get("clicked") == "all":
            logger.warning("  Extract-all didn't toggle — retrying once")
            await page.evaluate(_CLICK_EXTRACT_ALL)
            await _sleep(2, 3)

    fields = await page.evaluate(_FIELD_COUNT)
    logger.debug(f"  Fields: {fields}")

    # --- Step 4: Save ---
    save_res = await page.evaluate(
        "(id) => { const b = document.getElementById(id); if(!b) return 'NOT_FOUND';"
        " window.angular.element(b).triggerHandler('click'); return 'OK'; }",
        "saveButton"
    )
    logger.debug(f"  Save click: {save_res}")

    if save_res == "NOT_FOUND":
        logger.error("  saveButton not found")
        result["status"] = "error"
        return result

    # Wait for redirect back to compare page (up to 35s)
    try:
        await page.wait_for_url("**/match-compare/**#rm_*", timeout=35000)
    except PWTimeoutError:
        pass  # Check text fallback below

    await _sleep(2, 4)
    confirmed = await page.evaluate(_IS_CONFIRMED)
    if confirmed:
        logger.info(f"  ✓ Saved — {fields} fields")
        result["status"] = "ok"
        result["fields"] = fields
    else:
        logger.warning("  Save may not have completed (no 'подтверждено' text)")
        result["status"] = "error"

    return result


# ---------------------------------------------------------------------------
# Person-level iteration
# ---------------------------------------------------------------------------

async def get_person_match_urls(page: Page, person_id: str) -> list[str]:
    """Return all pending match-compare URLs for a person."""
    url = (
        f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-for-person/{person_id}"
        "?matchType=2&matchStatus=32&lang=RU"
    )
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await _sleep(4, 6)

    urls = await page.evaluate("""
        () => [...new Set(
            [...document.querySelectorAll('a[href*="match-compare"]')]
            .map(a => a.href)
        )]
    """)
    return urls


async def get_people_with_pending_matches(page: Page) -> list[dict]:
    """
    Scrape the matches-by-people list and return [{id, name, count}].
    Only returns people who still have pending matches (matchStatus=32).
    """
    await page.goto(MATCHES_BY_PEOPLE_URL, wait_until="domcontentloaded", timeout=30000)
    await _sleep(4, 6)

    people = await page.evaluate("""
        () => {
            const rows = [...document.querySelectorAll('[class*="discovery_hub_person_row"],'
                + '[class*="person-row"],[class*="personRow"]')];
            if (rows.length === 0) {
                // Fallback: extract from match-for-person links
                const seen = new Set();
                const links = [...document.querySelectorAll('a[href*="matches-for-person"]')];
                return links
                    .map(a => {
                        const m = a.href.match(/matches-for-person\\/([^?]+)/);
                        if (!m || seen.has(m[1])) return null;
                        seen.add(m[1]);
                        const nameEl = a.querySelector('[class*="name"],[class*="title"]') || a;
                        return {id: m[1], name: nameEl.textContent.trim(), count: 0};
                    })
                    .filter(Boolean);
            }
            return rows.map(row => {
                const linkEl = row.querySelector('a[href*="matches-for-person"]');
                if (!linkEl) return null;
                const m = linkEl.href.match(/matches-for-person\\/([^?]+)/);
                if (!m) return null;
                const nameEl = row.querySelector('[class*="name"],[class*="fullname"]') || linkEl;
                const countEl = row.querySelector('[class*="count"],[class*="badge"]');
                return {
                    id: m[1],
                    name: nameEl.textContent.trim().substring(0,60),
                    count: countEl ? parseInt(countEl.textContent) || 0 : 0,
                };
            }).filter(Boolean);
        }
    """)
    return people


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------

async def run_smart_matches_session(
    page: Page,
    max_matches: int = 200,
    start_person_index: int = 0,
) -> dict:
    """
    Main session loop. Processes people → matches until max_matches reached.
    Returns summary dict.
    """
    summary = {"processed": 0, "ok": 0, "skip": 0, "error": 0, "people": 0}

    logger.info("Loading matches-by-people list…")
    people = await get_people_with_pending_matches(page)
    logger.info(f"Found {len(people)} people with pending matches")

    for person in people[start_person_index:]:
        if summary["processed"] >= max_matches:
            logger.info(f"Reached session cap ({max_matches} matches) — stopping")
            break

        person_id = person["id"]
        person_name = person["name"]
        logger.info(f"\n{'='*60}\n{person_name} (ID: {person_id})")

        match_urls = await get_person_match_urls(page, person_id)
        logger.info(f"  {len(match_urls)} pending matches")

        for i, url in enumerate(match_urls):
            if summary["processed"] >= max_matches:
                break

            result = await process_one_match(page, url)
            status = result["status"]
            summary["processed"] += 1
            summary[status] = summary.get(status, 0) + 1

            logger.info(
                f"  [{i+1}/{len(match_urls)}] {status.upper()} "
                f"({result['fields']} fields) | session total: {summary['processed']}"
            )

            # Inter-match delay
            if i < len(match_urls) - 1:
                await _sleep(MATCH_DELAY_MIN, MATCH_DELAY_MAX)

        summary["people"] += 1
        # Between people: short breath
        await _sleep(ACTION_DELAY_MIN, ACTION_DELAY_MAX)

    return summary
