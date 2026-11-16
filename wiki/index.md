# Wiki Index — MyHeritage Automation Agent

> READ THIS FIRST before any domain question. Catalog of all wiki pages.
> Журнал изменений: [log.md](log.md). Как вести вики: [`docs/agent-method.md`](../docs/agent-method.md) §3. Проверка механики: `python3 -m pytest -q tests/test_wiki.py`.

## Overview
- [overview.md](overview.md) — проект целиком: что строим, ограничения, состояние

## Sources (ingested raw material)
| Slug | What it is |
|------|-----------|
| [agent-briefing](sources/agent-briefing.md) | Full project brief: goals, API situation, architecture, auth strategy, UI flow, decision logic, risk mitigation |
| [automation-explainer-2026-10-12](sources/automation-explainer-2026-10-12.md) | Объяснение для Никиты «как сейчас работает автоматизация» (частично устарело) |
| [project-memory-2026-11](sources/project-memory-2026-11.md) | Срез памяти проекта на 2026-11-13: раннер, капчи, уведомления, конфликты |
| [scheme-kit-2026-11-13](sources/scheme-kit-2026-11-13.md) | Набор «Схема проекта»: что взяли, что нет и почему |

## Entities (services, systems, features)
| Slug | What it is |
|------|-----------|
| [myheritage](entities/myheritage.md) | The MyHeritage platform — subscription, tree size, bot detection |
| [smart-matches](entities/smart-matches.md) | Smart Matches feature — UI flow, confidence score, confirm + extract actions |
| [record-matches](entities/record-matches.md) | Record Matches feature — historical documents, census, immigration records |
| [family-graph-api](entities/family-graph-api.md) | Read-only REST API at familygraph.myheritage.com — what it can/cannot do |

## Concepts (rules, workflows, algorithms)
| Slug | What it is | Staleness |
|------|-----------|-----------|
| [match-evaluation](concepts/match-evaluation.md) | 80% threshold, accept/skip/flag logic | stable |
| [browser-auth](concepts/browser-auth.md) | Cookie export, Playwright session state, re-auth strategy | 90d |
| [rate-limiting](concepts/rate-limiting.md) | Human-like delays, session caps, anti-detection rules | stable |
| [data-extraction](concepts/data-extraction.md) | What to save vs flag, priority order, conflict rules | stable |
| [agent-architecture](concepts/agent-architecture.md) | Hybrid API+Playwright design, module map, phase plan | active |
| [selectors](concepts/selectors.md) | CSS selectors for MyHeritage UI — MUST recon before use | 30d |
| [session-economics](concepts/session-economics.md) | Why MAX=100; the extract-step root cause of "saveButton not found"; safety verdict | 60d |
| [graph-accumulation](concepts/graph-accumulation.md) | Incremental local family-graph capture during confirmation, no manual GEDCOM re-export needed; generation-depth limitation | 60d |
| [priority-list](concepts/priority-list.md) | Read-only triage list for manual match review — VIP/ancestor hints, sorted by pending count | 60d |
| [background-runner](concepts/background-runner.md) | Фоновый раннер на Mac Mini: launchd, ритм сессий, что требует рук Никиты | 30d |
| [captcha-and-waf](concepts/captcha-and-waf.md) | Капча и WAF: правило реакции, хронология блоков, лечится свежим входом | 30d |
| [conflict-review](concepts/conflict-review.md) | Две проверки конфликтов и очередь `data/conflict_review.md` | 90d |
| [vip-alerts](concepts/vip-alerts.md) | VIP-фамилии прямой линии, уведомление только о новых находках | 90d |
| [nas-graph-export](concepts/nas-graph-export.md) | Публикация графа семьи на NAS после каждой сессии | 90d |
| [agent-framework](concepts/agent-framework.md) | Как устроена работа агентов: правила, метод, навыки `mh-*`, `/ship` | 1y |

## Generated
- [people/_index.md](people/_index.md) — страницы людей из GEDCOM (`gedcom_to_obsidian.py`), правила вики на них не действуют

## Status (2026-11-13)
- Smart Matches + Record Matches (каждая 3-я сессия) крутятся в фоне на Mac Mini → [background-runner](concepts/background-runner.md)
- С 2026-11-08 сессии упираются в капчу, нужен свежий вход Никиты → [captcha-and-waf](concepts/captcha-and-waf.md)
- Открытые PR: #1 (Record Matches, VIP только новые, очередь конфликтов), #2 (уведомление о капче и неудачном входе)

## Заменено
- Статус «Phase 1/2, ждём recon и cookie export» (2026-06-23) устарел: recon сделан, селекторы в [selectors](concepts/selectors.md)
