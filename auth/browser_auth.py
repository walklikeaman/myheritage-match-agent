"""
Session management for MyHeritage browser automation.

Two ways to authenticate:
  1. Load cookies exported from Chrome (EditThisCookie JSON format)
  2. Load a Playwright storage_state saved from a previous successful session

Preference: always try storage_state first (it includes cookies + localStorage),
fall back to raw cookie import if no state file exists yet.
"""

import json
import random
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

# ---------------------------------------------------------------------------
# Stealth init script — injected into every page before any JS runs.
# Covers the most common headless-detection vectors used by bot-protection
# systems (Cloudflare, PerimeterX, DataDome, etc.)
# ---------------------------------------------------------------------------
_STEALTH_SCRIPT = """
(() => {
    // 1. webdriver — use defineProperty so it survives toString inspection
    try {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
            configurable: true,
            enumerable: true,
        });
    } catch(e) {}

    // 2. plugins — headless has 0; real Chrome ships with 3
    try {
        const mkPlugin = (name, filename, description) => {
            const p = {name, filename, description, length: 0};
            Object.setPrototypeOf(p, Plugin.prototype);
            return p;
        };
        const plugins = [
            mkPlugin('Chrome PDF Plugin', 'internal-pdf-viewer', 'Portable Document Format'),
            mkPlugin('Chrome PDF Viewer', 'mhjfbmdgcfjbbpaeojofohoefgiehjai', ''),
            mkPlugin('Native Client', 'internal-nacl-plugin', ''),
        ];
        const pa = Object.create(PluginArray.prototype);
        Object.defineProperty(pa, 'length', {get: () => plugins.length});
        plugins.forEach((p, i) => { pa[i] = p; pa[p.name] = p; });
        Object.defineProperty(navigator, 'plugins', {get: () => pa, enumerable: true});
    } catch(e) {}

    // 3. languages — match the RU locale we set in the context
    try {
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ru-RU', 'ru', 'en-US', 'en'],
            enumerable: true,
        });
    } catch(e) {}

    // 4. window.chrome — headless may be missing loadTimes / csi
    try {
        if (!window.chrome) window.chrome = {};
        window.chrome.loadTimes = window.chrome.loadTimes || (() => ({}));
        window.chrome.csi        = window.chrome.csi        || (() => ({}));
        window.chrome.app        = window.chrome.app        || {isInstalled: false};
        if (!window.chrome.runtime) window.chrome.runtime = {};
    } catch(e) {}

    // 5. permissions — headless returns 'denied' for notifications by default;
    //    real Chrome returns 'default'. Also prevents fingerprinting via async query.
    try {
        const origQuery = navigator.permissions.query.bind(navigator.permissions);
        navigator.permissions.query = (params) => {
            if (params.name === 'notifications') {
                return Promise.resolve({state: 'default', onchange: null});
            }
            return origQuery(params);
        };
    } catch(e) {}

    // 6. hardware concurrency — headless often shows 2; M1 Mac shows 8
    try {
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8, enumerable: true,
        });
    } catch(e) {}

    // 7. platform
    try {
        Object.defineProperty(navigator, 'platform', {
            get: () => 'MacIntel', enumerable: true,
        });
    } catch(e) {}

    // 8. WebGL — headless Chromium reports "Google SwiftShader" which is the
    //    single biggest bot signal. Spoof to match a real Mac GPU.
    try {
        const patchGL = (ctx) => {
            const orig = ctx.getParameter.bind(ctx);
            ctx.getParameter = function(parameter) {
                if (parameter === 37445) return 'Apple Inc.';   // UNMASKED_VENDOR
                if (parameter === 37446) return 'Apple GPU';    // UNMASKED_RENDERER
                return orig(parameter);
            };
        };
        const canvas = document.createElement('canvas');
        const gl  = canvas.getContext('webgl');
        const gl2 = canvas.getContext('webgl2');
        if (gl)  patchGL(gl);
        if (gl2) patchGL(gl2);

        // Also patch the prototype so future canvases inherit the spoof
        const patchProto = (proto) => {
            if (!proto) return;
            const orig = proto.getParameter;
            proto.getParameter = function(parameter) {
                if (parameter === 37445) return 'Apple Inc.';
                if (parameter === 37446) return 'Apple GPU';
                return orig.call(this, parameter);
            };
        };
        patchProto(WebGLRenderingContext.prototype);
        if (typeof WebGL2RenderingContext !== 'undefined') {
            patchProto(WebGL2RenderingContext.prototype);
        }
    } catch(e) {}

    // 9. screen — match the viewport we launch with (avoids 0×0 headless screen)
    try {
        Object.defineProperty(screen, 'width',       {get: () => 1440});
        Object.defineProperty(screen, 'height',      {get: () => 900});
        Object.defineProperty(screen, 'availWidth',  {get: () => 1440});
        Object.defineProperty(screen, 'availHeight', {get: () => 877});
        Object.defineProperty(screen, 'colorDepth',  {get: () => 30});
        Object.defineProperty(screen, 'pixelDepth',  {get: () => 30});
    } catch(e) {}
})();
"""

# Extra HTTP headers that a real Chrome on macOS sends
_EXTRA_HEADERS = {
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}

# Chromium launch flags that reduce automation fingerprinting
_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-renderer-backgrounding",
    "--disable-backgrounding-occluded-windows",
    "--disable-ipc-flooding-protection",
    "--disable-hang-monitor",
    "--disable-sync",
    "--force-color-profile=srgb",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-client-side-phishing-detection",
    "--disable-popup-blocking",
    "--disable-translate",
    "--disable-component-update",
    "--disable-domain-reliability",
    "--no-pings",
    "--password-store=basic",
    "--window-size=1440,900",
]


def _randomized_viewport():
    """Return a viewport with slight pixel jitter so every run looks different."""
    return {
        "width":  VIEWPORT["width"]  + random.randint(-4, 4),
        "height": VIEWPORT["height"] + random.randint(-4, 4),
    }


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
        if "expirationDate" in c:
            cookie["expires"] = int(c["expirationDate"])
        elif "expires" in c:
            cookie["expires"] = int(c["expires"])
        else:
            cookie["expires"] = -1

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
        if "login" in url or "signin" in url or "accounts.myheritage" in url:
            logger.warning("Session check: redirected to login, not authenticated")
            return False
        logged_in = await page.locator("[data-testid='user-menu'], .user-avatar, .profile-menu, #user-menu-btn").count()
        if logged_in > 0:
            logger.info("Session check: logged in (found user menu element)")
            return True
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
        args=_LAUNCH_ARGS,
    )

    viewport = _randomized_viewport()
    context = None

    # --- Strategy 1: Playwright session state ---
    if SESSION_FILE.exists():
        logger.info(f"Loading Playwright session state from {SESSION_FILE}")
        try:
            context = await browser.new_context(
                storage_state=str(SESSION_FILE),
                viewport=viewport,
                user_agent=USER_AGENT,
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                extra_http_headers=_EXTRA_HEADERS,
            )
            await context.add_init_script(_STEALTH_SCRIPT)
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
                viewport=viewport,
                user_agent=USER_AGENT,
                locale="ru-RU",
                timezone_id="Europe/Moscow",
                extra_http_headers=_EXTRA_HEADERS,
            )
            await context.add_init_script(_STEALTH_SCRIPT)
            await context.add_cookies(cookies)
            logger.info(f"Imported {len(cookies)} cookies")
        except Exception as e:
            logger.error(f"Cookie import failed: {e}")
            context = None

    # --- Strategy 3: Unauthenticated fallback ---
    if context is None:
        logger.warning("No session or cookies found — launching unauthenticated browser")
        context = await browser.new_context(
            viewport=viewport,
            user_agent=USER_AGENT,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            extra_http_headers=_EXTRA_HEADERS,
        )
        await context.add_init_script(_STEALTH_SCRIPT)

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
