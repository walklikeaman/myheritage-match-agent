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
import difflib
import json
import random
import re
import time
from datetime import datetime, timezone

from loguru import logger
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PWTimeoutError

from config import (
    BASE_URL,
    GRAPH_UPDATES_FILE,
    MATCH_DELAY_MAX,
    MATCH_DELAY_MIN,
    MERGE_CONFLICTS_FILE,
    PERSON_DELAY_MAX,
    PERSON_DELAY_MIN,
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


async def _capture_graph_snapshot(page: Page, match_url: str) -> dict | None:
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
    except Exception as e:  # noqa: BLE001 -- best-effort capture, must never affect the real flow
        logger.debug(f"  Graph capture skipped: {e}")
        return None


def _append_graph_update(record: dict) -> None:
    """Append-only write — one JSON object per line. Never raises."""
    try:
        with open(GRAPH_UPDATES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001 -- append-only write, must never raise
        logger.debug(f"  Graph update write skipped: {e}")


# ---------------------------------------------------------------------------
# Merge-conflict detection (2026-09-08)
#
# The extract wizard sometimes asks "Выберите <source person> в Вашем семейном
# дереве: <suggested existing person>" when it isn't sure two profiles are the
# same, and pre-selects a suggestion. Confirmed live 2026-09-08 (see
# wiki/log.md) that the suggestion can be a completely different real person
# (different parents/spouse, different birth-death years) — e.g. it offered to
# merge source "Анна Корниенко (Стоцкая)" with existing tree person "Ганна
# Герасімовна Корнієнко (Зозуля)". The old extract-all click accepted whatever
# was pre-selected without checking. CLAUDE.md: never auto-save conflicting
# genealogy data — flag for manual review instead.
# ---------------------------------------------------------------------------

_MERGE_CHOICE_RE = re.compile(r"Выберите (.+?) в Вашем семейном дереве:\n(.+?)\n")

_CYRILLIC_VARIANT_TABLE = str.maketrans({
    "і": "и", "І": "И", "є": "е", "Є": "Е", "ґ": "г", "Ґ": "Г", "ї": "и", "Ї": "И",
    "ё": "е", "Ё": "Е",
})

_UNKNOWN_PLACEHOLDER_RE = re.compile(
    r"^(неизвестно|неизвестна|unknown)\b|^[?\s]+$", re.IGNORECASE
)

_HEBREW_RE = re.compile(r"[֐-׿]")

# "לבית"/"בלבית" (Hebrew "née"/"of the house of"), "born"/"nee"/"née" (English/
# French) and "nacida" (Spanish, found live 2026-09-12 on "Malka Ayzen (nacida
# Levin)" vs tree "Malka (Levin)" -- same surname, false-flagged because the
# Spanish marker wasn't stripped) wrap a maiden name inside the parens without
# being part of the name itself.
_NAME_CONNECTOR_RE = re.compile(r"\b(לבית|בלבית|born|n[eé]e|nacida)\b", re.IGNORECASE)

# Honorific/relational titles that can prefix a name -- "רבי"/"rabbi"/"rav"/
# "reb"/"ר'" = Rabbi/Mr. variants, 'הרה"ח' = an abbreviated rabbinic/chassidic
# title, "הגאון" = "the Gaon" (a scholarly honorific, found live 2026-09-12
# stacked after "הרב" in "הרב הגאון משה יהודה לייב אורנשטיין"), "מרת"/"גברת" =
# Mrs./Lady, "מר"/"мр" = Mr. -- found live 2026-09-10/12 causing false-positive
# conflicts where the title, not the actual name, was compared as the "first
# token" (e.g. source 'Chaim Radzyner' vs tree 'הרה"ח חיים רדזינר Radziner' is
# the same person).
_HONORIFIC_PREFIX_RE = re.compile(
    r'^(הרה"ח|הרב|הגאון|רבי|רב|מרת|גברת|מר|rabbi|rav|reb|ר[\'׳])\s+', re.IGNORECASE
)

# A tree-generated numbered/lettered list prefix on a name, e.g. "97-Rose /
# Raisel Lubanov" or "6. Екатерина Ивановна" or "1-жена N N" -- not part of the
# name, would otherwise pollute the first token compared.
_NUMERIC_PREFIX_RE = re.compile(r"^\d+[-.)]\s*")

# Outermost parenthetical aside, e.g. "(née Lubanow (לובנוב))" -- greedy so
# nested parens are captured as one aside rather than only the innermost pair.
_PAREN_RE = re.compile(r"\((.*)\)")


def _normalize_name(name: str) -> str:
    return name.translate(_CYRILLIC_VARIANT_TABLE).lower().strip()


def _strip_honorifics(name: str) -> str:
    prev = None
    while prev != name:
        prev = name
        name = _HONORIFIC_PREFIX_RE.sub("", name).strip()
    return name


def _has_hebrew(s: str) -> bool:
    return bool(_HEBREW_RE.search(s))


def _variant_match(a: str, b: str) -> bool:
    """True if two same-script name tokens are plausibly the same name --
    exact match, a nickname/truncation (one is a substring of the other, e.g.
    'sam' in 'samuel'), or a spelling/transliteration variant (high string
    similarity, e.g. 'eliashiv'/'elyashiv', 'raifman'/'reifman'). Length gates
    avoid single-letter initials or short tokens matching almost anything."""
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 3 and len(b) >= 3 and (a in b or b in a):
        return True
    return len(a) >= 4 and len(b) >= 4 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def _expand_token(token: str) -> set[str]:
    """A token may list alternatives with '/' (e.g. 'Yosef/Yoseph') or be a
    hyphenated compound (e.g. 'משה-יהודה-לייב') -- expand to every individual
    name it could mean. Hyphen parts are added alongside the joined form
    (some hyphenated names are genuinely a single compound name); slash parts
    replace the joined form (no one is actually named 'Yosef/Yoseph')."""
    variants: set[str] = set()
    for part in token.split("/"):
        part = part.strip()
        if not part or not any(ch.isalpha() for ch in part):
            continue  # drop pure punctuation/digit noise (e.g. a lone "-" separator)
        variants.add(part)
        if "-" in part:
            variants.update(
                p.strip() for p in part.split("-")
                if p.strip() and any(ch.isalpha() for ch in p)
            )
    return variants


def _trailing_surname_run(tokens: list[str]) -> list[str]:
    """MyHeritage often lists several alternate spellings of the SAME surname
    back to back at the end of a name (e.g. '...Orenstein אורנשטיין Urstein'
    -- Latin, Hebrew, and a third Latin respelling of one surname). Taking
    only the literal last word as "the surname" then misses the other two
    entirely. Walk backward from the last token, extending the run through
    each token that is either cross-script from (unjudgeable against) or a
    spelling variant of the one immediately before it in the run. Found live
    2026-09-12: a single cross-script hop is not enough signal on its own --
    'Joseph Haim אורנשטיין' would otherwise wrongly sweep the given name
    'Haim' into the surname run just because it sits next to the Hebrew
    surname -- so only trust a run of 3+ (i.e. at least 2 confirmed hops);
    a shorter run falls back to the plain last-token guess. The first token
    is never consumed, so there's always at least one given-name token left."""
    if not tokens:
        return []
    run = [tokens[-1]]
    i = len(tokens) - 2
    while i >= 1:
        cand = tokens[i]
        cand_exp = _expand_token(cand)
        prev_exp = _expand_token(run[-1])
        if not cand_exp or not prev_exp:
            break
        extends = any(
            _has_hebrew(a) != _has_hebrew(b) or _variant_match(a, b)
            for a in cand_exp for b in prev_exp
        )
        if not extends:
            break
        run.append(cand)
        i -= 1
    return run if len(run) >= 3 else [tokens[-1]]


def _name_pools(name: str) -> tuple[set[str], set[str]]:
    """Split an already-normalized name into (given_name_pool, surname_pool)
    -- sets of acceptable token spellings, not a single positional value, so
    slash/hyphen alternatives and parenthetical aliases all count. A
    parenthetical marked with a née/born/לבית/nacida connector is a surname
    alias (maiden/birth name); a bare parenthetical could be either an
    alternate given name (e.g. '(Jacob)') or a shortened surname (e.g.
    '(ORENSTEIN)' for 'Oren'), so it's added to both pools."""
    name = _NUMERIC_PREFIX_RE.sub("", _strip_honorifics(name))
    aside_pool: set[str] = set()
    aside_is_surname_only = False
    paren = _PAREN_RE.search(name)
    if paren:
        name = name[: paren.start()] + name[paren.end():]
        aside_raw = paren.group(1).replace("(", " ").replace(")", " ")
        if _NAME_CONNECTOR_RE.search(aside_raw):
            aside_raw = _NAME_CONNECTOR_RE.sub(" ", aside_raw)
            aside_is_surname_only = True
        for tok in aside_raw.split():
            aside_pool.update(_expand_token(tok))

    tokens = name.split()
    if not tokens:
        return (set(), aside_pool)

    surname_run = _trailing_surname_run(tokens)
    surname_seed: set[str] = set()
    for tok in surname_run:
        surname_seed.update(_expand_token(tok))
    given_pool: set[str] = set()
    for tok in tokens[: len(tokens) - len(surname_run)]:
        given_pool.update(_expand_token(tok))

    # A bare (non-connector) parenthetical could be an alternate given name
    # (e.g. "(Jacob)" glossing "Yaakov") or a shortened/expanded surname (e.g.
    # "(ORENSTEIN)" for "Oren") -- found live 2026-09-12 that guessing "both
    # pools" backfires: an unrelated given-name gloss landing in the surname
    # pool can out-vote a legitimate cross-script surname bypass. Route it by
    # whether it actually resembles the surname; only fall back to "both"
    # when there's no signal either way.
    aside_matches_surname = aside_pool and any(
        _variant_match(a, b) for a in aside_pool for b in surname_seed if _has_hebrew(a) == _has_hebrew(b)
    )
    if aside_is_surname_only or aside_matches_surname:
        surname_pool = surname_seed | aside_pool
    else:
        surname_pool = surname_seed
        given_pool |= aside_pool
    return (given_pool, surname_pool)


def _pool_match(pool_a: set[str], pool_b: set[str]) -> bool:
    """True if the two token pools are consistent -- either side empty means
    nothing to compare (permissive: can't judge). Cross-script pairs (Hebrew
    vs non-Hebrew) can't be judged without real transliteration and are
    skipped; if literally every pair crosses scripts, there's nothing
    comparable at all, so don't block on it. Otherwise at least one
    same-script pair must be a plausible variant match."""
    if not pool_a or not pool_b:
        return True
    comparable = [(a, b) for a in pool_a for b in pool_b if _has_hebrew(a) == _has_hebrew(b)]
    if not comparable:
        return True
    return any(_variant_match(a, b) for a, b in comparable)


def _names_conflict(source_name: str, suggested_name: str) -> bool:
    """Best-effort, deliberately biased toward over-flagging: a false positive
    just costs the operator a couple minutes of manual review on the site; a
    false negative silently writes a stranger's family into the tree.

    Requires BOTH a given-name pool match AND a surname pool match to clear a
    pair as non-conflicting -- a shared surname alone (very common within one
    extended family cluster) is never enough on its own, which is what keeps
    genuinely different relatives sharing a surname correctly flagged."""
    src, sug = _normalize_name(source_name), _normalize_name(suggested_name)
    if src == sug:
        return False
    # Tree side is a bare "Неизвестно <surname>" placeholder — merging a named
    # record into it is enrichment, not a conflict.
    if _UNKNOWN_PLACEHOLDER_RE.match(sug):
        return False
    src_given, src_surname = _name_pools(src)
    sug_given, sug_surname = _name_pools(sug)
    return not (_pool_match(src_given, sug_given) and _pool_match(src_surname, sug_surname))


def _extract_merge_conflicts(raw_text: str) -> list[tuple[str, str]]:
    conflicts = []
    for source_name, suggested_name in _MERGE_CHOICE_RE.findall(raw_text):
        source_name, suggested_name = source_name.strip(), suggested_name.strip()
        if suggested_name.startswith("Добавить как"):
            continue  # "add as new X" — no existing candidate, not a merge
        if _names_conflict(source_name, suggested_name):
            conflicts.append((source_name, suggested_name))
    return conflicts


def _append_conflict_flag(
    match_url: str, conflicts: list[tuple[str, str]], pre_confirm: bool = False
) -> None:
    """Append-only write — one JSON object per line. Never raises."""
    try:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "match_url": match_url,
            "pre_confirm": pre_confirm,
            "conflicts": [{"source": s, "suggested": t} for s, t in conflicts],
        }
        with open(MERGE_CONFLICTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001 -- append-only write, must never raise
        logger.debug(f"  Conflict flag write skipped: {e}")


# 2026-09-10: catching conflicts only after Confirm (above) means the match LINK is
# already created on MyHeritage's side by the time we detect a mismatch -- Save gets
# skipped, but the confirm itself can't be undone from here. Found live that the
# compare page's own "Родственники" section, rendered BEFORE confirming, already
# shows each relative slot side by side: the existing tree person (if any) in
# `.individual`, and the source's proposed person in `.other_individual`. Checking
# this lets us skip the whole match -- never click Confirm -- when it's a clear
# mismatch, instead of confirming-then-discovering-then-not-saving.
_COMPARE_RELATIVES = """
() => [...document.querySelectorAll('.compare_item[data-automations="individual_row"]')].map(item => {
    const mine = item.querySelector('.individual');
    const theirs = item.querySelector('.other_individual');
    const mineMissing = !!item.querySelector('.individual .missing_relative');
    const mineName = mine ? (mine.querySelector('.individual_name')?.textContent?.trim() || null) : null;
    const theirsName = theirs ? (theirs.querySelector('.individual_name')?.textContent?.trim() || null) : null;
    return {mineMissing, mineName, theirsName};
})
"""


def _pre_confirm_conflicts(relatives: list[dict]) -> list[tuple[str, str]]:
    """Same conflict heuristic as _extract_merge_conflicts, applied to the compare
    page's relatives list instead of the post-confirm wizard's raw text."""
    conflicts = []
    for r in relatives:
        if r.get("mineMissing"):
            continue  # no existing tree relative in this slot -- nothing to conflict with
        mine, theirs = r.get("mineName"), r.get("theirsName")
        if not mine or not theirs:
            continue
        if _names_conflict(theirs, mine):
            conflicts.append((theirs, mine))
    return conflicts

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


async def _wait_for_human_captcha_solve(page: Page, attempt: int) -> bool:
    """
    Pause and let a human solve the captcha in the visible browser window
    (only meaningful with --visible). Blocks on terminal input without
    blocking the event loop. Returns True if the challenge is gone after.
    """
    loop = asyncio.get_event_loop()
    logger.warning(
        f"  reCAPTCHA shown (attempt {attempt}) — solve it in the browser window, "
        "then press Enter here to continue…"
    )
    await loop.run_in_executor(None, input, "  [press Enter after solving the captcha] ")
    still_blocked = await page.evaluate(_IS_BOT_CHALLENGE)
    return not still_blocked


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

_FIND_MANUAL_EXTRACT_LINK = """
() => {
    const a = [...document.querySelectorAll('a')]
        .find(el => el.textContent.includes('Извлечь информацию вручную'));
    return a ? a.href : null;
}
"""


async def process_one_match(
    page: Page, match_url: str, wait_for_captcha: bool = False, extract_confirmed: bool = False,
) -> dict:
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
    except Exception as e:  # noqa: BLE001 -- one bad match must not crash the whole session
        logger.error(f"Navigation failed: {e}")
        result["status"] = "error"
        return result

    # Already confirmed?
    if await page.evaluate(_IS_CONFIRMED):
        if not extract_confirmed:
            logger.info("  Already confirmed — skipping")
            result["status"] = "skip"
            return result
        # extract_confirmed mode: this match was confirmed earlier (e.g. via the
        # matches-by-source bulk "Подтвердить все" action) but never enriched. The
        # compare page for a confirmed match shows "Извлечь информацию вручную"
        # instead of "Подтвердить совпадение" — it leads to the same showExtractWizard
        # URL our normal flow reaches after confirming, so jump straight there.
        manual_link = await page.evaluate(_FIND_MANUAL_EXTRACT_LINK)
        if not manual_link:
            logger.info("  Already confirmed, no extract link found — skipping")
            result["status"] = "skip"
            return result
        logger.debug("  Already confirmed — following extract link directly")
        await page.goto(manual_link, wait_until="domcontentloaded", timeout=30000)
        await _sleep(3, 5)
        on_wizard = "showExtractWizard" in page.url
        if not on_wizard:
            logger.warning("  Could not reach wizard from confirmed match — skipping")
            result["status"] = "skip"
            return result
    else:
        # WAF may serve the reCAPTCHA challenge on the compare page itself — bail BEFORE
        # confirming, so we don't consume a match we can't enrich.
        if await page.evaluate(_IS_BOT_CHALLENGE):
            cleared = False
            if wait_for_captcha:
                for attempt in (1, 2):
                    if await _wait_for_human_captcha_solve(page, attempt):
                        cleared = True
                        break
            if not cleared:
                logger.error("  reCAPTCHA bot-challenge on compare page (captcha) — blocking session")
                result["status"] = "blocked"
                return result

        # --- Step 1b: Pre-confirm conflict check (before Confirm is ever clicked) ---
        relatives = await page.evaluate(_COMPARE_RELATIVES)
        pre_conflicts = _pre_confirm_conflicts(relatives)
        if pre_conflicts:
            for src_name, tree_name in pre_conflicts:
                logger.warning(
                    f"  Pre-confirm conflict — source '{src_name}' vs tree '{tree_name}' "
                    f"— skipping entirely, not confirming"
                )
            _append_conflict_flag(match_url, pre_conflicts, pre_confirm=True)
            result["status"] = "conflict"
            return result

        # --- Step 2: Click confirm button ---
        try:
            res = await page.evaluate(_ANGULAR_CLICK, "text:Подтвердить совпадение")
            if res == "NOT_FOUND":
                logger.warning("  Confirm button not found")
                result["status"] = "skip"
                return result
            logger.debug(f"  Confirm click: {res}")
        except Exception as e:  # noqa: BLE001 -- one bad match must not crash the whole session
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
            manual_link = await page.evaluate(_FIND_MANUAL_EXTRACT_LINK)
            if manual_link:
                logger.debug("  Following manual wizard link")
                await page.goto(manual_link, wait_until="domcontentloaded", timeout=30000)
                await _sleep(3, 5)
                on_wizard = "showExtractWizard" in page.url

            # Already confirmed via link-only flow?
            if not on_wizard and await page.evaluate(_IS_CONFIRMED):
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
    if wizard_state == "challenge" and wait_for_captcha:
        for attempt in (1, 2):
            if await _wait_for_human_captcha_solve(page, attempt):
                wizard_state = await _await_wizard_ready(page, timeout=10.0)
                break
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

    # --- Step 3b3: Refuse to auto-save a conflicting merge suggestion ---
    # See module docstring above. Confirm (Step 2) already happened and can't be
    # undone from here, but Save — the step that actually writes the wrong
    # family into the tree — is skipped, and the conflict is flagged to
    # MERGE_CONFLICTS_FILE for manual review on the site.
    if snapshot:
        conflicts = _extract_merge_conflicts(snapshot["raw_text"])
        if conflicts:
            for src_name, sug_name in conflicts:
                logger.warning(
                    f"  Conflicting merge suggestion — source '{src_name}' vs "
                    f"tree '{sug_name}' — skipping save for manual review"
                )
            _append_conflict_flag(match_url, conflicts)
            result["status"] = "conflict"
            result["fields"] = fields
            return result

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


async def get_person_match_urls(
    page: Page, person_id: str, match_type: int = 2, match_status: int = 32,
) -> list[str]:
    """Return all match-compare URLs for a person at the given status (32=pending, 8=confirmed)."""
    url = (
        f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-for-person/{person_id}"
        f"?matchType={match_type}&matchStatus={match_status}&lang=RU"
    )
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await _sleep(4, 6)
    return await page.evaluate("""
        () => [...new Set(
            [...document.querySelectorAll('a[href*="match-compare"]')]
            .map(a => a.href)
        )]
    """)


_CLICK_TEXT_EXACT = """
(text) => {
    const el = [...document.querySelectorAll('*')]
        .find(e => e.children.length === 0 && e.textContent.trim() === text);
    if (!el) return 'NOT_FOUND';
    el.click();
    return 'OK';
}
"""


async def get_people_sorted_by_count(
    page: Page,
    match_type: int = 2,
    scroll_rounds: int = 8,
    match_status: int = 32,
    sort_by: str = "count",
) -> list[dict]:
    """
    Scrape the matches-by-people list with infinite-scroll.
    match_type=2 → Smart Matches, match_type=1 → Record Matches.
    match_status=32 → pending, match_status=8 → confirmed (see run_extract_confirmed_session).
    sort_by="count" (default) → our own sort by match count desc, most efficient first.
    sort_by="relationship" → use MyHeritage's own "Родственной связи" sort (closest relatives
    first) instead of our count-based sort — this uses the site's real tree structure, which
    is far more accurate than approximating closeness from the 48-person ancestors list in
    family_graph.json. The dropdown's default state on a fresh page load is always "Значению",
    so switching it is reliable without needing to read current state first.
    """
    list_url = (
        f"{BASE_URL}/discovery-hub/{TREE_ID}/matches-by-people"
        f"?matchType={match_type}&matchStatus={match_status}&lang=RU"
    )
    await page.goto(list_url, wait_until="networkidle", timeout=45000)
    await _sleep(5, 7)

    if sort_by == "relationship":
        res = await page.evaluate(_CLICK_TEXT_EXACT, "Значению")
        if res == "NOT_FOUND":
            logger.warning("  Sort dropdown not found — falling back to default (count) order")
        else:
            await _sleep(1, 1.5)
            res2 = await page.evaluate(_CLICK_TEXT_EXACT, "Родственной связи")
            if res2 == "NOT_FOUND":
                logger.warning("  'Родственной связи' option not found — falling back to default order")
            else:
                # This re-sort recomputes against the whole tree server-side and is much
                # slower than the default count sort — 3-5s wasn't enough in testing
                # (empty list), needed ~15-20s before cards actually render.
                await _sleep(16, 20)

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

    if sort_by == "count":
        all_people.sort(key=lambda p: p["count"], reverse=True)
    # sort_by="relationship": preserve the order the site's own sort already gave us
    return all_people


# ---------------------------------------------------------------------------
# Session runners
# ---------------------------------------------------------------------------

async def run_smart_matches_session(
    page: Page,
    max_matches: int = 200,
    scroll_rounds: int = 8,
    wait_for_captcha: bool = False,
    sort_by: str = "count",
) -> dict:
    """Smart Matches (matchType=2) session — largest families first, or closest relatives
    first when sort_by="relationship"."""
    summary = {"processed": 0, "ok": 0, "skip": 0, "error": 0, "people": 0}

    logger.info(f"Loading Smart Matches by-people list (sorted by {sort_by})…")
    people = await get_people_sorted_by_count(page, match_type=2, scroll_rounds=scroll_rounds, sort_by=sort_by)
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
            result = await process_one_match(page, url, wait_for_captcha=wait_for_captcha)
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


# Consecutive people who yield zero new fields before we assume this branch of the
# tree is already covered (the "Извлечь всю информацию" step pulls in a matched
# person's whole visible family — spouse, children — so extracting an early "hub"
# person often makes several later confirmed matches in the same cluster redundant).
_EXTRACT_CONFIRMED_DRY_STREAK = 5


async def run_extract_confirmed_session(
    page: Page,
    max_matches: int = 200,
    scroll_rounds: int = 8,
    wait_for_captcha: bool = False,
) -> dict:
    """
    Walk already-CONFIRMED Smart Matches (matchStatus=8) and extract/save the data
    that was never pulled in — e.g. matches confirmed in bulk via the "Совпадения по
    источнику" → "Подтвердить все" action, which registers the link but does not
    extract any fields. Same per-match extraction code as run_smart_matches_session,
    just entered via the "Извлечь информацию вручную" link instead of a confirm click.

    No pre-computed iteration count: a single extraction can cascade in several
    relatives' data via the matched tree's visible family, so a later person's own
    "confirmed match" entry is often already redundant. Instead of guessing how many
    people to cover, we track a rolling streak of people who added zero new fields and
    stop early once _EXTRACT_CONFIRMED_DRY_STREAK is hit — same "loop until dry" idea
    used elsewhere for unknown-size discovery, applied per-person instead of per-round.
    """
    summary = {"processed": 0, "ok": 0, "skip": 0, "error": 0, "people": 0, "new_fields": 0}

    logger.info("Loading confirmed Smart Matches by-people list (sorted by count)…")
    people = await get_people_sorted_by_count(page, match_type=2, scroll_rounds=scroll_rounds, match_status=8)
    logger.info(f"Found {len(people)} people with confirmed matches | top: {people[0]['name']} ({people[0]['count']} matches)" if people else "Found 0 people")

    dry_streak = 0
    for person in people:
        if summary["processed"] >= max_matches:
            logger.info(f"Session cap ({max_matches}) reached — stopping")
            break

        logger.info(f"\n{'='*60}\n{person['name']} (ID: {person['id']}, ~{person['count']} confirmed matches)")
        match_urls = await get_person_match_urls(page, person["id"], match_type=2, match_status=8)
        logger.info(f"  {len(match_urls)} confirmed Smart Matches to extract")

        person_new_fields = 0
        for i, url in enumerate(match_urls):
            if summary["processed"] >= max_matches:
                break
            result = await process_one_match(
                page, url, wait_for_captcha=wait_for_captcha, extract_confirmed=True,
            )
            status = result["status"]
            summary["processed"] += 1
            summary[status] = summary.get(status, 0) + 1
            summary["new_fields"] += result["fields"]
            person_new_fields += result["fields"]
            logger.info(f"  [{i+1}/{len(match_urls)}] {status.upper()} ({result['fields']} fields) | total: {summary['processed']}")
            if status == "blocked":
                summary["aborted"] = "captcha"
                logger.error(f"reCAPTCHA challenge (captcha) — aborting session after {summary['processed']} matches to back off")
                return summary
            if i < len(match_urls) - 1:
                await _sleep(MATCH_DELAY_MIN, MATCH_DELAY_MAX)

        summary["people"] += 1
        if person_new_fields == 0:
            dry_streak += 1
            logger.debug(f"  0 new fields for this person — dry streak {dry_streak}/{_EXTRACT_CONFIRMED_DRY_STREAK}")
            if dry_streak >= _EXTRACT_CONFIRMED_DRY_STREAK:
                summary["aborted"] = "dry"
                logger.info(
                    f"{dry_streak} people in a row added nothing new — likely already "
                    "covered via relative cascade from earlier extractions. Stopping early."
                )
                return summary
        else:
            dry_streak = 0
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
