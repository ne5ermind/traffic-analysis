# Контракт #51: results и export

Issue: https://github.com/ne5ermind/traffic-analysis/issues/51

- `GET /api/runs/{id}/results?mode=effective&interval=900` — сводка, events и картограмма.
- `GET /api/runs/{id}/results?view=cartogram` — только картограмма.
- `PATCH /api/runs/{id}` с `{"action":"set_topology","topology":"three_way"}` — смена схемы.
- `GET /api/runs/{id}/export/{json|csv|xlsx}`.

Aggregate содержит `total`, `transport_total`, `pedestrian_total`, `statuses`, `category_totals`, `matrix`, `intervals`, `events`, `geometry`, `video`, `scene`. `interval` в 1..86400; mode: `effective|confirmed|candidates`.

Инварианты: `total == sum(category_totals)` и `total == transport_total + pedestrian_total`; интервалы `[start,end)`; выгрузка совпадает с `results.summary` при тех же параметрах; неопределённые направления не теряются.

