"""
Record Match (matchType=4) automation for MyHeritage.

Record Matches have no match-compare page. The "Просмотреть совпадение" button on a
matches-for-person page opens a record viewer (action=showRecord) with the same Angular
"Подтвердить совпадение" button; confirming leads to showExtractWizard. The record wizard
has no checkboxes (editable rows + a pre-selected source citation) and saves via
saveButton. process_one_match() in smart_matches handles both pages; see
wiki/concepts/selectors.md "Record viewer + record wizard".
"""

import asyncio
import random

from playwright.async_api import Page

from browser.smart_matches import run_smart_matches_session  # shared session loop
from config import BASE_URL

TREE_ID = "OYYV6BL4NPB77IAKQQ65RX6Q4GAV5KA"
RECORD_MATCHES_URL = (
    f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-by-people"
    "?matchType=4&matchStatus=32&lang=RU"
)


async def _sleep(lo: float, hi: float) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


async def get_record_match_urls(page: Page, person_id: str) -> list[str]:
    url = (
        f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-for-person/{person_id}"
        "?matchType=4&matchStatus=32&lang=RU"
    )
    await page.goto(url, wait_until="networkidle", timeout=45000)
    await _sleep(4, 6)
    return await page.evaluate("""
        () => [...new Set(
            [...document.querySelectorAll('a[href*="match-compare"]')]
            .map(a => a.href)
        )]
    """)


async def get_people_with_record_matches(page: Page) -> list[dict]:
    await page.goto(RECORD_MATCHES_URL, wait_until="networkidle", timeout=45000)
    await _sleep(4, 6)
    return await page.evaluate("""
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


async def run_record_matches_session(
    page: Page,
    max_matches: int = 200,
    scroll_rounds: int = 8,
    sort_by: str = "count",
) -> dict:
    """Record Matches session through the Smart Matches loop (full scroll, known-conflict
    skip, navigation retry, reCAPTCHA breaker).

    Live probe 2026-10-13: matchType=1 is "Все совпадения" (smart + record), the Record
    Matches filter is matchType=4. Its "Просмотреть совпадение" button goes to a
    /research/collection-*/...?action=showRecord record viewer, not match-compare, so
    get_person_match_urls finds nothing to open and this processes 0 matches until a
    record-viewer flow exists. The runner keeps it off (RECORD_EVERY=0)."""
    return await run_smart_matches_session(
        page, max_matches=max_matches, scroll_rounds=scroll_rounds, sort_by=sort_by, match_type=4,
    )
