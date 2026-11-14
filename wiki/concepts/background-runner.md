---
type: concept
created: 2026-11-13
updated: 2026-11-13
sources: [project-memory-2026-11, automation-explainer-2026-10-12]
confidence: high
status: active
relates_to: [agent-architecture, captcha-and-waf, vip-alerts, conflict-review, nas-graph-export]
staleness_window: 30d
tags: [runner, operations, mac-mini]
---
# Фоновый раннер: где живёт и что ему нужно

Схема цикла (launchd → `scripts/mh_runner_smart.sh` → `main.py` → шаги после сессии) описана в [agent-architecture](agent-architecture.md), раздел «Standing runner». Здесь только эксплуатация.

## Где

- **С 2026-11-03 раннер работает на Mac Mini.** Раннер на MacBook должен оставаться выключенным, иначе два цикла ходят в один аккаунт.
- Задание launchd: `com.walklikeaman.myheritage-runner` (`RunAtLoad` + `KeepAlive`), поднимается после перезагрузки сам.
- Mac должен быть на питании: цикл идёт под `caffeinate -is`, во сне на батарее он стоит.
- Никита разрешил автономную работу и планирование на Mac Mini (2026-11-02). Менять запущенный цикл всё равно лучше в паузе между сессиями: работающий скрипт держит старую версию до перезапуска.

## Ритм

- Smart Matches две сессии, потом одна Record Matches (`RECORD_EVERY=3`, выбор Никиты 2026-10-17).
- До 100 совпадений за сессию (`config.py`, почему 100: [session-economics](session-economics.md)); потолок безопасности 500 в `CLAUDE.md`.
- Пауза после чистой сессии 45–165 мин, после падения 5 мин, после капчи или WAF 6 ч.
- После каждой сессии: `notify_vip.py --notify`, `conflict_review.py`, `graph_accumulate.py`, `nas_export.py`.

## Что требует рук Никиты

- **Свежий вход в MyHeritage.** Сессия лежит в `data/myheritage_session.json`. Когда MyHeritage её сбрасывает или упорно показывает капчу, помогает только новый вход. Команда на Mac Mini (через venv проекта; старый путь фреймворка Python 3.12 больше не существует):
  `cd ~/GitHub/"My Heritage" && .venv/bin/python3 main.py --capture-session`
- Никита сменил пароль 2026-11-09, поэтому вход делает только он. Агент пароль не вводит.

## История сбоев

- Сентябрь–октябрь 2026: раннер жил в `screen` в `/tmp` и умирал при каждой перезагрузке (7 перезагрузок за месяц, самый долгий простой около 16 дней). С 2026-10-12 им управляет launchd.
- Капчи: отдельная страница [captcha-and-waf](captcha-and-waf.md).
