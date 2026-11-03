# Architecture Decision Records

В этой папке хранятся короткие решения по архитектуре InnovaTransport.

| ADR | Решение | Модули |
|---|---|---|
| [0001](0001-compact-public-api.md) | Компактный API и Swagger | `app/main.py` |
| [0002](0002-modular-monolith.md) | Модульный монолит | весь проект |
| [0003](0003-http-api.md) | HTTP API на FastAPI | `app/main.py` |
| [0004](0004-sqlite-storage.md) | SQLite и файловое хранилище | `app/storage.py` |
| [0005](0005-computer-vision.md) | YOLO, WBF и ByteTrack | `app/model.py`, `app/ensemble.py` |
| [0006](0006-worker-and-sampling.md) | Фоновый worker и выборка кадров | `app/worker.py`, `app/sampling.py` |
| [0007](0007-geometry-and-counting.md) | Геометрия и подсчёт | `app/geometry.py` |
| [0008](0008-cartogram-and-reports.md) | Картограмма и отчёты | `app/cartogram.py`, `app/main.py` |
| [0009](0009-static-frontend.md) | Статический frontend | `static/` |

Новые решения добавляются отдельным файлом; принятые ADR не переписываются задним числом.
