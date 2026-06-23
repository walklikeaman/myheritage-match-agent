"""
Parse GEDCOM → family graph.
Finds: all individuals, direct ancestors of @I1@ (Nikita),
VIP surnames (Ганущинер, Рассадина/Разсадина variants), outputs summary.
Usage: python3 gedcom_graph.py [path/to/file.ged]
"""
import re
import sys
import json
from pathlib import Path
from collections import defaultdict

GED = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Users/walklikeaman/Downloads/es268m_8996013ay311i66aec9fh8_A.ged")
ROOT_ID = "@I1@"  # Nikita Nakonechnyi

# ── GEDCOM parser ─────────────────────────────────────────────
persons = {}   # id -> {name, givn, surn, sex, birth_date, birth_place, death_date, famc, fams}
families = {}  # id -> {husb, wife, children}

cur_id = cur_type = None
cur = {}
cur_tag = None  # track last level-1 tag for level-2 context

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

# ── Ancestor traversal from Nikita (@I1@) ─────────────────────
ancestors = {}  # id -> generation (1=parents, 2=grandparents …)

def find_ancestors(pid, gen=1, visited=None):
    if visited is None:
        visited = set()
    if pid in visited or gen > 20:
        return
    visited.add(pid)
    p = persons.get(pid, {})
    for fam_id in p.get("famc", []):
        fam = families.get(fam_id, {})
        for parent_key in ("husb", "wife"):
            par = fam.get(parent_key)
            if par and par not in ancestors:
                ancestors[par] = gen
                find_ancestors(par, gen + 1, visited)

find_ancestors(ROOT_ID)
print(f"Direct ancestors found: {len(ancestors)}")

# ── VIP surname search ─────────────────────────────────────────
VIP = {
    "Ганущинер": re.compile(
        r"[Гг]анн?у[щш][иi]н[еeё]р|Gann?u[sc]h?ch?in[eo]r|Hann?u[sc]h?ch?in[eo]r",
        re.I),
    "Рассадина": re.compile(
        r"[Рр][аaоo]зс?с?[аa]ди[нн]?[аоыий]?"   # Разсадина (старая орф.), Рассадина, Росадина
        r"|[Рр]озс?[аa]ди[нн]?[аоыий]?"           # Розсадина (укр.)
        r"|R[oa]ss?adi[nн][aoiy]?"                 # Rassadin(a), Rosadin(a)
        r"|Rozs?adi[nн][aoiy]?",                   # Rozsadina
        re.I),
}

vip_hits = defaultdict(list)
for pid, p in persons.items():
    full = f"{p.get('name','')} {p.get('givn','')} {p.get('surn','')}"
    for label, rx in VIP.items():
        if rx.search(full):
            gen = ancestors.get(pid)
            is_anc = gen is not None
            vip_hits[label].append({
                "id": pid, "name": p.get("name","?"),
                "birth": p.get("birth_date",""),
                "place": p.get("birth_place",""),
                "generation": gen,
                "is_direct_ancestor": is_anc,
            })

# ── Ancestor name table (first 8 gens) ────────────────────────
gen_labels = {1:"Parents",2:"Grandparents",3:"Great-grandparents",
              4:"2× Great",5:"3× Great",6:"4× Great",7:"5× Great",8:"6× Great"}

print("\n=== DIRECT ANCESTORS (gen 1–8) ===")
for pid, gen in sorted(ancestors.items(), key=lambda x: x[1]):
    if gen > 8:
        continue
    p = persons[pid]
    print(f"  Gen{gen} [{gen_labels.get(gen,'')}] {p.get('name','?')}  "
          f"b.{p.get('birth_date','')}  {p.get('birth_place','')[:40]}")

print("\n=== VIP SURNAME HITS IN TREE ===")
for label, hits in vip_hits.items():
    print(f"\n[{label}] — {len(hits)} person(s):")
    for h in hits:
        flag = "★ DIRECT ANCESTOR gen=" + str(h["generation"]) if h["is_direct_ancestor"] else "  collateral"
        print(f"  {flag}  {h['name']}  b.{h['birth']}  {h['place'][:40]}  {h['id']}")

# ── Save compact graph for agent use ──────────────────────────
out = {
    "root": ROOT_ID,
    "root_name": persons.get(ROOT_ID, {}).get("name", ""),
    "total_persons": len(persons),
    "total_families": len(families),
    "ancestors": {pid: {"gen": g, "name": persons[pid].get("name",""),
                        "birth": persons[pid].get("birth_date",""),
                        "surn": persons[pid].get("surn","")}
                  for pid, g in ancestors.items()},
    "vip_hits": {k: v for k, v in vip_hits.items()},
}

out_path = Path("/Users/walklikeaman/GitHub/My Heritage/data/family_graph.json")
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(f"\n✓ Graph saved → {out_path}  ({out_path.stat().st_size//1024}KB)")
