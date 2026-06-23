"""
MyHeritage Automation Agent — entry point.

Usage:
  python main.py                     # combined mode: SM then RM per person, largest families first
  python main.py --smart-only        # Smart Matches only
  python main.py --record-only       # Record Matches only
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
)
from browser.record_matches import run_record_matches_session

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


async def capture_session() -> None:
    from playwright.async_api import async_playwright
    console.print("[bold yellow]Session capture mode[/bold yellow]")
    console.print("A Chromium window will open. Log into MyHeritage, then come back.\n")
    async with async_playwright() as pw:
        context = await create_browser_context(pw, headless=False)
        page = await context.new_page()
        await page.goto("https://www.myheritage.com/my/account")
        console.print("Press [bold]Enter[/bold] when you're logged in…")
        await asyncio.get_event_loop().run_in_executor(None, input)
        is_auth = await validate_and_save_session(context)
        console.print(f"[green]✓ Session saved[/green]" if is_auth else "[red]✗ Not authenticated[/red]")
        await context.close()


async def run(mode: str, headless: bool, max_matches: int, scroll_rounds: int) -> None:
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
            summary = await run_smart_matches_session(page, max_matches=max_matches, scroll_rounds=scroll_rounds)
        else:  # record
            summary = await run_record_matches_session(page, max_matches=max_matches)

        await context.close()

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
    parser.add_argument("--capture-session", action="store_true", help="One-time auth setup")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    _setup_logging(args.verbose)

    if args.capture_session:
        asyncio.run(capture_session())
        return

    if args.smart_only:
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
    ))


if __name__ == "__main__":
    main()
