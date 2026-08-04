"""
MyHeritage Automation Agent — entry point.

Usage:
  python main.py                     # combined mode: SM then RM per person, largest families first
  python main.py --smart-only        # Smart Matches only
  python main.py --record-only       # Record Matches only
  python main.py --extract-confirmed # extract data from already-confirmed Smart Matches
                                      # (e.g. matches bulk-confirmed via "Совпадения по
                                      # источнику" that never got their data pulled in)
  python main.py --confirm-by-source # bulk-confirm whole source trees at once (no per-match
                                      # wizard, hasn't triggered the WAF in testing); use
                                      # --max-sources to cap how many trees per session
  python main.py --visible           # non-headless (debug)
  python main.py --max 50            # limit session to 50 matches
  python main.py --scroll 15         # scroll rounds to load people list (default: 8)
  python main.py --capture-session   # one-time: launch browser, log in, save session

Auth (one-time setup):
  Run `python main.py --capture-session` — a Chromium window opens, log in,
  session is auto-detected and saved to data/myheritage_session.json.
  All future runs use the saved session (fully headless).
"""

import asyncio
import sys
import argparse

from loguru import logger
from rich.console import Console
from rich.table import Table

from config import LOGS_DIR, MAX_MATCHES_PER_SESSION, SESSION_FILE, COOKIES_FILE
from auth.browser_auth import create_browser_context, validate_and_save_session
from browser.smart_matches import (
    run_smart_matches_session,
    run_combined_session,
    run_extract_confirmed_session,
)
from browser.record_matches import run_record_matches_session
from browser.source_confirm import run_bulk_source_confirm_session

console = Console()


def _setup_logging(verbose: bool = False) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level, colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}")
    logger.add(
        LOGS_DIR / "agent_{time:YYYY-MM-DD}.log",
        level="DEBUG", rotation="1 day", retention="14 days", encoding="utf-8",
    )


TREE_ID = "OYYV6BL4NPB77IAKQQ65RX6Q4GAV5KA"
_DISCOVERY_URL = (
    f"https://www.myheritage.com/discovery-hub/{TREE_ID}"
    "/matches-by-people?matchType=2&matchStatus=32&lang=RU"
)


async def capture_session() -> None:
    from playwright.async_api import async_playwright
    from auth.browser_auth import _STEALTH_SCRIPT, _EXTRA_HEADERS, _LAUNCH_ARGS, _randomized_viewport
    from config import USER_AGENT

    console.print("[bold yellow]Session capture mode — FRESH start (no old cookies)[/bold yellow]")
    console.print(
        "A Chromium window will open with a clean browser profile.\n"
        "1. Log into MyHeritage (email + password).\n"
        "2. Wait until the Smart Matches list is [bold]fully loaded[/bold] — people cards visible.\n"
        "3. Come back here and press [bold]Enter[/bold].\n"
    )
    async with async_playwright() as pw:
        # Start completely fresh — no existing cookies/session so WAF (Incapsula)
        # issues fresh un-flagged tracking cookies for this headless fingerprint.
        browser = await pw.chromium.launch(headless=False, args=_LAUNCH_ARGS)
        context = await browser.new_context(
            viewport=_randomized_viewport(),
            user_agent=USER_AGENT,
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            extra_http_headers=_EXTRA_HEADERS,
        )
        await context.add_init_script(_STEALTH_SCRIPT)

        page = await context.new_page()
        await page.goto(_DISCOVERY_URL, wait_until="domcontentloaded", timeout=30000)
        console.print(f"[dim]Opened: {page.url}[/dim]")
        console.print("Press [bold]Enter[/bold] when the matches list is visible and you're logged in…")
        await asyncio.get_event_loop().run_in_executor(None, input)

        final_url = page.url
        if "discovery-hub" in final_url:
            await context.storage_state(path=str(SESSION_FILE))
            console.print(f"[green]✓ Session saved — matches page confirmed[/green]")
        else:
            console.print(f"[yellow]⚠ Still on: {final_url}[/yellow]")
            console.print("Saving anyway — try running main.py to see if it works.")
            await context.storage_state(path=str(SESSION_FILE))
        await context.close()


async def run(
    mode: str, headless: bool, max_matches: int, scroll_rounds: int,
    wait_for_captcha: bool = False, max_sources: int = 5,
) -> None:
    from playwright.async_api import async_playwright

    console.print(f"[bold]MyHeritage Agent[/bold] | mode={mode} | headless={headless} | max={max_matches} | scroll={scroll_rounds}")

    if not SESSION_FILE.exists() and not COOKIES_FILE.exists():
        console.print("[red]No auth found![/red] Run: python main.py --capture-session")
        sys.exit(1)

    async with async_playwright() as pw:
        context = await create_browser_context(pw, headless=headless)
        is_auth = await validate_and_save_session(context)
        if not is_auth:
            console.print("[red]Auth failed.[/red] Run: python main.py --capture-session")
            await context.close()
            sys.exit(1)

        console.print("[green]✓ Authenticated[/green]")
        page = await context.new_page()

        if mode == "combined":
            summary = await run_combined_session(page, max_matches=max_matches, scroll_rounds=scroll_rounds)
        elif mode == "smart":
            summary = await run_smart_matches_session(
                page, max_matches=max_matches, scroll_rounds=scroll_rounds,
                wait_for_captcha=wait_for_captcha,
            )
        elif mode == "extract_confirmed":
            summary = await run_extract_confirmed_session(
                page, max_matches=max_matches, scroll_rounds=scroll_rounds,
                wait_for_captcha=wait_for_captcha,
            )
        elif mode == "confirm_by_source":
            summary = await run_bulk_source_confirm_session(page, max_sources=max_sources)
        else:  # record
            summary = await run_record_matches_session(page, max_matches=max_matches)

        await context.close()

    if mode == "confirm_by_source":
        table = Table(title="Session Summary")
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")
        table.add_row("Source trees processed", str(summary.get("sources_processed", 0)))
        table.add_row("✓ Confirmed", str(summary.get("ok", 0)))
        table.add_row("⚠ Skipped", str(summary.get("skip", 0)))
        table.add_row("✗ Errors", str(summary.get("error", 0)))
        table.add_row("Matches reported (pre-confirm counts)", str(summary.get("total_reported", 0)))
        if summary.get("aborted") == "captcha":
            table.add_row("⛔ Blocked (reCAPTCHA)", str(summary.get("blocked", 0)))
        console.print(table)
        return

    table = Table(title="Session Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("People processed", str(summary.get("people", 0)))
    table.add_row("Matches processed", str(summary.get("processed", 0)))
    table.add_row("✓ Confirmed + saved", str(summary.get("ok", 0)))
    if "smart_ok" in summary:
        table.add_row("  · Smart Matches", str(summary.get("smart_ok", 0)))
        table.add_row("  · Record Matches", str(summary.get("record_ok", 0)))
    table.add_row("⚠ Skipped", str(summary.get("skip", 0)))
    table.add_row("✗ Errors", str(summary.get("error", 0)))
    if "new_fields" in summary:
        table.add_row("New fields extracted", str(summary.get("new_fields", 0)))
    if summary.get("aborted") == "captcha":
        table.add_row("⛔ Blocked (reCAPTCHA)", str(summary.get("blocked", 0)))
    elif summary.get("aborted") == "dry":
        table.add_row("Stopped early", "dry streak — likely fully covered")
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="MyHeritage automation agent")
    parser.add_argument("--visible", action="store_true", help="Non-headless browser (debug)")
    parser.add_argument("--max", type=int, default=MAX_MATCHES_PER_SESSION,
                        help=f"Max matches per session (default: {MAX_MATCHES_PER_SESSION})")
    parser.add_argument("--scroll", type=int, default=8,
                        help="Scroll rounds to load people list (default: 8, ~80-160 people)")
    parser.add_argument("--smart-only", action="store_true", help="Smart Matches only")
    parser.add_argument("--record-only", action="store_true", help="Record Matches only")
    parser.add_argument("--extract-confirmed", action="store_true",
                        help="Extract data from already-confirmed Smart Matches that "
                             "were never enriched (e.g. bulk-confirmed via source tree)")
    parser.add_argument("--confirm-by-source", action="store_true",
                        help="Bulk-confirm whole source trees at once via 'Совпадения по "
                             "источнику' instead of per-match confirmation")
    parser.add_argument("--max-sources", type=int, default=5,
                        help="Max source trees per session for --confirm-by-source (default: 5)")
    parser.add_argument("--capture-session", action="store_true", help="One-time auth setup")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    parser.add_argument("--wait-for-captcha", action="store_true",
                        help="On reCAPTCHA, pause and wait for a human to solve it in the "
                             "visible window instead of aborting (requires --visible)")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    if args.capture_session:
        asyncio.run(capture_session())
        return

    if args.wait_for_captcha and not args.visible:
        console.print("[red]--wait-for-captcha requires --visible (nothing to look at otherwise)[/red]")
        sys.exit(1)

    if args.confirm_by_source:
        mode = "confirm_by_source"
    elif args.extract_confirmed:
        mode = "extract_confirmed"
    elif args.smart_only:
        mode = "smart"
    elif args.record_only:
        mode = "record"
    else:
        mode = "combined"

    asyncio.run(run(
        mode=mode,
        headless=not args.visible,
        max_matches=args.max,
        scroll_rounds=args.scroll,
        wait_for_captcha=args.wait_for_captcha,
        max_sources=args.max_sources,
    ))


if __name__ == "__main__":
    main()
