---
type: source
created: 2026-11-13
updated: 2026-11-13
sources: [scheme-kit-2026-11-13]
confidence: high
status: active
relates_to: [agent-framework]
staleness_window: 1y
tags: [harness, ingest]
---
# Набор «Схема проекта» (2026-11-13)

Никита приложил набор, по которому уже работают Media Manager и KIT: шаблоны правил, метода, вики, `.loops/`, `/ship`, навыков, хуков и теста вики.

Что взято и куда легло: [agent-framework](../concepts/agent-framework.md).

Что не взято и почему:

- **Тонкий `CLAUDE.md` вместо текущего.** Текущий `CLAUDE.md` содержит живые правила проекта, его не урезали, а дописали таблицей ссылок.
- **Граф Graphify.** Graphify на машинах проекта не стоит, `graphify-out/` нет. Хук `.githooks/post-commit` уже пересобирает граф, если graphify появится; папка добавлена в `.gitignore`.
- **Папка `.scheme-claude-ai/`.** Текст инструкций проекта для claude.ai отдан Никите отдельным файлом, в репозиторий не кладётся.
