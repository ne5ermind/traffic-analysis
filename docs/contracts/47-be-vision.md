# Контракт #47: computer vision

Issue: https://github.com/ne5ermind/traffic-analysis/issues/47

Процессор кадра возвращает `xyxy[N,4]`, `class_id[N]`, `tracker_id[N]`, `confidence[N]`. Классы COCO: `0/1/2/3/5/7`; категории: pedestrian, bicycle, car, motorcycle, bus, truck.

`GET /api/runs/{id}/results?view=detections&time_s=N` возвращает `t` и `objects[]`: `tracker_id`, `class_id`, `category`, `xyxy`, нормализованный `box`, `confidence`. Если данных нет — `200` и пустой `objects`.

Один ID не дублируется в кадре; bbox имеет положительную площадь и ограничен кадром; NaN/Inf и неизвестные classes отбрасываются.

