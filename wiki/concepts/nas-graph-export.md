---
type: concept
created: 2026-11-13
updated: 2026-11-13
sources: [project-memory-2026-11]
confidence: medium
status: active
relates_to: [graph-accumulation, background-runner]
staleness_window: 90d
tags: [nas, graph, export]
---
# Граф семьи на NAS

С 2026-11-02 граф публикуется на домашний NAS рядом с архивом документов, по просьбе Никиты.

- `graph_accumulate.py` сливает снимки мастера извлечения в `data/family_graph.json` ([graph-accumulation](graph-accumulation.md)).
- `nas_export.py` пишет в архив NAS папку `Родословная/граф/` (persons.json, family_graph.json, страницы людей, README) и индекс документов родственников.
- Папки документов на NAS названы так же, как страницы `wiki/people/`, поэтому у страницы и её документов один ключ.
- Раннер делает оба шага после каждой сессии; если NAS выключен, пишет в лог «NAS export failed» и идёт дальше.
- Первая публикация: 193 человека, у 24 родственников есть документы.
