# Контракт #43: backend видео

Issue: https://github.com/ne5ermind/traffic-analysis/issues/43

## API

- `POST /api/videos`, `multipart/form-data`, поле `file`.
- `GET /api/videos` — массив записей с `available`.
- `GET /api/videos/{id}/media?kind=file` — видео с корректным MIME.
- `GET /api/videos/{id}/media?kind=frame&time_s=N` — JPEG-кадр.

Успешная загрузка возвращает `id`, `name`, `width`, `height`, `duration`, `fps`, `created_at`. Поддерживаются MP4, MOV, MKV, AVI, WebM. Невалидный/пустой файл — `422`; отсутствующий ID/файл — `404`.

## Инварианты

- ID уникален; физическое имя генерирует backend.
- Невалидный файл не остаётся в БД и storage.
- Frontend не строит URL из внутреннего `path`.

## Приёмка

Видео появляется в каталоге, метаданные верны, файл и preview доступны; error paths покрыты API-тестами.

