"""
MyHeritage Automation Agent — entry point.

Usage:
  python main.py                        # headless, up to 200 matches
  python main.py --headless             # explicit headless mode
  python main.py --visible              # non-headless (debug)
  python main.py --max 50              # limit session to 50 matches
  python main.py --capture-session      # one-time: launch browser, log in, save session
  python main.py --dry-run              # scrape but don't click anything (future)

Auth (one-time setup):
  Option A — export cookies with EditThisCookie from Chrome, save to data/myheritage_cookies.json
  Option B — run `python main.py --capture-session`, log in in the browser window that opens,
             then close it (session saved automatically to data/myheritage_session.json).
             All future runs will use the saved session and won't need cookies.
"""

import asyncio
import sys
import argparse
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.table import Table

from config import (
    LOGS_DIR,
    MAX_MATCHES_PER_SESSION,
    SESSION_FILE,
    COOKIES_FILE,
)
from auth.browser_auth import create_browser_context, validate_and_save_session
from browser.smart_matches import run_smart_matches_session
from browser.record_matches import run_record_matches_session

console = Console()


def _setup_logging(verbose: bool = False) -> None:
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level, colorize=True,
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}")
    logger.add(
        LOGS_DIR / "agent_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="1 day",
        retention="14 days",
        encoding="utf-8",
    )


async def capture_session() -> None:
    """Launch a visible browser, wait for user to be logged in, save session."""
    from playwright.async_api import async_playwright

    console.print("[bold yellow]Session capture mode[/bold yellow]")
    console.print("A Chromium browser will open. Log into MyHeritage if needed.")
    console.print("Once logged in, come back here and press Enter to save the session.\n")

    async with async_playwright() as pw:
        context = await create_browser_context(pw, headless=False)
        page = await context.new_page()
        await page.goto("https://www.myheritage.com/my/account")
        console.print("Browser is open. Press [bold]Enter[/bold] when you're logged in…")
        await asyncio.get_event_loop().run_in_executor(None, input)
        is_auth = await validate_and_save_session(context)
        if is_auth:
            console.print(f"[green]✓ Session saved to {SESSION_FILE}[/green]")
        else:
            console.print("[red]✗ Not authenticated — session not saved[/red]")
        await context.close()


async def run(headless: bool, max_matches: int, verbose: bool, record_matches: bool = False) -> None:
    from playwright.async_api import async_playwright

    mode = "Record Matches" if record_matches else "Smart Matches"
    console.print(f"[bold]MyHeritage Agent[/bold] | mode={mode} | headless={headless} | max={max_matches}")

    if not SESSION_FILE.exists() and not COOKIES_FILE.exists():
        console.print(
            "[red]No auth found![/red] Run one of:\n"
            "  python main.py --capture-session   (recommended)\n"
            "  — or —\n"
            "  Export cookies from Chrome with EditThisCookie → save to data/myheritage_cookies.json"
        )
        sys.exit(1)

    async with async_playwright() as pw:
        context = await create_browser_context(pw, headless=headless)
        is_auth = await validate_and_save_session(context)

        if not is_auth:
            console.print(
                "[red]Authentication failed.[/red] Your session may have expired.\n"
                "Run: python main.py --capture-session"
            )
            await context.close()
            sys.exit(1)

        console.print("[green]✓ Authenticated[/green]")
        page = await context.new_page()

        if record_matches:
            summary = await run_record_matches_session(
                page=page,
                max_matches=max_matches,
            )
        else:
            summary = await run_smart_matches_session(
                page=page,
                max_matches=max_matches,
            )

        await context.close()

    # Summary table
    table = Table(title="Session Summary")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("People processed", str(summary.get("people", 0)))
    table.add_row("Matches processed", str(summary.get("processed", 0)))
    table.add_row("✓ Confirmed + saved", str(summary.get("ok", 0)))
    table.add_row("⚠ Skipped", str(summary.get("skip", 0)))
    table.add_row("✗ Errors", str(summary.get("error", 0)))
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="MyHeritage automation agent")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="Run in headless mode (default: True)")
    parser.add_argument("--visible", action="store_true",
                        help="Run with visible browser window (overrides --headless)")
    parser.add_argument("--max", type=int, default=MAX_MATCHES_PER_SESSION,
                        help=f"Max matches per session (default: {MAX_MATCHES_PER_SESSION})")
    parser.add_argument("--capture-session", action="store_true",
                        help="One-time: open browser, log in, save session")
    parser.add_argument("--record-matches", action="store_true",
                        help="Process Record Matches (matchType=1) instead of Smart Matches")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Debug logging")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    if args.capture_session:
        asyncio.run(capture_session())
        return

    headless = not args.visible
    asyncio.run(run(headless=headless, max_matches=args.max, verbose=args.verbose, record_matches=args.record_matches))


if __name__ == "__main__":
    main()
