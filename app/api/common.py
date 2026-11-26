

from datetime import datetime, timezone
from fastapi import HTTPException

ALLOWED_VIDEO = {".mp4", ".mov", ".mkv", ".avi", ".webm"}

VIDEO_MEDIA_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
}

STATUSES = {"review", "confirmed", "auto_accept", "discarded"}

CATEGORY_LABELS = {
    "pedestrian": "Пешеходы",
    "bicycle": "Вело",
    "car": "Авто",
    "motorcycle": "Мото",
    "truck": "Груз.",
    "bus": "ОТ",
}

CATEGORY_ORDER = ("pedestrian", "bicycle", "car", "motorcycle", "truck", "bus")

MODE_LABELS = {"effective": "Учтённые", "confirmed": "Только подтверждённые",
               "candidates": "Все кандидаты"}

TOPOLOGY_LABELS = {"three_way": "Трёхлучевой", "four_way": "Четырёхлучевой",
                   "unknown": "Не определён"}

REPORT_NAVY = "0B1F3A"

REPORT_BLUE = "1E5AA8"

REPORT_PALE = "EAF2FB"

REPORT_BORDER = "C8D5E6"

def now():
    return datetime.now(timezone.utc).isoformat()

def one(db, table, identity):
    if table not in ("videos", "scenes", "runs", "events", "ground_truth"):
        raise ValueError("unknown table")
    row = db.execute(f"SELECT * FROM {table} WHERE id=?", (identity,)).fetchone()
    if not row:
        raise HTTPException(404, f"{table}: не найдено")
    return dict(row)

def geometry_check(geometry):
    if not isinstance(geometry, dict):
        raise ValueError("Геометрия должна быть объектом")
    if geometry.get("mode") == "automatic":
        if geometry.get("entries") or geometry.get("exits"):
            raise ValueError("Автоматический режим не использует линии въезда и выезда")
    elif geometry.get("mode", "manual") != "manual":
        raise ValueError("Неизвестный режим подсчёта")
    elif not geometry.get("entries") or not geometry.get("exits"):
        raise ValueError("Нужна хотя бы одна линия въезда и выезда")
    for kind in (("entries", "exits") if geometry.get("mode") != "automatic" else ()):
        names = set()
        for line in geometry[kind]:
            if not line.get("name") or line["name"] in names:
                raise ValueError("У каждой линии должно быть уникальное название")
            names.add(line["name"])
            if len(line.get("points", [])) != 2:
                raise ValueError("Линия состоит из двух точек")
            if line["points"][0] == line["points"][1]:
                raise ValueError("Точки линии не должны совпадать")
            for point in line["points"]:
                if len(point) != 2 or not all(0 <= float(v) <= 1 for v in point):
                    raise ValueError("Координаты должны быть нормализованы (0..1)")
    for point in geometry.get("roi", []):
        if len(point) != 2 or not all(0 <= float(v) <= 1 for v in point):
            raise ValueError("Некорректная область интереса")
    if geometry.get("roi") and len(geometry["roi"]) < 3:
        raise ValueError("Для области интереса нужны минимум три точки")

