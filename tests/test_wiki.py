"""Mechanical checks for the wiki: frontmatter, index coverage, log order, links, secrets.

Run: python3 -m pytest -q tests/test_wiki.py

wiki/people/ is generated from the GEDCOM export by gedcom_to_obsidian.py (Obsidian
person pages, own _index.md), so it is excluded from the page rules below and only
checked for secrets.
"""

import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
TOP_LEVEL_SKIP = {"index.md", "log.md"}
GENERATED = {"people"}
# Gitignored, machine-local folders: links into them are fine, they just don't exist in CI.
LOCAL_ONLY = {"data", "logs", "recon", "graphify-out"}
REQUIRED = ("type", "created", "updated", "sources")
TYPES = {"concept", "source", "entity"}
SECRET = re.compile(
    r"[\w.+-]+@[\w-]+\.(ru|com|net|org|io)\b"
    r"|password\s*[:=]\s*\S+"
    r"|sk-ant-"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|\b(sessionid|incap_ses_\w+|visid_incap_\w+)\s*[:=]",
    re.IGNORECASE,
)


def pages():
    out = []
    for p in WIKI.rglob("*.md"):
        rel = p.relative_to(WIKI)
        if rel.parts[0] in GENERATED:
            continue
        if len(rel.parts) == 1 and p.name in TOP_LEVEL_SKIP:
            continue
        out.append(p)
    return sorted(out)


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, f"{path.relative_to(ROOT)}: no YAML frontmatter"
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def test_pages_have_required_frontmatter():
    for p in pages():
        fm = frontmatter(p)
        for key in REQUIRED:
            assert key in fm, f"{p.relative_to(ROOT)}: missing '{key}'"
        assert fm["type"] in TYPES, f"{p.relative_to(ROOT)}: bad type {fm['type']}"
        for key in ("created", "updated"):
            date.fromisoformat(fm[key])
        if fm.get("status") == "superseded":
            assert fm.get("superseded_by"), f"{p.relative_to(ROOT)}: superseded without superseded_by"


def test_index_lists_every_page():
    index = (WIKI / "index.md").read_text(encoding="utf-8")
    for p in pages():
        if p.parent == WIKI:  # overview.md and other top-level pages
            rel = p.name
        else:
            rel = p.relative_to(WIKI).as_posix()
        assert f"]({rel})" in index, f"wiki/index.md does not list {rel}"


def test_log_is_newest_first():
    log = (WIKI / "log.md").read_text(encoding="utf-8")
    dates = re.findall(r"^## \[(\d{4}-\d{2}-\d{2})\]", log, re.MULTILINE)
    assert dates, "wiki/log.md has no entries"
    assert dates == sorted(dates, reverse=True), "wiki/log.md must be newest-first"


def test_relative_links_resolve():
    for p in [*pages(), WIKI / "index.md", WIKI / "log.md"]:
        text = p.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
            if re.match(r"^[a-z]+:", target):
                continue
            resolved = (p.parent / target).resolve()
            try:
                if resolved.relative_to(ROOT).parts[0] in LOCAL_ONLY:
                    continue
            except (ValueError, IndexError):
                pass
            assert resolved.exists(), f"{p.relative_to(ROOT)}: broken link {target}"


def test_wikilinks_resolve():
    stems = {p.stem for p in WIKI.rglob("*.md")}
    for p in [*pages(), WIKI / "index.md"]:
        for target in re.findall(r"\[\[([^\]|#]+)", p.read_text(encoding="utf-8")):
            assert target.strip() in stems, f"{p.relative_to(ROOT)}: broken [[{target}]]"


def test_wiki_has_no_obvious_secrets():
    for p in [*WIKI.rglob("*.md")]:
        assert not SECRET.search(p.read_text(encoding="utf-8")), (
            f"{p.relative_to(ROOT)}: looks like a secret or account email"
        )
