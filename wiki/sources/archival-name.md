---
type: source
created: 2026-11-17
updated: 2026-11-17
sources: [archival-name]
confidence: medium
status: active
relates_to: [vip-alerts, dako-r3050-1-54-shmul-duvid-ganushchiner]
staleness_window: 180d
tags: [external-source, archive, ukraine, pogroms]
---
# archival.name: именной указатель по архивным делам

Сайт [archival.name](https://archival.name/ru/) собирает имена из оцифрованных архивных дел. Никита нашёл через него запись о Шмуль-Дувиде Ганущинере (2026-11-17), см. [dako-r3050-1-54-shmul-duvid-ganushchiner](dako-r3050-1-54-shmul-duvid-ganushchiner.md).

## Что видно на странице (по скриншоту Никиты)

- Коллекция `ru/ukraine/pogrom-relief-resettlement-1917-1938`: дела комитетов помощи пострадавшим от погромов 1917–1924 и переселения до 1938 года.
- Поиск по параметру `q=` (пример: `?q=ganuschiner`), плюс параметр `m=`. Латинский запрос `ganuschiner` нашёл запись, записанную как «Ганущинер» и транслитерированную как «Ganuszcziner», то есть поиск сопоставляет написания.
- Карта мест; люди без места тоже ищутся.
- У записи есть ID (`PGR-P0493-284-R7`), ID человека (`…-R7-7`), кнопка «найти этого человека в других записях», архивный шифр, лист, страница скана и ссылки на скан и на всё дело в Wikimedia Commons.

## Можно ли подключить как постоянный источник

**Автоматически нельзя.** 2026-11-17 любые автоматические запросы к сайту отклонены его правилами `robots.txt` (`robots_disallowed`), а сеть облака и Mac Mini через прокси вообще не пускает на этот домен. Обходить такие запреты не будем, это то же правило, что и для капчи (§3.3 [правил](../../docs/RULES.md)).

Что работает:

1. **Ручной поиск по VIP-фамилиям** в браузере, раз в несколько месяцев. Готовые ссылки:
   - [ganuschiner](https://archival.name/ru/ukraine/pogrom-relief-resettlement-1917-1938/?q=ganuschiner), [ganushchiner](https://archival.name/ru/ukraine/pogrom-relief-resettlement-1917-1938/?q=ganushchiner), [ганущинер](https://archival.name/ru/ukraine/pogrom-relief-resettlement-1917-1938/?q=ганущинер)
   - [rassadina](https://archival.name/ru/ukraine/pogrom-relief-resettlement-1917-1938/?q=rassadina), [рассадина](https://archival.name/ru/ukraine/pogrom-relief-resettlement-1917-1938/?q=рассадина) (Рассадины не евреи, в этой коллекции их вряд ли много; полезнее поиск по всему сайту, если он есть)
2. **Найденное присылать агенту** скриншотом или ID записи. Агент сверяет с деревом и пишет страницу в `wiki/sources/`, как сделано для Шмуль-Дувида.
3. **Сканы брать с Wikimedia Commons**, куда ведёт сайт. Это открытый ресурс, его можно читать автоматически.
4. Если нужен регулярный прогон, **написать владельцу сайта** и спросить про выгрузку или API. Письмо только после «да» Никиты (§3.1).

Не проверено: есть ли у сайта поиск по всем коллекциям сразу, API или выгрузка. Агент страницы сайта не видел, только скриншот.
