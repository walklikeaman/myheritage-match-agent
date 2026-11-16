---
name: mh-knowledge-lookup
description: Search everything the MyHeritage project already knows (project memory, wiki, docs, Context brief, .loops, shared project notes) before starting a task or asking Nikita anything, then write new decisions back. Use at the start of every MyHeritage task and whenever a fact is unknown. Triggers (RU+EN) — «что мы знаем про», «где это записано», «найди в знаниях», «посмотри в вики», «что решили», "what do we know", "search the wiki", "what did we decide", "check the knowledge base".
---

# MyHeritage — поиск по знаниям

Правило: **сначала ищи, потом спрашивай.** Спрашивать уже записанное нельзя (`docs/RULES.md` §4).

## 1. Поиск (по порядку)

1. Память проекта уже загружена — открой файлы тем, не только строки индекса.
2. Локальный проход одной командой:
   ```bash
   bash .claude/skills/mh-knowledge-lookup/search.sh 'капча|captcha'
   ```
   Сначала `wiki/index.md`, потом найденные страницы и `wiki/log.md`. Ищи на обоих языках: вики смешанная RU/EN.
3. Граф: `graphify-out/GRAPH_REPORT.md`, если он есть.
4. Соседние треды проекта и общие файлы проекта (`/mnt/project-files/notes/`).

В первом ответе одной строкой: что нашёл и где. Не нашёл нигде — так и скажи, потом спрашивай.

## 2. Запись обратно

Новое решение или факт → его страница в `wiki/` (замена решения — по `docs/RULES.md` §5) → запись сверху в `wiki/log.md` → указатель в памяти проекта → `/ship`.

## Никогда

- Не класть в вики пароли, куки, почтовые адреса аккаунтов.
- Не править `Context/` и `wiki/people/` руками.
