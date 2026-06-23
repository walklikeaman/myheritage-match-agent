"""
Generate Obsidian markdown pages from GEDCOM.
Creates wiki/people/<slug>.md for:
  - All direct ancestors of Nikita
  - All Ганущинер family members
  - Their spouses and parents (for graph context)
Usage: python3 gedcom_to_obsidian.py [path/to/file.ged]
"""
import re
import sys
import json
from pathlib import Path
from collections import defaultdict

GED = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "/Users/walklikeaman/Downloads/es268m_8996013ay311i66aec9fh8_A.ged")
OUT = Path("wiki/people")
ROOT_ID = "@I1@"

# ── Parse GEDCOM ──────────────────────────────────────────────
persons = {}
families = {}

cur_id = cur_type = None
cur = {}
cur_tag = None

def flush():
    if cur_id and cur_type == "INDI":
        persons[cur_id] = dict(cur)
    elif cur_id and cur_type == "FAM":
        families[cur_id] = dict(cur)

with open(GED, encoding="utf-8", errors="replace") as f:
    for raw in f:
        line = raw.rstrip()
        if not line:
            continue
        parts = line.split(" ", 2)
        if len(parts) < 2:
            continue
        level = parts[0]
        rest = parts[1:]

        if level == "0":
            flush()
            cur = defaultdict(list)
            if len(rest) >= 2 and rest[1] in ("INDI", "FAM"):
                cur_id = rest[0]
                cur_type = rest[1]
            else:
                cur_id = cur_type = None
            cur_tag = None
        elif level == "1" and cur_id:
            tag = rest[0]
            val = rest[1] if len(rest) > 1 else ""
            cur_tag = tag
            if tag == "NAME":
                cur["name"] = val.replace("/", "").strip()
            elif tag == "GIVN":
                cur["givn"] = val
            elif tag == "SURN":
                cur["surn"] = val
            elif tag == "SEX":
                cur["sex"] = val
            elif tag == "FAMC":
                cur["famc"].append(val)
            elif tag == "FAMS":
                cur["fams"].append(val)
            elif tag == "HUSB":
                cur["husb"] = val
            elif tag == "WIFE":
                cur["wife"] = val
            elif tag == "CHIL":
                cur["children"].append(val)
        elif level == "2" and cur_id and cur_tag:
            tag = rest[0]
            val = rest[1] if len(rest) > 1 else ""
            if cur_tag == "BIRT":
                if tag == "DATE":
                    cur["birth_date"] = val
                elif tag == "PLAC":
                    cur["birth_place"] = val
            elif cur_tag == "DEAT":
                if tag == "DATE":
                    cur["death_date"] = val
                elif tag == "PLAC":
                    cur["death_place"] = val

flush()
print(f"Parsed: {len(persons):,} individuals, {len(families):,} families")

# ── Find direct ancestors ─────────────────────────────────────
ancestors = {}

def find_ancestors(pid, gen=1, visited=None):
    if visited is None:
        visited = set()
    if pid in visited or gen > 20:
        return
    visited.add(pid)
    p = persons.get(pid, {})
    for fam_id in p.get("famc", []):
        fam = families.get(fam_id, {})
        for pk in ("husb", "wife"):
            par = fam.get(pk)
            if par and par not in ancestors:
                ancestors[par] = gen
                find_ancestors(par, gen + 1, visited)

find_ancestors(ROOT_ID)

# ── Determine who to include ──────────────────────────────────
VIP_RE = re.compile(
    r"[Гг]анн?у[щш][иi]н[еeё]р"
    r"|Gann?u[sc]h?ch?in[eo]r"
    r"|[Рр][аaоo]зс?с?[аa]ди[нн]?"
    r"|R[oa]ss?adi[nн]", re.I)

include = set()
include.add(ROOT_ID)
include.update(ancestors.keys())

# Add VIP extended family + their immediate relatives
for pid, p in persons.items():
    full = f"{p.get('name','')} {p.get('surn','')}"
    if VIP_RE.search(full):
        include.add(pid)
        # parents
        for fam_id in p.get("famc", []):
            fam = families.get(fam_id, {})
            for pk in ("husb", "wife"):
                par = fam.get(pk)
                if par:
                    include.add(par)
        # children
        for fam_id in p.get("fams", []):
            fam = families.get(fam_id, {})
            include.update(fam.get("children", []))

# Add spouses of all included
for pid in list(include):
    p = persons.get(pid, {})
    for fam_id in p.get("fams", []):
        fam = families.get(fam_id, {})
        for pk in ("husb", "wife"):
            sp = fam.get(pk)
            if sp:
                include.add(sp)

print(f"Pages to generate: {len(include)}")

# ── Slug helpers ──────────────────────────────────────────────
used_slugs = {}

def make_slug(pid):
    if pid in used_slugs:
        return used_slugs[pid]
    p = persons.get(pid, {})
    name = p.get("name", "").strip() or pid
    year = ""
    bd = p.get("birth_date", "")
    m = re.search(r"\b(\d{4})\b", bd)
    if m:
        year = m.group(1)
    slug = re.sub(r'[\\/*?:"<>|#%&{}]', "", name)
    slug = slug.strip()
    if year:
        slug = f"{slug} ({year})"
    # uniquify
    base = slug
    i = 2
    while slug in used_slugs.values():
        slug = f"{base} [{i}]"
        i += 1
    used_slugs[pid] = slug
    return slug

# Pre-compute all slugs for included people
for pid in include:
    make_slug(pid)

# ── Generation label ──────────────────────────────────────────
GEN_LABEL = {
    1: "👨‍👩‍👧 Родители", 2: "👴 Дедушки/бабушки",
    3: "🧓 Прадедушки/прабабушки", 4: "4-е колено",
    5: "5-е колено", 6: "6-е колено", 7: "7-е колено",
    8: "8-е колено", 9: "9-е колено",
}

def gen_label(pid):
    g = ancestors.get(pid)
    if g:
        return GEN_LABEL.get(g, f"{g}-е колено")
    if pid == ROOT_ID:
        return "🌟 Никита (корень)"
    return "Родственник"

# ── Write pages ───────────────────────────────────────────────
OUT.mkdir(parents=True, exist_ok=True)

def link(pid):
    if pid not in include:
        p = persons.get(pid, {})
        return p.get("name", pid)
    return f"[[{make_slug(pid)}]]"

written = 0
for pid in include:
    p = persons.get(pid, {})
    slug = make_slug(pid)
    name = p.get("name", "?")
    birth_date = p.get("birth_date", "")
    birth_place = p.get("birth_place", "")
    death_date = p.get("death_date", "")
    death_place = p.get("death_place", "")
    sex = p.get("sex", "")
    surn = p.get("surn", "")
    gen = ancestors.get(pid)
    is_anc = gen is not None
    is_vip = bool(VIP_RE.search(f"{name} {surn}"))
    is_root = pid == ROOT_ID

    tags = ["genealogy"]
    if is_anc:
        tags.append("direct-ancestor")
    if is_vip:
        tags.append("vip-lineage")
    if is_root:
        tags.append("root")

    # Parents
    parents = []
    for fam_id in p.get("famc", []):
        fam = families.get(fam_id, {})
        for pk in ("husb", "wife"):
            par = fam.get(pk)
            if par:
                parents.append(par)

    # Spouses + children
    spouses_children = []
    for fam_id in p.get("fams", []):
        fam = families.get(fam_id, {})
        sp_key = "wife" if p.get("sex") == "M" else "husb"
        sp = fam.get(sp_key)
        if not sp:
            sp_key = "husb" if sp_key == "wife" else "wife"
            sp = fam.get(sp_key)
        children = fam.get("children", [])
        spouses_children.append((sp, children))

    # Build frontmatter relates_to
    relates = []
    for par in parents:
        if par in include:
            relates.append(make_slug(par))
    for sp, kids in spouses_children:
        if sp and sp in include:
            relates.append(make_slug(sp))
        for kid in kids:
            if kid in include:
                relates.append(make_slug(kid))

    lines = []
    lines.append("---")
    lines.append("type: person")
    lines.append("created: 2026-06-23")
    lines.append(f"gedcom_id: \"{pid}\"")
    if birth_date:
        lines.append(f"birth_date: \"{birth_date}\"")
    if birth_place:
        lines.append(f"birth_place: \"{birth_place}\"")
    if death_date:
        lines.append(f"death_date: \"{death_date}\"")
    if death_place:
        lines.append(f"death_place: \"{death_place}\"")
    if sex:
        lines.append(f"sex: \"{sex}\"")
    if gen:
        lines.append(f"generation: {gen}")
    if relates:
        lines.append(f"relates_to: [{', '.join(repr(r) for r in relates[:8])}]")
    lines.append(f"tags: [{', '.join(tags)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {name}")
    lines.append("")

    badge = gen_label(pid)
    if is_vip:
        badge += " · ⭐ VIP"
    lines.append(f"> {badge}")
    lines.append("")

    if birth_date or birth_place:
        b = " · ".join(filter(None, [birth_date, birth_place]))
        lines.append(f"**Рождение:** {b}")
    if death_date or death_place:
        d = " · ".join(filter(None, [death_date, death_place]))
        lines.append(f"**Смерть:** {d}")
    lines.append("")

    if parents:
        lines.append("## Родители")
        for par in parents:
            lines.append(f"- {link(par)}")
        lines.append("")

    for sp, kids in spouses_children:
        if sp:
            lines.append(f"## Супруг(а): {link(sp)}")
        if kids:
            lines.append("### Дети")
            for kid in kids:
                lines.append(f"- {link(kid)}")
        lines.append("")

    fpath = OUT / f"{slug}.md"
    fpath.write_text("\n".join(lines), encoding="utf-8")
    written += 1

# ── Index page ────────────────────────────────────────────────
idx_lines = ["---", "type: index", "tags: [genealogy, ancestors]", "---", "",
             "# Семейное дерево — прямые предки", "",
             f"Корень: [[{make_slug(ROOT_ID)}]]  |  Всего страниц: {written}", ""]

for gen_n in sorted(set(ancestors.values())):
    label = GEN_LABEL.get(gen_n, f"Колено {gen_n}")
    idx_lines.append(f"## {label}")
    for pid, g in sorted(ancestors.items(), key=lambda x: x[1]):
        if g == gen_n and pid in include:
            idx_lines.append(f"- [[{make_slug(pid)}]]")
    idx_lines.append("")

idx_lines += ["## ⭐ VIP линии", ""]
for pid in include:
    p = persons.get(pid, {})
    if VIP_RE.search(f"{p.get('name','')} {p.get('surn','')}"):
        anc_note = f" _(ген. {ancestors[pid]})_" if pid in ancestors else ""
        idx_lines.append(f"- [[{make_slug(pid)}]]{anc_note}")

(OUT / "_index.md").write_text("\n".join(idx_lines), encoding="utf-8")

print(f"✓ Written {written} pages + index → {OUT}/")
