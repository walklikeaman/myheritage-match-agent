"""Inbox stage 1: dedup of read threads, triage categories, safe drafts."""
from browser.inbox import pick_threads, text_hash, thread_key
from inbox_triage import _vip_regexes, classify, draft, language, triage

GRAPH = {
    "ancestors": {
        "@I30@": {"gen": 3, "name": "Мария Михайловна Разсадина", "birth": "7 AUG 1908"},
        "@I2@": {"gen": 1, "name": "Владимир Николаевич Наконечный", "birth": "22 AUG 1956"},
    },
    "harvested_people": {},
}


def test_thread_key_is_stable_across_lang_param():
    a = thread_key("https://www.myheritage.com/inbox/thread/123456?lang=RU")
    b = thread_key("https://www.myheritage.com/inbox/thread/123456")
    assert a == b == "123456"


def test_pick_skips_unchanged_and_puts_unread_first():
    t1 = {"href": "https://www.myheritage.com/inbox/thread/1111", "text": "old", "unread": False}
    t2 = {"href": "https://www.myheritage.com/inbox/thread/2222", "text": "new", "unread": True}
    t3 = {"href": "https://www.myheritage.com/inbox/thread/3333", "text": "changed", "unread": False}
    for t in (t1, t2, t3):
        t["preview_hash"] = text_hash(t["text"])
    seen = {"1111": text_hash("old"), "3333": text_hash("before")}
    picked = pick_threads([t1, t2, t3], seen, limit=10)
    assert [p["thread"] for p in picked] == ["2222", "3333"]
    assert len(pick_threads([t1, t2, t3], {}, limit=1)) == 1


def test_classify():
    assert classify("Здравствуйте! Подскажите, как мы связаны? Видела совпадение с вашим деревом") == "kinship"
    assert classify("Hi, how are we related? I saw your Smart Match") == "kinship"
    assert classify("Спасибо, что подтвердили совпадение!") == "thanks"
    assert classify("Команда MyHeritage: скидка 50% на подписку") == "system"
    assert classify("Добрый день, у вас есть фото этого дома?") == "other"


def test_language():
    assert language("Здравствуйте, как дела") == "ru"
    assert language("Hello there") == "en"


def test_draft_is_plain_and_honest():
    d = draft("kinship", "ru", "Анна", ["Мария Михайловна Разсадина (1908)"])
    assert "Smart Matches" in d and "Разсадина (1908)" in d
    assert "—" not in d and "–" not in d  # no dashes in replies (RULES §3.10)
    assert draft("system", "ru", "", []) == ""


def test_triage_keeps_living_people_out_of_drafts_and_flags_vip():
    rec = {"thread": "1", "hash": "h", "url": "u", "preview": "Анна\nпривет",
           "text": "Как мы связаны? Моя бабушка из Разсадиных, и ещё Наконечный в дереве"}
    [item] = triage([rec], GRAPH, _vip_regexes())
    assert item["category"] == "kinship" and item["needs_nikita"]
    assert item["vip"] == ["Рассадина"]
    assert "Разсадина (1908)" in item["draft"]
    assert "1956" not in item["draft"]  # living-generation dates stay out of the reply
    assert any(h["name"].startswith("Владимир") for h in item["context"])  # but Nikita sees it
