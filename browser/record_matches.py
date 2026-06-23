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
from loguru import logger
from playwright.async_api import Page

from config import BASE_URL, ACTION_DELAY_MIN, ACTION_DELAY_MAX, MATCH_DELAY_MIN, MATCH_DELAY_MAX
from browser.smart_matches import process_one_match  # shared wizard logic

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
    start_person_index: int = 0,
) -> dict:
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

            result = await process_one_match(page, url)
            status = result["status"]
            summary["processed"] += 1
            summary[status] = summary.get(status, 0) + 1

            logger.info(
                f"  [{i+1}/{len(match_urls)}] {status.upper()} "
                f"({result['fields']} fields) | total: {summary['processed']}"
            )

            if i < len(match_urls) - 1:
                await _sleep(MATCH_DELAY_MIN, MATCH_DELAY_MAX)

        summary["people"] += 1
        await _sleep(ACTION_DELAY_MIN, ACTION_DELAY_MAX)

    return summary
