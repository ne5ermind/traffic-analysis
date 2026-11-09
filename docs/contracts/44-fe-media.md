# Контракт #44: frontend видео

Issue: https://github.com/ne5ermind/traffic-analysis/issues/44

UI отправляет `FormData(file)` в `POST /api/videos`, затем перечитывает `GET /api/videos`. Используемые поля: `id`, `name`, `width`, `height`, `duration`, `fps`, `created_at`, `available`.

Состояния: `idle -> uploading -> success|error`. При `available=false` проигрыватель и новый анализ отключены, но история результатов остаётся.

Ошибка `detail` показывается без stack trace. Повторный выбор того же файла снова запускает upload. После успеха выбранное видео, poster и src обновлены без reload страницы.

