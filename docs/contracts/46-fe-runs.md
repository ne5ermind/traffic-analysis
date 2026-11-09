# Контракт #46: frontend запусков

Issue: https://github.com/ne5ermind/traffic-analysis/issues/46

UI позволяет выбрать profile, FPS, topology и зону. Для automatic в `POST /api/runs` уходит `video_id`, для manual — `scene_id`.

Polling выполняется только для `queued|running|stalled`. Terminal status останавливает polling. Кнопка запуска защищена от double click; cancel виден только для активной задачи. При смене видео/запуска старые ответы и polling не должны перезаписывать UI.

