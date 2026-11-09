# InnovaTransport — анализ транспортных потоков

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Computer Vision](https://img.shields.io/badge/CV-YOLO11%20%2B%20ByteTrack-4F46E5)](https://docs.ultralytics.com/)
[![CI](https://github.com/ne5ermind/traffic-analysis/actions/workflows/check.yml/badge.svg)](https://github.com/ne5ermind/traffic-analysis/actions/workflows/check.yml)

Локальный сервис для автоматического подсчёта транспорта и пешеходов по видеозаписям. InnovaTransport обнаруживает и сопровождает объекты, считает потоки по всему кадру или пользовательской зоне, помогает проверить спорные события и формирует отчёты в JSON, CSV и XLSX.

> Видео, результаты и база SQLite остаются на устройстве пользователя. Внешняя передача исходных записей не требуется.

---

## 📌 О проекте

Ручной подсчёт транспортных потоков занимает много времени и плохо масштабируется. InnovaTransport объединяет полный рабочий цикл в одном интерфейсе:

1. загрузка видеозаписи;
2. настройка режима и зоны подсчёта;
3. запуск анализа;
4. детекция и трекинг объектов;
5. проверка событий и картограммы;
6. экспорт воспроизводимого отчёта.

Система рассчитана на учебные и исследовательские сценарии анализа перекрёстков, транспортных узлов и пешеходных потоков.

## 🎯 Возможности

- загрузка MP4, MOV, MKV, AVI и WebM;
- быстрый режим **YOLO11s + ByteTrack** и ансамбль двух моделей с WBF;
- распознавание пешеходов, велосипедов, автомобилей, мотоциклов, автобусов и грузовиков;
- автоматический подсчёт устойчивых треков или подсчёт проездов через заданную зону;
- сохранение рамок, траекторий и истории запусков;
- ручное подтверждение, отклонение и исправление событий;
- KPI, диаграммы, матрица направлений и картограмма;
- экспорт результатов в JSON, CSV и XLSX;
- локальное хранение данных и русскоязычный интерфейс.

## 🧭 Рабочий процесс

| Этап | Что происходит | Результат |
|---|---|---|
| 1. Видео | Пользователь загружает запись | Файл и метаданные появляются в каталоге |
| 2. Режим | Выбирается автоматический анализ или пользовательская зона | Зафиксирована геометрия подсчёта |
| 3. Анализ | Worker обрабатывает выбранные кадры | Детекции, треки и прогресс сохраняются |
| 4. Проверка | Пользователь проверяет найденные события | Подтверждённый набор данных |
| 5. Визуализация | Строятся KPI, графики и картограмма | Понятное представление потока |
| 6. Экспорт | Формируется JSON, CSV или XLSX | Переносимый отчёт |

## 🧩 Архитектура

```text
Браузер
   │
   ▼
FastAPI ───── SQLite
   │             │
   ├── API       ├── видео и сцены
   ├── статика   ├── запуски
   └── экспорт   └── события и ревизии
   │
   ▼
Worker ── YOLO11 / WBF ── ByteTrack ── подсчёт ── картограмма
```

Проект реализован как компактный модульный монолит: API и интерфейс обслуживаются FastAPI, длительная обработка выполняется отдельным worker-процессом, а состояние хранится в SQLite.

## 📁 Структура репозитория

```text
traffic-analysis/
├── app/                 # API, хранение, CV pipeline и worker
├── static/              # интерфейс без отдельного frontend-сервера
├── tests/               # API, геометрия, CV, экспорт и sampling
├── scripts/             # загрузка весов, smoke и benchmark
├── data/models/         # локальные веса моделей, не входят в Git
├── docs/                # требования, диаграммы, ADR и контракты задач
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 🚀 Быстрый запуск

### 1. Клонировать репозиторий

```bash
git clone https://github.com/ne5ermind/traffic-analysis.git
cd traffic-analysis
```

### 2. Скачать веса быстрого режима

```bash
python3 scripts/fetch_weights.py --model yolo11s.pt
```

Для ансамбля:

```bash
python3 scripts/fetch_weights.py --ensemble
```

### 3. Запустить через Docker Compose

```bash
docker compose up --build
```

Откройте [http://127.0.0.1:8000](http://127.0.0.1:8000). Swagger доступен по адресу [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Запуск без Docker

Нужны Python 3.11+ и системные зависимости FFmpeg/OpenCV.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Во втором терминале:

```bash
source .venv/bin/activate
python -m app.worker
```

## 🔌 Основные API-маршруты

| Метод | Маршрут | Назначение |
|---|---|---|
| `POST` | `/api/videos` | загрузить видеозапись |
| `GET` | `/api/videos/{id}/media` | получить видео или preview |
| `POST` | `/api/scenes` | сохранить зону подсчёта |
| `POST` | `/api/runs` | запустить анализ |
| `GET` | `/api/runs/{id}/results` | получить KPI, события и картограмму |
| `PATCH` | `/api/runs/{id}` | отменить запуск или сменить topology |
| `POST/PATCH` | `/api/runs/{id}/events` | добавить или исправить событие |
| `GET` | `/api/runs/{id}/export/{format}` | скачать JSON, CSV или XLSX |

Полная интерактивная схема доступна в Swagger после запуска приложения.

## ✅ Проверка проекта

```bash
PYTHONPATH=. .venv/bin/pytest -q tests
.venv/bin/python -m compileall -q app tests scripts
node --check static/app.js
docker compose config --quiet
```

Тесты покрывают API, загрузку видео, геометрию зон, выборку кадров, детекцию, трекинг, события, картограмму и экспорт.

## 👥 Команда и зоны ответственности

| Участник | Зона | Issues |
|---|---|---|
| [@ne5ermind](https://github.com/ne5ermind) | загрузка, каталог и проигрывание видео | [#43](https://github.com/ne5ermind/traffic-analysis/issues/43), [#44](https://github.com/ne5ermind/traffic-analysis/issues/44) |
| [@Gov1-10dav](https://github.com/Gov1-10dav) | очередь, прогресс и отмена анализа | [#45](https://github.com/ne5ermind/traffic-analysis/issues/45), [#46](https://github.com/ne5ermind/traffic-analysis/issues/46) |
| [@skillshifting](https://github.com/skillshifting) | детекция, трекинг и video overlay | [#47](https://github.com/ne5ermind/traffic-analysis/issues/47), [#48](https://github.com/ne5ermind/traffic-analysis/issues/48) |
| [@qqqquinke](https://github.com/qqqquinke) | зоны подсчёта и проверка событий | [#49](https://github.com/ne5ermind/traffic-analysis/issues/49), [#50](https://github.com/ne5ermind/traffic-analysis/issues/50) |
| [@zhorarichka-a11y](https://github.com/zhorarichka-a11y) | агрегация, картограмма и экспорт | [#51](https://github.com/ne5ermind/traffic-analysis/issues/51), [#52](https://github.com/ne5ermind/traffic-analysis/issues/52) |

## 📚 Документация

| Документ | Содержание |
|---|---|
| [AS-IS](./docs/AS-IS.md) | исходный процесс ручного анализа |
| [Упрощённая TO-BE](./docs/TO-BE-COMPANY.md) | целевой процесс для компании и заказчика |
| [Функциональные требования](./docs/FR.md) | требования ФТ-1 — ФТ-10 |
| [Нефункциональные требования](./docs/NFR.md) | производительность, надёжность, безопасность и качество |
| [Реестр требований](./docs/REQUIREMENTS.md) | требования, способы проверки и критерии приёмки |
| [Гипотезы и риски](./docs/Hypotises_and_Risks.md) | проверяемые предположения и ограничения |
| [Таблица предположений](./docs/Таблица_предположений.md) | статус и способ проверки предположений |
| [Стейкхолдеры](./docs/Таблица_стейкхолдеров.md) | роли, влияние и интерес участников |
| [ADR](./docs/adr/README.md) | принятые архитектурные решения |
| [Контракты задач](./docs/contracts/) | интерфейсы и критерии приёмки issues #43–52 |

## ⚠️ Ограничения метода

Точность зависит от ракурса камеры, освещения, окклюзий, частоты выборки кадров и качества трекинга. Автоматический режим считает уникальные устойчивые треки во всём кадре; пользовательская зона считает проезды через заданные границы. Эти показатели нельзя напрямую сравнивать без одинаковой области наблюдения и правил разметки.

Проект не заменяет сертифицированную систему транспортного мониторинга. Для оценки качества на новых данных необходима отдельная размеченная выборка.

