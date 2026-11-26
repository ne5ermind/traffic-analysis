# InnovaTransport

Локальный анализ транспортных и пешеходных потоков: загрузка видео, YOLO + ByteTrack, зоны/линии подсчёта, кластеры направлений, дневная и ночная обработка, проверка событий и экспорт. Интерфейс написан на React. Backend — модульный монолит FastAPI/SQLite; обработчик видео работает отдельным процессом.

## Запуск

Нужны Docker Compose и локальные веса. Скачивание зависимостей и весов выполняется при подготовке; обработка видео не использует внешние сервисы.

```bash
python3 scripts/fetch_weights.py --model yolo11s.pt
docker compose up --build -d
```

Открыть [приложение](http://127.0.0.1:8000) и [Swagger](http://127.0.0.1:8000/docs). Порт доступен только на localhost. Данные сохраняются в `data/`. Compose выделяет API 1 CPU, worker 3 CPU: общий бюджет — 4 CPU. У worker два потока PyTorch, один поток декодера и очередь не более четырёх кадров; состояние трекера обрабатывается строго по времени.

Ансамбль требует дополнительных локальных весов:

```bash
python3 scripts/fetch_weights.py --ensemble
```

### Без Docker

Python 3.11/3.12, Node.js 20+, FFmpeg и системные зависимости OpenCV:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
npm ci
npm run build
python scripts/fetch_weights.py --model yolo11s.pt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

В другом терминале с тем же окружением:

```bash
python -m app.worker
```

После изменения React-кода выполните `npm run build`. FastAPI раздаёт локально собранный JS/CSS; CDN не нужен. `INNOVA_DATA` позволяет задать другой каталог данных. По умолчанию используется CPU; `INNOVA_DEVICE=mps` включает доступный ускоритель Mac явно. Отсутствующие веса приводят к понятной ошибке, а не скачиванию во время анализа.

## Рабочий сценарий

1. Загрузить MP4/MOV/MKV/AVI/WebM и выбрать запись.
2. Оставить автоматический подсчёт либо задать линии въезда/выезда и ROI мышью или координатами. Зоны можно сохранить и открыть повторно; изменения сохраняются новой сценой, чтобы не менять старый результат.
3. Выбрать быстрый режим или ансамбль, частоту кадров и освещение. Для тёмного видео доступны night и auto. Отдельные ночные веса при наличии указываются именем файла в `data/models/`.
4. Запустить анализ. История и прогресс обновляются автоматически; анализ можно остановить. При исчезновении heartbeat интерфейс показывает явную ошибку не позднее пяти минут с учётом интервала опроса.
5. Проверить видео с рамками, категории, события, картограмму и кластеры. Исправление события защищено версией; устаревшая правка возвращает 409. По необходимости добавить пропущенный объект.
6. Скачать XLSX/CSV/JSON. JSON и XLSX включают кластеры; XLSX содержит также производительность. CSV сохраняет совместимую таблицу направлений.
7. Загрузить независимый эталон и получить метрики по [описанному протоколу](docs/RESEARCH_AND_EVALUATION.md).

Ночной baseline — коррекция L-канала + обычный детектор. Это не обученная специализированная ночная модель. Поддержаны её подключение, нормализация классов и обучение командой `python scripts/train_night.py --data /path/to/dataset.yaml`. Для обучения и измерения точности необходим размеченный ночной набор.

## Модули

```text
app/main.py              сборка приложения
app/api/media.py         загрузка и воспроизведение
app/api/counting.py      сцены и линии
app/api/analysis.py      очередь и управление запусками
app/api/results.py       события, ревизии, агрегация, overlay
app/api/reports.py        CSV/XLSX/JSON
app/api/evaluation.py     загрузка эталона и оценка
app/api/schemas.py       валидируемые контракты
app/worker.py            оркестрация обработки
app/vision/frames.py     ограниченная очередь декодирования
app/vision/lighting.py   ночная обработка
app/ensemble.py          детекция и постоянный ByteTrack
app/geometry.py          ROI, пересечения и подсчёт
app/clustering.py        DBSCAN направленных траекторий
app/evaluation.py        метрики без зависимости от HTTP
app/storage.py           переносимые пути и SQLite/WAL
frontend/hooks/          загрузка состояния и опрос API
frontend/components/     видео, конфигурация, результаты, редактор
```

В OpenAPI сохранены 10 согласованных API-путей. `GET /api/runs/{id}/results` возвращает summary, events, cartogram, clusters и performance; `view` позволяет запросить раздел отдельно. Сохранённые видео/события старых локальных YOLO-запусков читаются без миграции схемы. Для старых запусков кластеры отсутствуют до нового анализа. Данные API и путей остаются совместимыми с прежними контрактами команды.

## Проверки

```bash
pytest -q tests
python -m compileall -q app tests scripts
npm run build
docker compose config --quiet
```

Браузерный smoke на изолированных данных:

```bash
INNOVA_DATA=/tmp/innova-ui python scripts/seed_ui.py
INNOVA_DATA=/tmp/innova-ui uvicorn app.main:app --port 8017
# отдельный терминал
npm run test:ui
```

На Linux сначала `npx playwright install --with-deps chromium`. Smoke использует тестовую завершённую запись и проверяет зоны, редактирование событий, экспорт и responsive layout. Данные seed синтетические и не являются тестом качества модели.

Полный benchmark, без экстраполяции:

```bash
INNOVA_DATA=/path/to/empty-benchmark-data python scripts/benchmark_full.py /path/to/15-minute-video.mp4 --lighting night
```

Скопируйте веса в `models/` выбранного каталога. Для приёмки NF-01 выполняйте этот скрипт внутри Docker с тем же лимитом worker `--cpus=3`, резервируя 1 CPU для API. Скрипт требует видео ≥900 секунд, измеряет весь запуск включая загрузку модели и сохраняет JSON с параметрами среды.

Результаты проверки: [VERIFICATION.md](docs/VERIFICATION.md). Требования: [FR](docs/FR.md), [NFR](docs/NFR.md), [реестр](docs/REQUIREMENTS.md). Методы, ограничения и научные источники: [RESEARCH_AND_EVALUATION.md](docs/RESEARCH_AND_EVALUATION.md).
