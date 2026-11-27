"""
Sort the MyHeritage inbox that browser/inbox.py saved, prepare draft replies, and tell
Nikita only when a message needs him.

Usage (from scripts/mh_runner_smart.sh, after each session):
    python3 inbox_triage.py --notify

Input:  data/inbox.jsonl     (one record per read thread, written by browser/inbox.py)
Output: data/inbox_review.md (every thread: category, what the graph knows, a draft)
State:  data/inbox_seen.json (threads already notified)

Categories:
  system   MyHeritage's own notifications or bulk mail. No draft, no notification.
  thanks   "thank you for confirming / nice to connect". Short draft, no notification.
  kinship  asks how we are related or for help linking trees. Draft + notification.
  other    anything else from a person. Draft stub + notification.
A thread that mentions a VIP surname (notify_vip.VIP_GROUPS) always notifies.

Nothing is sent anywhere: drafts are for Nikita to approve (docs/RULES.md §3.1, §3.10).
Drafts never carry dates or places of living people; the graph facts go to the
"for Nikita only" block of the review file instead.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

INBOX_FILE = Path("data/inbox.jsonl")
REVIEW_FILE = Path("data/inbox_review.md")
SEEN_FILE = Path("data/inbox_seen.json")
GRAPH_FILE = Path("data/family_graph.json")

SYSTEM_PATTERNS = [
    r"\bMyHeritage\s+(Team|Команда)\b", r"Команда MyHeritage", r"no-?reply", r"unsubscribe",
    r"отписаться", r"\bnewsletter\b", r"рассылк", r"скидк", r"\bdiscount\b", r"\bsale\b",
    r"подписк[аиу] (истекает|продл)", r"subscription (expires|renew)",
]
KINSHIP_PATTERNS = [
    r"как (мы|вы|наши)\b.{0,40}(связан|родств|пересека)", r"(связь|родство) между",
    r"кем (вы|мне|я)\b.{0,30}(приход|являет)", r"(помогите|помочь|подскаж).{0,60}(дерев|родствен|предк|связ)",
    r"(общ(ий|ая|ие|его|ей)|наш(и|его|ей)) (предок|предки|предка|родственник|прадед|прабаб)",
    r"how (are|were) we (related|connected)", r"(our|the) (connection|relationship)",
    r"common (ancestor|relative)", r"(help|link|connect).{0,40}(tree|relative|ancestor)",
    r"related (to|through)", r"\bcousin\b", r"двоюродн|троюродн", r"родственник[аи]? по",
]
THANKS_PATTERNS = [
    r"спасибо", r"благодар", r"thank", r"рад(а)? (знакомству|связи)", r"nice to (meet|connect)",
    r"תודה",
]


def _vip_regexes() -> dict[str, re.Pattern]:
    # notify_vip.py runs its scan at import time, so copy its patterns by reading the
    # file instead of importing it (one home for the VIP spellings: notify_vip.py).
    src = Path(__file__).with_name("notify_vip.py").read_text(encoding="utf-8")
    block = src.split("VIP_GROUPS = {", 1)[1].split("\n}\n", 1)[0]
    groups: dict[str, re.Pattern] = {}
    for m in re.finditer(r'"([^"]+)":\s*\[(.*?)\],', block, re.DOTALL):
        pats = re.findall(r'r"([^"]+)"', m.group(2))
        groups[m.group(1)] = re.compile("|".join(pats), re.IGNORECASE)
    return groups


def _any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def classify(text: str) -> str:
    if _any(SYSTEM_PATTERNS, text):
        return "system"
    if _any(KINSHIP_PATTERNS, text):
        return "kinship"
    if _any(THANKS_PATTERNS, text) and len(text) < 1500:
        return "thanks"
    return "other"


def language(text: str) -> str:
    cyr = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    return "ru" if cyr >= lat else "en"


def sender_name(rec: dict) -> str:
    """Best guess at the sender's first name from the list preview's first line."""
    first = (rec.get("preview") or "").strip().splitlines()[:1]
    if not first:
        return ""
    name = re.sub(r"[^\w\s'-]", " ", first[0]).split()
    return name[0] if name and not name[0].isdigit() else ""


def _year(s: str) -> int | None:
    m = re.search(r"\b(1[5-9]\d\d|20[0-2]\d)\b", s or "")
    return int(m.group(1)) if m else None


def graph_context(text: str, graph: dict) -> list[dict]:
    """People from the tree whose surname (or full name) appears in the message."""
    hits: list[dict] = []
    words = [w.lower() for w in re.findall(r"[\w'-]{4,}", text)]
    for pid, p in (graph.get("ancestors") or {}).items():
        name = p.get("name", "")
        parts = [w.lower() for w in name.split() if len(w) >= 4]
        # Russian surnames change their ending (Разсадина / Разсадиных / Разсадину):
        # compare on the stem without the last two letters, at least 5 letters long.
        stem = parts[-1][:-2] if parts and len(parts[-1]) >= 7 else (parts[-1] if parts else "")
        if stem and any(w.startswith(stem) for w in words):
            hits.append({"id": pid, "name": name, "birth": p.get("birth", ""), "gen": p.get("gen"),
                         "source": "ancestors"})
    harvested = graph.get("harvested_people") or {}
    lowered = text.lower()
    for name in harvested:
        if len(name) >= 8 and name.lower() in lowered:
            hits.append({"name": name, "source": "harvested",
                         "sightings": harvested[name].get("sightings")})
        if len(hits) >= 15:
            break
    return hits


def _safe_fact(h: dict) -> str | None:
    """A fact allowed in a reply to a stranger: only ancestors born before 1925."""
    y = _year(h.get("birth", ""))
    if h.get("source") == "ancestors" and y and y < 1925:
        return f"{h['name']} ({y})"
    return None


def draft(category: str, lang: str, name: str, facts: list[str]) -> str:
    hi_ru = f"Здравствуйте, {name}!" if name else "Здравствуйте!"
    hi_en = f"Hello {name}," if name else "Hello,"
    if category == "thanks":
        return (f"{hi_ru}\n\nИ вам спасибо! Рад, что наши деревья нашли друг друга. "
                "Если захотите что-то уточнить про общих родственников, пишите.\n\nНикита"
                if lang == "ru" else
                f"{hi_en}\n\nThank you too! Glad our trees found each other. "
                "If you want to check anything about the relatives we share, just write.\n\nNikita")
    if category not in ("kinship", "other"):
        return ""
    known_ru = ("\n\nВ моём дереве есть: " + "; ".join(facts) + ". Возможно, связь идёт через кого-то из них."
                if facts else "")
    known_en = ("\n\nIn my tree I have: " + "; ".join(facts) + ". The link may go through one of them."
                if facts else "")
    if lang == "ru":
        return (f"{hi_ru}\n\nСпасибо, что написали. Совпадения с другими деревьями я подтверждаю через "
                "Smart Matches: MyHeritage находит одних и тех же людей в разных деревьях, а я проверяю "
                "и сохраняю эти совпадения. Поэтому вы и увидели отклик от меня."
                f"{known_ru}\n\nНапишите, через кого из ваших родственников вы видите связь (имя и примерные "
                "годы жизни), и я посмотрю в своём дереве, как мы связаны.\n\nНикита")
    return (f"{hi_en}\n\nThanks for writing. I confirm matches with other trees through Smart Matches: "
            "MyHeritage finds the same people in different trees, and I check and save those matches. "
            "That is why you saw activity from me."
            f"{known_en}\n\nIf you tell me which of your relatives you think links us (a name and rough "
            "years), I will look in my tree and tell you how we are connected.\n\nNikita")


def latest_threads(path: Path = INBOX_FILE) -> list[dict]:
    """The newest saved version of every thread, newest first."""
    by_thread: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            by_thread[rec["thread"]] = rec
    return sorted(by_thread.values(), key=lambda r: r.get("ts", ""), reverse=True)


def triage(records: list[dict], graph: dict, vip: dict[str, re.Pattern]) -> list[dict]:
    out = []
    for rec in records:
        text = rec.get("text") or rec.get("preview") or ""
        cat = classify(text)
        vip_hits = sorted(g for g, rx in vip.items() if rx.search(text))
        ctx = graph_context(text, graph) if cat in ("kinship", "other") or vip_hits else []
        facts = [f for f in (_safe_fact(h) for h in ctx) if f]
        out.append({
            **rec, "category": cat, "vip": vip_hits, "context": ctx,
            "draft": draft(cat, language(text), sender_name(rec), facts),
            "needs_nikita": cat in ("kinship", "other") or bool(vip_hits),
        })
    return out


def render(items: list[dict]) -> str:
    counts = {c: sum(1 for i in items if i["category"] == c) for c in ("kinship", "other", "thanks", "system")}
    lines = [
        "# Входящие MyHeritage: разбор", "",
        (f"Тредов: {len(items)} · вопросы о родстве: {counts['kinship']} · прочее: {counts['other']} · "
         f"благодарности: {counts['thanks']} · системные: {counts['system']}"), "",
        "Ничего не отправлено. Черновики уходят только после «да» Никиты (docs/RULES.md §3.1).", "",
    ]
    order = {"kinship": 0, "other": 1, "thanks": 2, "system": 3}
    for i in sorted(items, key=lambda x: (not x["vip"], order[x["category"]])):
        vip = " VIP: " + ", ".join(i["vip"]) if i["vip"] else ""
        title = (i.get("preview") or "").splitlines()[0][:80] if i.get("preview") else i["thread"]
        lines += [f"## [{i['category']}]{vip} {title}",
                  "", f"[открыть в MyHeritage]({i['url']}) · прочитано {i.get('ts', '')[:16]}", "",
                  "**Письмо:**", "", "> " + (i.get("text") or "").strip()[:3000].replace("\n", "\n> "), ""]
        if i["context"]:
            lines += ["**Что нашлось в графе (только для Никиты):**", ""]
            for h in i["context"]:
                extra = f", род. {h['birth']}, поколение {h['gen']}" if h["source"] == "ancestors" else \
                        f", встречался в {h.get('sightings')} совпадениях"
                lines.append(f"- {h['name']}{extra}")
            lines.append("")
        if i["draft"]:
            lines += ["**Черновик ответа:**", "", "```text", i["draft"], "```", ""]
    return "\n".join(lines) + "\n"


def notify(new_items: list[dict]) -> None:
    vip = [i for i in new_items if i["vip"]]
    title = "MyHeritage: письмо про VIP-предка" if vip else "MyHeritage: новое письмо"
    body = f"{len(new_items)} новых писем ждут тебя. Разбор и черновики: data/inbox_review.md"
    subprocess.run(["osascript", "-e",
                    f'display notification "{body}" with title "{title}" sound name "Glass"'], check=False)


def main() -> int:
    records = latest_threads()
    if not records:
        print("[inbox] no saved messages yet (data/inbox.jsonl is empty)")
        return 0
    graph = json.loads(GRAPH_FILE.read_text(encoding="utf-8")) if GRAPH_FILE.exists() else {}
    items = triage(records, graph, _vip_regexes())
    REVIEW_FILE.write_text(render(items), encoding="utf-8")

    seen = set(json.loads(SEEN_FILE.read_text())) if SEEN_FILE.exists() else set()
    new = [i for i in items if i["needs_nikita"] and f"{i['thread']}|{i['hash']}" not in seen]
    seen.update(f"{i['thread']}|{i['hash']}" for i in items)
    SEEN_FILE.write_text(json.dumps(sorted(seen)))
    print(f"[inbox] {len(items)} thread(s) triaged, {len(new)} new for Nikita -> {REVIEW_FILE}")
    if new and "--notify" in sys.argv:
        notify(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
