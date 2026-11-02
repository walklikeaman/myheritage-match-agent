"""
Publish the family graph to the NAS so the document archive and other agents can read it.

Writes to OzzyNAS (Synology), share Archive:
  Родословная/граф/persons.json      one record per wiki/people page: gedcom id, name, dates,
                                     generation, parents/spouses/children, documents folder
  Родословная/граф/family_graph.json copy of data/family_graph.json (GEDCOM ancestors + harvested)
  Родословная/граф/people/*.md       copy of wiki/people (the Obsidian graph pages)
  Родословная/граф/README.md         what lives here and who writes it
  Документы/Родственники/_index.json  folder -> gedcom id -> relation, for the archive side

The documents themselves live in Документы/Родственники/<page name>/ — one folder per person,
named exactly like the wiki page, so a page and its documents share a key.

Run by scripts/mh_runner_smart.sh after every session; safe to run by hand:
  python3 nas_export.py            # publish
  python3 nas_export.py --dry-run  # build persons.json locally, no NAS
"""
import argparse
import io
import json
import re
import subprocess
import sys
import tarfile
import time
import unicodedata
from pathlib import Path

from config import BASE_DIR, DATA_DIR

PEOPLE_DIR = BASE_DIR / "wiki" / "people"
GRAPH_FILE = DATA_DIR / "family_graph.json"
NAS_HOST = "ozzynas"                              # ~/.ssh/config alias (user nikita-admin, key auth)
NAS_ADDRS = ["192.168.1.161", "100.97.72.100"]    # LAN first, then Tailscale
GRAPH_DIR = "/volume1/Archive/Родословная/граф"
RELATIVES_DIR = "/volume1/Archive/Документы/Родственники"
ROOT_ID = "@I1@"

LINK = re.compile(r"\[\[([^\]]+)\]\]")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def field(text: str, name: str) -> str:
    m = re.search(rf'^{name}: "?([^"\n]*)"?$', text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def parse_page(path: Path) -> dict | None:
    text = nfc(path.read_text(encoding="utf-8"))
    gid = field(text, "gedcom_id")
    if not gid:
        return None
    label = re.search(r"^> (.+)$", text, re.MULTILINE)
    parents, spouses, children = [], [], []
    section = None
    for line in text.splitlines():
        if line.startswith("## Родители"):
            section = parents
        elif line.startswith("## Супруг"):
            spouses += LINK.findall(line)
            section = None
        elif line.startswith("### Дети"):
            section = children
        elif line.startswith("#"):
            section = None
        elif section is not None and line.startswith("- "):
            section += LINK.findall(line) or [line[2:].strip()]
    return {
        "gedcom_id": gid,
        "name": nfc(path.stem),
        "sex": field(text, "sex"),
        "birth": field(text, "birth_date"),
        "birth_place": field(text, "birth_place"),
        "death": field(text, "death_date"),
        "generation": label.group(1) if label else "",
        "parents": parents,
        "spouses": spouses,
        "children": children,
    }


def ssh(cmd: str, stdin: bytes | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    last = None
    for addr in NAS_ADDRS:
        last = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", f"HostName={addr}", NAS_HOST, cmd],
            input=stdin, capture_output=True, timeout=timeout, check=False)
        if last.returncode != 255:      # 255 = could not connect; anything else came from the NAS
            return last
    return last


def documents_on_nas() -> dict[str, int]:
    """Folder name -> file count under Документы/Родственники."""
    r = ssh(f"cd '{RELATIVES_DIR}' 2>/dev/null && for d in */; do "
            f"printf '%s\\t%s\\n' \"${{d%/}}\" \"$(find \"$d\" -type f ! -path '*@eaDir*' | wc -l)\"; done")
    out = {}
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        if "\t" in line:
            name, n = line.rsplit("\t", 1)
            out[nfc(name)] = int(n.strip() or 0)
    return out


def build(docs: dict[str, int]) -> list[dict]:
    persons = [p for p in (parse_page(f) for f in sorted(PEOPLE_DIR.glob("*.md")) if not f.name.startswith("_")) if p]
    by_name = {p["name"]: p["gedcom_id"] for p in persons}
    for p in persons:
        for key in ("parents", "spouses", "children"):
            p[key] = [{"name": n, "gedcom_id": by_name.get(n)} for n in p[key]]
        if p["gedcom_id"] == ROOT_ID:
            p["documents_folder"], p["documents"] = "Документы/Я", None
        elif p["name"] in docs:
            p["documents_folder"], p["documents"] = f"Документы/Родственники/{p['name']}", docs[p["name"]]
    return persons


def tar_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size, info.mtime = len(data), int(time.time())
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


README = """# Граф родственников

Эту папку пишет проект My Heritage (`~/GitHub/My Heritage/nas_export.py`) после каждой сессии.
Руками здесь ничего не меняйте: следующая выгрузка перезапишет файлы.

- `persons.json` — люди из графа: GEDCOM-ID, имя, даты, колено, родители, супруги, дети,
  и папка с документами в `Archive/Документы/Родственники/` (если она есть).
- `family_graph.json` — полный граф из GEDCOM и найденные на MyHeritage люди.
- `people/` — страницы людей (Obsidian), по одной на человека.

Имя папки с документами = имя страницы человека. Так страница и документы связаны.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="write persons.json to data/ only")
    args = ap.parse_args()

    docs = {} if args.dry_run else documents_on_nas()
    persons = build(docs)
    persons_json = json.dumps({"updated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "root": ROOT_ID,
                               "persons": persons}, ensure_ascii=False, indent=1).encode("utf-8")
    if args.dry_run:
        (DATA_DIR / "persons.json").write_bytes(persons_json)
        print(f"dry run: {len(persons)} persons → {DATA_DIR / 'persons.json'}")
        return 0

    files = {"persons.json": persons_json, "README.md": README.encode("utf-8")}
    if GRAPH_FILE.exists():
        files["family_graph.json"] = GRAPH_FILE.read_bytes()
    for page in PEOPLE_DIR.glob("*.md"):
        files[f"people/{nfc(page.name)}"] = page.read_bytes()
    # publish into a fresh dir, then swap, so readers never see a half-written graph
    r = ssh(f"set -e; mkdir -p '{GRAPH_DIR}'; rm -rf '{GRAPH_DIR}.new'; mkdir '{GRAPH_DIR}.new'; "
            f"tar -xf - -C '{GRAPH_DIR}.new'; rm -rf '{GRAPH_DIR}.old'; mv '{GRAPH_DIR}' '{GRAPH_DIR}.old'; "
            f"mv '{GRAPH_DIR}.new' '{GRAPH_DIR}'; rm -rf '{GRAPH_DIR}.old'", stdin=tar_bytes(files))
    if r.returncode:
        print(f"[nas_export] graph upload failed: {r.stderr.decode('utf-8', 'replace').strip()}", file=sys.stderr)
        return 1

    index = [{"folder": p["name"], "gedcom_id": p["gedcom_id"], "generation": p["generation"],
              "birth": p["birth"], "death": p["death"], "documents": p["documents"]}
             for p in persons if p.get("documents")]
    known = {p["name"] for p in persons}
    index += [{"folder": n, "gedcom_id": None, "generation": "нет в графе", "documents": c}
              for n, c in sorted(docs.items()) if n not in known and not n.startswith("_")]
    r = ssh(f"cat > '{RELATIVES_DIR}/_index.json'",
            stdin=json.dumps(index, ensure_ascii=False, indent=1).encode("utf-8"))
    print(f"[nas_export] {len(persons)} persons, {len(files) - 3} files → {GRAPH_DIR}; "
          f"{sum(1 for i in index if i['gedcom_id'])} relatives with documents linked")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
