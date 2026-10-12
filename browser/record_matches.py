"""
Record Match (matchType=1) automation for MyHeritage.

Flow is identical to Smart Matches:
  1. Navigate to match-compare page (matchType=1 in URL)
  2. Click "Подтвердить совпадение" via AngularJS triggerHandler
  3. Page auto-navigates to showExtractWizard
  4. On wizard: click "Сохранить в дерево" (Record Match style) or
               "Извлечь всю информацию" (family-tree style, shared wizard)
  5. Confirm success ("подтверждено" text back on match-compare)

Delegates wizard logic to process_one_match() from smart_matches — same
wizard URL, same save flow; only difference is matchType=1 in the list URLs.
"""

import asyncio
import random

from playwright.async_api import Page

from browser.smart_matches import run_smart_matches_session  # shared session loop
from config import BASE_URL

TREE_ID = "OYYV6BL4NPB77IAKQQ65RX6Q4GAV5KA"
RECORD_MATCHES_URL = (
    f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-by-people"
    "?matchType=1&matchStatus=32&lang=RU"
)


async def _sleep(lo: float, hi: float) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


async def get_record_match_urls(page: Page, person_id: str) -> list[str]:
    url = (
        f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-for-person/{person_id}"
        "?matchType=1&matchStatus=32&lang=RU"
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
    """Record Matches session. 2026-10-12: runs through the same loop as Smart Matches
    (full scroll, known-conflict skip, per-person navigation retry, reCAPTCHA circuit
    breaker) instead of the old first-screen-only loop that had none of those."""
    return await run_smart_matches_session(
        page, max_matches=max_matches, scroll_rounds=scroll_rounds, sort_by=sort_by, match_type=1,
    )
