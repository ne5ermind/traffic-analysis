# Контракт #45: backend запусков

Issue: https://github.com/ne5ermind/traffic-analysis/issues/45

- `POST /api/runs`: `video_id` или `scene_id`, `profile=fast|ensemble`, `sample_fps=2..12`, `topology=auto|three_way|four_way`, tracker.
- `GET /api/runs?video_id=...` — история.
- `GET /api/runs/{id}` — состояние, geometry и опциональный `eta_s`.
- `PATCH /api/runs/{id}` с `{"action":"cancel"}` — отмена.

Статусы: `queued`, `running`, `completed`, `failed`, `cancelled`; API может выдать вычисляемый `stalled`. `progress` в `[0,1]` и не уменьшается. Geometry — снимок на момент старта. Ошибка worker переводит run в `failed` и заполняет `message`.

