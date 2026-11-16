---
type: source
created: 2026-11-13
updated: 2026-11-13
sources: [automation-explainer-2026-10-12]
confidence: medium
status: active
relates_to: [agent-architecture, conflict-review, vip-alerts, background-runner]
staleness_window: 90d
tags: [explainer, ingest]
---
# Объяснение «Как сейчас работает автоматизация» (2026-10-12)

Файл в общих файлах проекта: `notes/kak-rabotaet-avtomatizaciya.md`. Написан для Никиты по коду на коммите `52280d1` и живым логам Mac.

Коротко, что в нём:

1. Откуда совпадения: Discovery Hub «по людям», сначала самые близкие родственники, уже известные конфликты за 14 дней пропускаются.
2. Как подтверждается одно совпадение: проверка до подтверждения, подтверждение, мастер извлечения со всеми родственниками и фото, вторая проверка по предложению слияния, сохранение → [conflict-review](../concepts/conflict-review.md).
3. Что извлекается и где копия графа → [graph-accumulation](../concepts/graph-accumulation.md).
4. Как крутится фон → [background-runner](../concepts/background-runner.md).
5. Живые логи того дня: около 30 сохранений из 100 за сессию, остальное конфликты.

**Что устарело с тех пор:** Record Matches уже в цикле (каждая 3-я сессия), VIP-уведомление приходит на Mac о новых находках, раннер переехал на Mac Mini.
