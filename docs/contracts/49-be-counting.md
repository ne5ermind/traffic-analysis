# Контракт #49: zones и counting

Issue: https://github.com/ne5ermind/traffic-analysis/issues/49

`POST /api/scenes`, `PUT /api/scenes/{id}`, `GET /api/scenes?video_id=...`. Geometry manual содержит `entries`, `exits`, `roi`; координаты `[x,y]` в `[0,1]`. Каждая линия имеет уникальное имя и ровно две точки. Ошибка geometry — `422`; перепривязка сцены — `409`.

Events: `GET /api/runs/{id}/results?view=events`, `POST /api/runs/{id}/events`, `PATCH /api/runs/{id}/events`. Правка передаёт `id` и `version`; конфликт — `409`. Статусы: `review|confirmed|auto_accept|discarded`. В automatic направление «В кадре → В кадре». Один проход объекта не создаёт дублей.

