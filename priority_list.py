"""
Priority list for manual match confirmation.

Read-only: fetches the pending Smart Matches people list (no confirm clicks,
so it doesn't touch the WAF-sensitive action) and cross-references against
data/family_graph.json's direct-ancestor and VIP-surname records, so manual
work in a real browser can be spent on the highest-value people first.

Usage: python3 priority_list.py [--top 50]
"""

import argparse
import asyncio
import json
import re
import sys

from playwright.async_api import async_playwright

from auth.browser_auth import create_browser_context
from browser.smart_matches import get_people_sorted_by_count
from config import DATA_DIR

VIP_PATTERNS = [
    re.compile(r"ганн?ущинер", re.IGNORECASE),
    re.compile(r"ганушинер", re.IGNORECASE),
    re.compile(r"gan(n)?ushchiner", re.IGNORECASE),
    re.compile(r"hanushchiner", re.IGNORECASE),
    re.compile(r"расс?адин", re.IGNORECASE),
    re.compile(r"розсадин", re.IGNORECASE),
    re.compile(r"rassadina|rossadina|rozsadina", re.IGNORECASE),
]


def _load_ancestor_names() -> set[str]:
    graph = json.loads((DATA_DIR / "family_graph.json").read_text())
    names = set()
    for person in graph.get("ancestors", {}).values():
        name = person.get("name", "").strip()
        if name:
            names.add(name)
    return names


def _is_vip(name: str) -> bool:
    return any(p.search(name) for p in VIP_PATTERNS)


def _is_ancestor_match(name: str, ancestor_names: set[str]) -> bool:
    # crude but effective: share last name token, since MyHeritage match names
    # are the OTHER tree's person, not literally our ancestor's own name
    name_tokens = set(name.lower().split())
    for anc in ancestor_names:
        anc_tokens = set(anc.lower().split())
        if name_tokens & anc_tokens:
            return True
    return False


async def main(top: int) -> None:
    ancestor_names = _load_ancestor_names()

    async with async_playwright() as p:
        context = await create_browser_context(p, headless=True)
        page = await context.new_page()
        people = await get_people_sorted_by_count(page, match_type=2, scroll_rounds=8)
        await context.close()

    for person in people:
        person["vip"] = _is_vip(person["name"])
        person["ancestor_hint"] = _is_ancestor_match(person["name"], ancestor_names)

    people.sort(key=lambda p: (not p["vip"], not p["ancestor_hint"], -p["count"]))

    out_path = DATA_DIR / "priority_list.md"
    lines = [
        "# Priority list — manual Smart Match review",
        "",
        f"Generated from {len(people)} pending people, sorted VIP surname > ancestor-name hint > match count.",
        "",
        "| # | Name | Pending matches | VIP | Ancestor hint |",
        "|---|------|-----------------|-----|----------------|",
    ]
    for i, p in enumerate(people[:top], 1):
        lines.append(
            f"| {i} | {p['name']} | {p['count']} | "
            f"{'🔴' if p['vip'] else ''} | {'⭐' if p['ancestor_hint'] else ''} |"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path} ({min(top, len(people))} of {len(people)} people)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(main(args.top))
