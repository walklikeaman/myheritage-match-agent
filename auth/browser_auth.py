"""
Session management for MyHeritage browser automation.

Two ways to authenticate:
  1. Load cookies exported from Chrome (EditThisCookie JSON format)
  2. Load a Playwright storage_state saved from a previous successful session

Preference: always try storage_state first (it includes cookies + localStorage),
fall back to raw cookie import if no state file exists yet.
"""

import json
import asyncio
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, BrowserContext, Page
from loguru import logger

from config import (
    COOKIES_FILE,
    SESSION_FILE,
    VIEWPORT,
    USER_AGENT,
    BASE_URL,
)


def _normalize_cookies(raw: list[dict]) -> list[dict]:
    """
    Convert EditThisCookie / browser export format to Playwright format.
    EditThisCookie uses 'expirationDate' (float); Playwright wants 'expires' (int).
    Also strips keys Playwright doesn't accept.
    """
    playwright_keys = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
    normalized = []
    for c in raw:
        cookie = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
        }
        # Handle expiry field name variants
        if "expirationDate" in c:
            cookie["expires"] = int(c["expirationDate"])
        elif "expires" in c:
            cookie["expires"] = int(c["expires"])
        else:
            cookie["expires"] = -1  # session cookie

        # sameSite must be one of: "Strict", "Lax", "None"
        same_site = c.get("sameSite", "Lax")
        if same_site not in ("Strict", "Lax", "None"):
            same_site = "Lax"
        cookie["sameSite"] = same_site

        normalized.append(cookie)
    return normalized


async def _check_logged_in(page: Page) -> bool:
    """Navigate to profile page and check if we're authenticated."""
    try:
        await page.goto(f"{BASE_URL}/my/account", wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(2)
        url = page.url
        # If redirected to login page, we're not authenticated
        if "login" in url or "signin" in url or "accounts.myheritage" in url:
            logger.warning("Session check: redirected to login, not authenticated")
            return False
        # Look for a sign of being logged in (avatar, username, etc.)
        logged_in = await page.locator("[data-testid='user-menu'], .user-avatar, .profile-menu, #user-menu-btn").count()
        if logged_in > 0:
            logger.info("Session check: logged in (found user menu element)")
            return True
        # Fallback: check URL didn't redirect to login
        if "myheritage.com/my" in url or "myheritage.com/account" in url:
            logger.info("Session check: logged in (stayed on account page)")
            return True
        logger.warning(f"Session check: unclear state at URL {url}")
        return False
    except Exception as e:
        logger.error(f"Session check failed: {e}")
        return False


async def create_browser_context(playwright, headless: bool = False) -> BrowserContext:
    """
    Launch Chromium and return an authenticated BrowserContext.

    Tries in order:
    1. Load Playwright storage_state from SESSION_FILE (most reliable)
    2. Load raw cookies from COOKIES_FILE and convert them
    3. Return unauthenticated context (recon mode / manual login)
    """
    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )

    context = None

    # --- Strategy 1: Playwright session state ---
    if SESSION_FILE.exists():
        logger.info(f"Loading Playwright session state from {SESSION_FILE}")
        try:
            context = await browser.new_context(
                storage_state=str(SESSION_FILE),
                viewport=VIEWPORT,
                user_agent=USER_AGENT,
                locale="en-US",
            )
            # Mask WebDriver flag
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            logger.info("Session state loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load session state: {e}. Trying cookie import.")
            context = None

    # --- Strategy 2: Raw cookie import ---
    if context is None and COOKIES_FILE.exists():
        logger.info(f"Loading cookies from {COOKIES_FILE}")
        try:
            with open(COOKIES_FILE, "r") as f:
                raw_cookies = json.load(f)
            cookies = _normalize_cookies(raw_cookies)
            context = await browser.new_context(
                viewport=VIEWPORT,
                user_agent=USER_AGENT,
                locale="en-US",
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            await context.add_cookies(cookies)
            logger.info(f"Imported {len(cookies)} cookies")
        except Exception as e:
            logger.error(f"Cookie import failed: {e}")
            context = None

    # --- Strategy 3: Unauthenticated fallback ---
    if context is None:
        logger.warning("No session or cookies found — launching unauthenticated browser")
        context = await browser.new_context(
            viewport=VIEWPORT,
            user_agent=USER_AGENT,
            locale="en-US",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    return context


async def validate_and_save_session(context: BrowserContext) -> bool:
    """
    Open a page, check if we're logged into MyHeritage, and if so,
    save the current storage state to SESSION_FILE for future runs.

    Returns True if authenticated.
    """
    page = await context.new_page()
    try:
        is_logged_in = await _check_logged_in(page)
        if is_logged_in:
            await context.storage_state(path=str(SESSION_FILE))
            logger.info(f"Session saved to {SESSION_FILE}")
        return is_logged_in
    finally:
        await page.close()


async def get_authenticated_context(headless: bool = False):
    """
    High-level entry point: returns (playwright, context, is_authenticated).
    Caller is responsible for closing playwright when done.
    """
    playwright = await async_playwright().start()
    context = await create_browser_context(playwright, headless=headless)
    is_auth = await validate_and_save_session(context)
    return playwright, context, is_auth


# --- CLI usage for testing auth alone ---
if __name__ == "__main__":
    import sys
    from rich.console import Console

    console = Console()

    async def main():
        console.print("[bold]MyHeritage Auth Check[/bold]")
        console.print(f"Session file: {SESSION_FILE} (exists: {SESSION_FILE.exists()})")
        console.print(f"Cookies file: {COOKIES_FILE} (exists: {COOKIES_FILE.exists()})")

        playwright, context, is_auth = await get_authenticated_context(headless=False)
        if is_auth:
            console.print("[green]✓ Authenticated successfully[/green]")
            console.print(f"[green]Session saved to {SESSION_FILE}[/green]")
        else:
            console.print("[red]✗ Not authenticated[/red]")
            console.print(
                "\n[yellow]To authenticate:[/yellow]\n"
                "1. Log into MyHeritage in Chrome\n"
                "2. Export cookies with EditThisCookie extension (JSON format)\n"
                f"3. Save the exported JSON to: {COOKIES_FILE}\n"
                "4. Run this script again"
            )
        await playwright.stop()
        return is_auth

    success = asyncio.run(main())
    sys.exit(0 if success else 1)
