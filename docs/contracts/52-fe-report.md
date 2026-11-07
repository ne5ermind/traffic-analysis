# Контракт #52: frontend отчёта

Issue: https://github.com/ne5ermind/traffic-analysis/issues/52

KPI, категории, интервалы, матрица и картограмма берутся одним запросом из `/api/runs/{id}/results`; события — из того же ответа. UI переводит минуты интервала в секунды API. Export-ссылки содержат текущие run, mode и interval.

Пустые arrays — валидный empty state. Категории различаются не только цветом, но и подписью/значением. После event edit/topology change нужные endpoint-ы перечитываются. Старый асинхронный ответ не перезаписывает новый run.

