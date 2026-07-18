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
import json
import random
import time
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from playwright.async_api import Page, TimeoutError as PWTimeoutError

from config import (
    BASE_URL,
    ACTION_DELAY_MIN,
    ACTION_DELAY_MAX,
    MATCH_DELAY_MIN,
    MATCH_DELAY_MAX,
    PERSON_DELAY_MIN,
    PERSON_DELAY_MAX,
    GRAPH_UPDATES_FILE,
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

# Local graph accumulation (2026-07-18): the wizard's navigator sidebar lists every
# person this extraction touches (the main match plus any expanded relatives), each
# with a name and its relation to the main person. Recon on a live wizard confirmed
# `li.individual_navigator_item` (class `main_true`/`main_false`) + `.individual_full_name`
# + `.individual_relationship`. Combined with the raw `.extract_record_row` text (which
# carries Имя/Фамилия/Рождение/Смерть/Родители etc. per person in DOM order), this is
# enough to accumulate a local graph incrementally without a manual GEDCOM re-export —
# see `graph_accumulate.py` for how these get merged and VIP-scanned.
_NAVIGATOR_PEOPLE = """
() => [...document.querySelectorAll('li.individual_navigator_item')].map(li => ({
    main: li.className.includes('main_true'),
    name: (li.querySelector('.individual_full_name') || {}).textContent?.trim() || null,
    relation: (li.querySelector('.individual_relationship') || {}).textContent?.trim() || null,
}))
"""

_EXTRACT_ROWS_TEXT = """
() => [...document.querySelectorAll('.extract_record_row')]
    .map(r => r.innerText.trim())
    .filter(t => t)
    .join('\\n===ROW===\\n')
"""


async def _capture_graph_snapshot(page: Page, match_url: str) -> Optional[dict]:
    """
    Best-effort scrape of the wizard's navigator (name + relation-to-main per person)
    and the raw extract-row text, appended to GRAPH_UPDATES_FILE for later offline
    accumulation into the local family graph. Never raises — a capture failure must
    never affect the real confirm/extract/save flow.
    """
    try:
        navigator = await page.evaluate(_NAVIGATOR_PEOPLE)
        raw_text = await page.evaluate(_EXTRACT_ROWS_TEXT)
        if not navigator and not raw_text:
            return None
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "match_url": match_url,
            "navigator": navigator,
            "raw_text": raw_text[:20000],
        }
    except Exception as e:
        logger.debug(f"  Graph capture skipped: {e}")
        return None


def _append_graph_update(record: dict) -> None:
    """Append-only write — one JSON object per line. Never raises."""
    try:
        with open(GRAPH_UPDATES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.debug(f"  Graph update write skipped: {e}")

# WAF bot-challenge served IN PLACE OF a page (HTTP 200, no Angular render).
# Recon 2026-06-27: MyHeritage FraudProtection serves a Google reCAPTCHA Enterprise
# challenge ("/FP/recaptcha-challenge.php" iframe + "докажите, что Вы человек" body,
# ~578 chars) when the session is flagged. This is the true cause of the old
# "saveButton not found" mass failures. See wiki/concepts/selectors.md and
# wiki/concepts/session-economics.md.
# Recon 2026-07-17: a second, distinct WAF vendor was also observed serving the same
# in-place-of-wizard block — Imperva Incapsula ("_Incapsula_Resource" iframe, 0-char
# body, 0 Angular nodes, ~886-byte HTML). Neither the recaptcha selector nor the
# body-text regex matches it, so it was falling through to the "empty" (skip) path
# instead of "challenge" (blocked) — silently confirming matches with zero enrichment
# and never triggering the runner's backoff. See session-economics.md for the fix.
_IS_BOT_CHALLENGE = """
() => {
    if (document.querySelector('iframe[src*="recaptcha-challenge.php"]')) return true;
    if (document.querySelector('iframe[src*="_Incapsula_Resource"]')) return true;
    const body = document.body.innerText || '';
    return body.length < 3000 &&
        /Вы\\s*-?\\s*робот|докажите, что Вы человек|prove you are human|that you are human/i.test(body);
}
"""

# Any of the three extract-control variants is present (mirror of _CLICK_EXTRACT_ALL's
# find conditions, without clicking) — used to poll for the wizard to finish rendering.
_HAS_EXTRACT_CONTROL = """
() => {
    const txt = (e) => (e.textContent || '').trim();
    if ([...document.querySelectorAll('*')]
            .some(e => e.children.length === 0 && txt(e) === 'Извлечь всю информацию')) return true;
    if (document.querySelector('[class*="extract_record_row_copied_all_sign"]')) return true;
    return [...document.querySelectorAll('a,button,[ng-click]')]
        .some(e => txt(e).startsWith('Сохранить в дерево') ||
                   ((e.getAttribute('ng-click') || '').includes('saveAndNavigateTo')));
}
"""

# Click the final save (id=saveButton) or the Record-Match fallback; poll-friendly.
_SAVE_CLICK = """
() => {
    const b = document.getElementById('saveButton');
    if (b) { window.angular.element(b).triggerHandler('click'); return 'OK'; }
    const rm = [...document.querySelectorAll('a,button,[ng-click]')]
        .find(e => e.textContent.trim().startsWith('Сохранить в дерево') ||
                   (e.getAttribute('ng-click')||'').includes('saveAndNavigateTo'));
    if (rm) { window.angular.element(rm).triggerHandler('click'); return 'OK_RM'; }
    return 'NOT_FOUND';
}
"""


async def _sleep(lo: float, hi: float) -> None:
    await asyncio.sleep(random.uniform(lo, hi))


async def _await_wizard_ready(page: Page, timeout: float = 10.0, interval: float = 0.7) -> str:
    """
    Poll the post-confirm wizard. Angular renders the extract control client-side, so a
    single immediate read races the paint. Returns one of:
      'control'   — an extract control is present, safe to click
      'challenge' — a reCAPTCHA bot-challenge was served instead of the wizard
      'empty'     — neither appeared within the timeout
    """
    deadline = time.monotonic() + timeout
    while True:
        if await page.evaluate(_IS_BOT_CHALLENGE):
            return "challenge"
        if await page.evaluate(_HAS_EXTRACT_CONTROL):
            return "control"
        if time.monotonic() >= deadline:
            return "empty"
        await asyncio.sleep(interval)


async def _poll_save_click(page: Page, timeout: float = 10.0, interval: float = 0.7) -> str:
    """Angular can re-render the save button after extract; poll up to ~timeout before NOT_FOUND."""
    deadline = time.monotonic() + timeout
    res = "NOT_FOUND"
    while True:
        res = await page.evaluate(_SAVE_CLICK)
        if res != "NOT_FOUND":
            return res
        if time.monotonic() >= deadline:
            return res
        await asyncio.sleep(interval)


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

    # WAF may serve the reCAPTCHA challenge on the compare page itself — bail BEFORE
    # confirming, so we don't consume a match we can't enrich.
    if await page.evaluate(_IS_BOT_CHALLENGE):
        logger.error("  reCAPTCHA bot-challenge on compare page (captcha) — blocking session")
        result["status"] = "blocked"
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

    # --- Step 3: Extract all info (text fields + relatives) ---
    await _sleep(2, 4)
    # Poll for the wizard to render. This both fixes the Angular paint race (a single
    # read was firing before the control existed) AND catches the reCAPTCHA bot-challenge
    # the WAF serves in place of the wizard when the session is flagged.
    wizard_state = await _await_wizard_ready(page, timeout=10.0)
    if wizard_state == "challenge":
        # The match was confirmed in Step 2, but the wizard is walled off by reCAPTCHA.
        # Continuing would confirm more matches without enriching them, so stop the
        # session and let the runner's backoff kick in.
        logger.error("  reCAPTCHA bot-challenge instead of wizard (captcha) — blocking session")
        result["status"] = "blocked"
        return result
    if wizard_state == "empty":
        logger.warning("  Wizard rendered no extract control after 10s — skipping (wizard-empty)")
        result["status"] = "skip"
        return result

    click_res = await page.evaluate(_CLICK_EXTRACT_ALL)
    logger.debug(f"  Extract click: {click_res}")
    if not click_res.get("clicked"):
        logger.warning("  Extract control vanished before click — skipping (wizard-empty)")
        result["status"] = "skip"
        return result
    await _sleep(1.5, 3)
    success = await page.evaluate(_CHECK_EXTRACT_SUCCESS)
    if not success and click_res.get("clicked") == "all":
        logger.warning("  Extract-all didn't toggle — retrying once")
        await page.evaluate(_CLICK_EXTRACT_ALL)
        await _sleep(2, 3)

    # --- Step 3b: Expand additional relatives ("Извлечь информацию еще об N родственниках") ---
    more_relatives = await page.evaluate("""
        () => {
            const btn = [...document.querySelectorAll('a,button,[ng-click],[class*="extract"]')]
                .find(e => e.textContent.trim().startsWith('Извлечь информацию еще об'));
            if (!btn) return null;
            window.angular.element(btn).triggerHandler('click');
            return btn.textContent.trim().substring(0, 60);
        }
    """)
    if more_relatives:
        logger.debug(f"  Relatives expansion: {more_relatives}")
        await _sleep(2, 3)

    fields = await page.evaluate(_FIELD_COUNT)
    logger.debug(f"  Fields: {fields}")
    # A populated Smart-Match wizard always yields checkboxes; 0 means it never really
    # rendered (the RM 'rm_save' path legitimately has none, so exclude it). Don't save.
    if fields == 0 and click_res.get("clicked") in ("all", "single"):
        logger.warning("  Wizard populated 0 fields — skipping (wizard-empty)")
        result["status"] = "skip"
        return result

    # --- Step 3b2: Capture graph snapshot for local accumulation (best-effort) ---
    snapshot = await _capture_graph_snapshot(page, match_url)
    if snapshot:
        _append_graph_update(snapshot)

    # --- Step 3c: Transfer photos ---
    photos_clicked = await page.evaluate("""
        () => {
            // uploadPhoto() divs on wizard = photos from the matched tree to import
            const photos = [...document.querySelectorAll('[ng-click="uploadPhoto()"]')];
            let clicked = 0;
            for (const el of photos) {
                try {
                    window.angular.element(el).triggerHandler('click');
                    clicked++;
                } catch(e) {}
            }
            return clicked;
        }
    """)
    if photos_clicked:
        logger.debug(f"  Photos queued for transfer: {photos_clicked}")
        await _sleep(1, 2)

    # --- Step 4: Save (poll — Angular may re-render the button after extract) ---
    save_res = await _poll_save_click(page, timeout=10.0)
    logger.debug(f"  Save click: {save_res}")

    if save_res == "NOT_FOUND":
        # A wizard rendered and extracted, yet no save button after a 10s poll — a genuine
        # anomaly now (the mass reCAPTCHA failures are caught upstream as 'blocked').
        logger.error("  saveButton not found after 10s poll")
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
        photos_note = f" + {photos_clicked} photos" if photos_clicked else ""
        logger.info(f"  ✓ Saved — {fields} fields{photos_note}")
        result["status"] = "ok"
        result["fields"] = fields
        result["photos"] = photos_clicked
    else:
        logger.warning("  Save may not have completed (no 'подтверждено' text)")
        result["status"] = "error"

    return result


# ---------------------------------------------------------------------------
# Person-level iteration
# ---------------------------------------------------------------------------

_EXTRACT_PEOPLE = """
() => {
    const seen = new Set();
    const result = [];
    const links = [...document.querySelectorAll('a[href*="matches-for-person"]')];
    for (const a of links) {
        const m = a.href.match(/matches-for-person\\/([^?]+)/);
        if (!m || seen.has(m[1])) continue;
        seen.add(m[1]);

        // Walk up to find the card container
        let card = a;
        for (let i = 0; i < 6; i++) {
            if (!card.parentElement) break;
            card = card.parentElement;
            if (card.className && (card.className.includes('action_elements') ||
                card.className.includes('person_card') || card.className.includes('card'))) break;
        }

        // Extract name from card
        const nameEl = card.querySelector('[class*="person_name"],[class*="fullname"],[class*="title"]') || a;
        const name = nameEl.textContent.trim().substring(0, 60);

        // Extract match count from "Просмотрите N совпадения"
        const cardText = card.innerText || '';
        const countMatch = cardText.match(/Просмотрите\\s+(\\d+)\\s+совпадени/);
        const count = countMatch ? parseInt(countMatch[1]) : 0;

        result.push({id: m[1], name, count});
    }
    return result;
}
"""


async def get_person_match_urls(page: Page, person_id: str, match_type: int = 2) -> list[str]:
    """Return all pending match-compare URLs for a person."""
    url = (
        f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-for-person/{person_id}"
        f"?matchType={match_type}&matchStatus=32&lang=RU"
    )
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await _sleep(4, 6)
    return await page.evaluate("""
        () => [...new Set(
            [...document.querySelectorAll('a[href*="match-compare"]')]
            .map(a => a.href)
        )]
    """)


async def get_people_sorted_by_count(
    page: Page,
    match_type: int = 2,
    scroll_rounds: int = 8,
) -> list[dict]:
    """
    Scrape the matches-by-people list with infinite-scroll, sort by match count desc.
    match_type=2 → Smart Matches, match_type=1 → Record Matches.
    """
    list_url = (
        f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-by-people"
        f"?matchType={match_type}&matchStatus=32&lang=RU"
    )
    await page.goto(list_url, wait_until="networkidle", timeout=45000)
    await _sleep(5, 7)

    seen_ids: set[str] = set()
    all_people: list[dict] = []

    for round_n in range(scroll_rounds):
        batch = await page.evaluate(_EXTRACT_PEOPLE)
        new = [p for p in batch if p["id"] not in seen_ids]
        for p in new:
            seen_ids.add(p["id"])
            all_people.append(p)

        if not new and round_n > 0:
            logger.debug(f"  Scroll {round_n}: no new people — stopping scroll")
            break

        logger.debug(f"  Scroll {round_n}: +{len(new)} people (total {len(all_people)})")
        # Scroll to bottom to trigger infinite-load
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await _sleep(3, 5)

    all_people.sort(key=lambda p: p["count"], reverse=True)
    return all_people


# ---------------------------------------------------------------------------
# Session runners
# ---------------------------------------------------------------------------

async def run_smart_matches_session(
    page: Page,
    max_matches: int = 200,
    scroll_rounds: int = 8,
) -> dict:
    """Smart Matches (matchType=2) session — largest families first."""
    summary = {"processed": 0, "ok": 0, "skip": 0, "error": 0, "people": 0}

    logger.info("Loading Smart Matches by-people list (sorted by count)…")
    people = await get_people_sorted_by_count(page, match_type=2, scroll_rounds=scroll_rounds)
    logger.info(f"Found {len(people)} people | top: {people[0]['name']} ({people[0]['count']} matches)" if people else "Found 0 people")

    for person in people:
        if summary["processed"] >= max_matches:
            logger.info(f"Session cap ({max_matches}) reached — stopping")
            break

        logger.info(f"\n{'='*60}\n{person['name']} (ID: {person['id']}, ~{person['count']} matches)")
        match_urls = await get_person_match_urls(page, person["id"], match_type=2)
        logger.info(f"  {len(match_urls)} pending Smart Matches")

        for i, url in enumerate(match_urls):
            if summary["processed"] >= max_matches:
                break
            result = await process_one_match(page, url)
            status = result["status"]
            summary["processed"] += 1
            summary[status] = summary.get(status, 0) + 1
            logger.info(f"  [{i+1}/{len(match_urls)}] {status.upper()} ({result['fields']} fields) | total: {summary['processed']}")
            if status == "blocked":
                # Circuit breaker: a reCAPTCHA challenge means the WAF has flagged us.
                # Stop now (every further confirm would consume a match without enriching
                # it) and emit a 'captcha' token so the auto-runner applies its long backoff.
                summary["aborted"] = "captcha"
                logger.error(f"reCAPTCHA challenge (captcha) — aborting session after {summary['processed']} matches to back off")
                return summary
            if i < len(match_urls) - 1:
                await _sleep(MATCH_DELAY_MIN, MATCH_DELAY_MAX)

        summary["people"] += 1
        await _sleep(PERSON_DELAY_MIN, PERSON_DELAY_MAX)

    return summary


async def run_combined_session(
    page: Page,
    max_matches: int = 200,
    scroll_rounds: int = 8,
) -> dict:
    """
    Combined mode: per person, process Smart Matches then Record Matches.
    People sorted by total match count (largest families first).
    """
    summary = {"processed": 0, "ok": 0, "skip": 0, "error": 0, "people": 0,
               "smart_ok": 0, "record_ok": 0}

    logger.info("Loading Smart Matches list…")
    smart_people = await get_people_sorted_by_count(page, match_type=2, scroll_rounds=scroll_rounds)
    logger.info(f"  {len(smart_people)} people with Smart Matches")

    logger.info("Loading Record Matches list…")
    record_people = await get_people_sorted_by_count(page, match_type=1, scroll_rounds=scroll_rounds)
    logger.info(f"  {len(record_people)} people with Record Matches")

    # Merge: combine counts, union of people
    merged: dict[str, dict] = {}
    for p in smart_people:
        merged[p["id"]] = {"id": p["id"], "name": p["name"],
                           "smart_count": p["count"], "record_count": 0}
    for p in record_people:
        if p["id"] in merged:
            merged[p["id"]]["record_count"] = p["count"]
        else:
            merged[p["id"]] = {"id": p["id"], "name": p["name"],
                               "smart_count": 0, "record_count": p["count"]}

    people = sorted(merged.values(),
                    key=lambda p: p["smart_count"] + p["record_count"], reverse=True)
    logger.info(f"Total: {len(people)} unique people | top: {people[0]['name']} "
                f"(SM:{people[0]['smart_count']} RM:{people[0]['record_count']})" if people else "")

    for person in people:
        if summary["processed"] >= max_matches:
            logger.info(f"Session cap ({max_matches}) reached — stopping")
            break

        pid = person["id"]
        logger.info(f"\n{'='*60}\n{person['name']} (SM:{person['smart_count']} RM:{person['record_count']})")

        # --- Smart Matches first ---
        if person["smart_count"] > 0:
            sm_urls = await get_person_match_urls(page, pid, match_type=2)
            for i, url in enumerate(sm_urls):
                if summary["processed"] >= max_matches:
                    break
                result = await process_one_match(page, url)
                status = result["status"]
                summary["processed"] += 1
                summary[status] = summary.get(status, 0) + 1
                if status == "ok":
                    summary["smart_ok"] += 1
                logger.info(f"  SM [{i+1}/{len(sm_urls)}] {status.upper()} ({result['fields']} fields) | total: {summary['processed']}")
                if status == "blocked":
                    summary["aborted"] = "captcha"
                    logger.error(f"reCAPTCHA challenge (captcha) — aborting session after {summary['processed']} matches to back off")
                    return summary
                if i < len(sm_urls) - 1:
                    await _sleep(MATCH_DELAY_MIN, MATCH_DELAY_MAX)

        # --- Record Matches second ---
        if person["record_count"] > 0 and summary["processed"] < max_matches:
            rm_urls = await get_person_match_urls(page, pid, match_type=1)
            for i, url in enumerate(rm_urls):
                if summary["processed"] >= max_matches:
                    break
                result = await process_one_match(page, url)
                status = result["status"]
                summary["processed"] += 1
                summary[status] = summary.get(status, 0) + 1
                if status == "ok":
                    summary["record_ok"] += 1
                logger.info(f"  RM [{i+1}/{len(rm_urls)}] {status.upper()} ({result['fields']} fields) | total: {summary['processed']}")
                if status == "blocked":
                    summary["aborted"] = "captcha"
                    logger.error(f"reCAPTCHA challenge (captcha) — aborting session after {summary['processed']} matches to back off")
                    return summary
                if i < len(rm_urls) - 1:
                    await _sleep(MATCH_DELAY_MIN, MATCH_DELAY_MAX)

        summary["people"] += 1
        await _sleep(PERSON_DELAY_MIN, PERSON_DELAY_MAX)

    return summary
