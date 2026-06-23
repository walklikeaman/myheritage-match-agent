"""
Phase 1 Reconnaissance Script

Logs into MyHeritage via saved session/cookies, navigates to match pages,
takes screenshots, saves HTML, and attempts to identify key CSS selectors.

Run this BEFORE writing any automation code. Output goes to recon/ directory.

Usage:
    python recon.py                  # Recon all pages
    python recon.py --page smart     # Only Smart Matches
    python recon.py --page record    # Only Record Matches
"""

import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright, Page
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from config import SMART_MATCHES_URL, RECORD_MATCHES_URL, DISCOVERIES_URL
from auth.browser_auth import create_browser_context, validate_and_save_session

console = Console()
RECON_DIR = Path("recon")
RECON_DIR.mkdir(exist_ok=True)


# Candidate selectors to probe — we'll check which ones exist on the page.
# These are educated guesses; recon will tell us which are real.
SELECTOR_CANDIDATES = {
    "match_card": [
        ".match-card",
        ".discovery-card",
        "[data-testid='match-card']",
        "[data-testid='discovery-card']",
        ".smart-match-card",
        ".candidate-card",
        "[class*='MatchCard']",
        "[class*='match-card']",
        "[class*='SmartMatch']",
        ".comparison-card",
    ],
    "confidence_score": [
        ".confidence-score",
        ".match-score",
        "[data-testid='confidence']",
        "[class*='confidence']",
        "[class*='score']",
        ".match-percentage",
        "[class*='percentage']",
        "[class*='Confidence']",
        "[aria-label*='%']",
        "[title*='%']",
    ],
    "person_name": [
        ".person-name",
        ".match-person-name",
        "[data-testid='person-name']",
        "[class*='PersonName']",
        "[class*='person-name']",
        "h2[class*='name']",
        "h3[class*='name']",
    ],
    "new_info_badge": [
        ".new-info-badge",
        ".new-info",
        "[data-testid='new-info']",
        "[class*='new-info']",
        "[class*='NewInfo']",
        "[class*='badge']",
        ".additions-count",
    ],
    "confirm_button": [
        "button[data-testid='confirm']",
        "button[data-testid='accept']",
        "button[class*='confirm']",
        "button[class*='Confirm']",
        ".confirm-btn",
        ".accept-btn",
        "button:has-text('Confirm')",
        "button:has-text('Accept')",
        "a:has-text('Confirm')",
    ],
    "review_match_button": [
        "button:has-text('Review')",
        "a:has-text('Review')",
        "[data-testid='review-match']",
        "[class*='review-btn']",
        "[class*='ReviewBtn']",
    ],
    "pagination_next": [
        "button[aria-label='Next page']",
        ".pagination-next",
        "[data-testid='next-page']",
        "a[rel='next']",
        ".next-page",
        "[class*='pagination'] button:last-child",
    ],
    "match_count": [
        ".matches-count",
        "[data-testid='matches-count']",
        "[class*='count']",
        "h1[class*='count']",
        "[class*='total']",
    ],
}


async def probe_selectors(page: Page, page_name: str) -> dict:
    """Check which candidate selectors exist on the current page."""
    results = {}
    for element_name, candidates in SELECTOR_CANDIDATES.items():
        found = []
        for selector in candidates:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    found.append({"selector": selector, "count": count})
            except Exception:
                pass
        results[element_name] = found

    # Save results
    output_file = RECON_DIR / f"{page_name}_selectors.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Selector probe saved to {output_file}")

    return results


async def extract_accessibility_tree(page: Page, page_name: str):
    """Dump the accessibility tree for deeper analysis."""
    try:
        snapshot = await page.accessibility.snapshot()
        output_file = RECON_DIR / f"{page_name}_accessibility.json"
        with open(output_file, "w") as f:
            json.dump(snapshot, f, indent=2)
        logger.info(f"Accessibility tree saved to {output_file}")
    except Exception as e:
        logger.warning(f"Could not extract accessibility tree: {e}")


async def extract_match_data_sample(page: Page, page_name: str):
    """
    Try to extract text content from whatever match cards are visible.
    This gives us a sample of the data structure even before we know the right selectors.
    """
    sample_data = []

    # Try all candidate match card selectors
    for selector in SELECTOR_CANDIDATES["match_card"]:
        try:
            cards = page.locator(selector)
            count = await cards.count()
            if count > 0:
                logger.info(f"Found {count} elements with selector: {selector}")
                for i in range(min(3, count)):  # Sample first 3
                    card = cards.nth(i)
                    text = await card.inner_text()
                    html = await card.inner_html()
                    sample_data.append({
                        "selector": selector,
                        "index": i,
                        "text": text[:500],
                        "html_snippet": html[:1000],
                    })
                break
        except Exception:
            pass

    if sample_data:
        output_file = RECON_DIR / f"{page_name}_match_samples.json"
        with open(output_file, "w") as f:
            json.dump(sample_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Match samples saved to {output_file}")
    else:
        logger.warning("Could not find any match cards — page may need scrolling or be empty")

    return sample_data


async def recon_page(page: Page, url: str, page_name: str):
    """Full reconnaissance of a single page."""
    console.print(f"\n[bold cyan]Reconning: {url}[/bold cyan]")

    # Navigate
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(3)  # Let React render

    # Screenshot
    screenshot_file = RECON_DIR / f"{page_name}_01_initial.png"
    await page.screenshot(path=str(screenshot_file), full_page=False)
    console.print(f"[green]Screenshot:[/green] {screenshot_file}")

    # Scroll down to trigger lazy loading
    await page.evaluate("window.scrollTo(0, 500)")
    await asyncio.sleep(2)
    screenshot_file2 = RECON_DIR / f"{page_name}_02_scrolled.png"
    await page.screenshot(path=str(screenshot_file2), full_page=False)

    # Full page HTML
    html = await page.content()
    html_file = RECON_DIR / f"{page_name}.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    console.print(f"[green]HTML saved:[/green] {html_file} ({len(html):,} bytes)")

    # Probe selectors
    selector_results = await probe_selectors(page, page_name)

    # Accessibility tree
    await extract_accessibility_tree(page, page_name)

    # Sample match data
    samples = await extract_match_data_sample(page, page_name)

    # Print selector summary
    table = Table(title=f"Selector Probe Results — {page_name}")
    table.add_column("Element", style="cyan")
    table.add_column("Found Selectors", style="green")
    table.add_column("Count")

    for element_name, found in selector_results.items():
        if found:
            selectors_str = "\n".join(f['selector'] for f in found[:2])
            counts_str = "\n".join(str(f['count']) for f in found[:2])
            table.add_row(element_name, selectors_str, counts_str)
        else:
            table.add_row(element_name, "[red]NOT FOUND[/red]", "-")

    console.print(table)

    # Current page URL (may have redirected)
    final_url = page.url
    if final_url != url:
        console.print(f"[yellow]Redirected to:[/yellow] {final_url}")

    return {
        "url": url,
        "final_url": final_url,
        "selectors": selector_results,
        "match_samples": len(samples),
        "html_size": len(html),
    }


async def run_recon(pages: list[str]):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    console.print(Panel(
        f"[bold]MyHeritage Reconnaissance[/bold]\n"
        f"Timestamp: {timestamp}\n"
        f"Output: {RECON_DIR.absolute()}",
        title="Phase 1"
    ))

    async with async_playwright() as playwright:
        context = await create_browser_context(playwright, headless=False)
        is_auth = await validate_and_save_session(context)

        if not is_auth:
            console.print(Panel(
                "[red]Not authenticated![/red]\n\n"
                "Steps to fix:\n"
                "1. Log into MyHeritage in Chrome\n"
                "2. Install EditThisCookie extension\n"
                "3. Export cookies as JSON\n"
                f"4. Save to: [bold]{Path('data/myheritage_cookies.json').absolute()}[/bold]\n"
                "5. Re-run this script",
                title="Authentication Required",
                border_style="red"
            ))
            await playwright.stop()
            return

        console.print("[green]✓ Authenticated[/green]")
        page = await context.new_page()

        # Enable request logging for debugging
        async def log_request(req):
            if "myheritage.com/api" in req.url or "familygraph" in req.url:
                logger.debug(f"API call: {req.method} {req.url}")

        page.on("request", log_request)

        results = {}

        page_map = {
            "smart": (SMART_MATCHES_URL, "smart_matches"),
            "record": (RECORD_MATCHES_URL, "record_matches"),
            "discoveries": (DISCOVERIES_URL, "discoveries"),
        }

        for page_key in pages:
            if page_key in page_map:
                url, name = page_map[page_key]
                try:
                    result = await recon_page(page, url, name)
                    results[page_key] = result
                except Exception as e:
                    logger.error(f"Recon failed for {page_key}: {e}")
                    results[page_key] = {"error": str(e)}
                await asyncio.sleep(5)

        # Save full recon summary
        summary_file = RECON_DIR / f"summary_{timestamp}.json"
        with open(summary_file, "w") as f:
            json.dump(results, f, indent=2)

        console.print(Panel(
            f"[bold green]Recon complete![/bold green]\n\n"
            f"Files in {RECON_DIR}/:\n"
            + "\n".join(f"  • {p.name}" for p in sorted(RECON_DIR.iterdir())),
            title="Done"
        ))

        await playwright.stop()


def main():
    parser = argparse.ArgumentParser(description="MyHeritage Reconnaissance Script")
    parser.add_argument(
        "--page",
        choices=["smart", "record", "discoveries", "all"],
        default="all",
        help="Which page(s) to recon",
    )
    args = parser.parse_args()

    if args.page == "all":
        pages = ["discoveries", "smart", "record"]
    else:
        pages = [args.page]

    asyncio.run(run_recon(pages))


if __name__ == "__main__":
    main()
