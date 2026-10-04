"""Heuristic consistency audit for traffic-analysis results.

The detector is the neural part of the pipeline.  This module uses its
confidence and tracks as evidence, then performs a conservative consistency
pass.  It never invents a vehicle count when the recording is too poor.
"""

from collections import Counter


SIDES = ("north", "east", "south", "west")
SIDE_LABELS = {"north": "сверху", "east": "справа", "south": "снизу", "west": "слева"}


def _xy(point):
    if isinstance(point, dict):
        return float(point["x"]), float(point["y"])
    return float(point[0]), float(point[1])


def _side(point):
    x, y = _xy(point)
    distances = {"west": x, "east": 1 - x, "north": y, "south": 1 - y}
    return min(distances, key=distances.get)


def _zone_side(zone):
    points = zone.get("points") or []
    if not points:
        return None
    x = sum(_xy(point)[0] for point in points) / len(points)
    y = sum(_xy(point)[1] for point in points) / len(points)
    return _side((x, y))


def _movement_route(movement):
    path = movement.get("path") or []
    if movement.get("id") == "unknown" or len(path) < 2:
        return None
    source, target = _side(path[0]), _side(path[-1])
    if source == target:
        return None
    return source, target


def _intersection(result):
    calibration = result.get("calibration") or {}
    configured = {_zone_side(zone) for zone in calibration.get("zones", [])}
    configured.discard(None)
    routes = []
    for movement in result.get("movements", []):
        route = _movement_route(movement)
        if route:
            routes.append((movement, route))
    routed = {side for _, route in routes for side in route}
    active = configured if len(configured) in (3, 4) else routed
    if len(active) == 4:
        kind = "Четырёхсторонний перекрёсток"
    elif len(active) == 3:
        kind = "Т‑образный перекрёсток"
    elif len(active) == 2:
        kind = "Двухсторонний участок"
    else:
        kind = "Конфигурация не определена"

    route_weights = Counter()
    for movement, route in routes:
        route_weights[route] += max(1, int(movement.get("total", 0)))
    dominant = route_weights.most_common(1)
    direction = None
    if dominant:
        source, target = dominant[0][0]
        direction = f"{SIDE_LABELS[source]} → {SIDE_LABELS[target]}"
    evidence = min(1.0, len(active) / 3) if active else 0.0
    evidence *= min(1.0, len(routes) / 3) if routes else 0.35
    if configured:
        evidence = min(1.0, evidence + 0.25)
    return {
        "type": kind,
        "approaches": [SIDE_LABELS[side] for side in SIDES if side in active],
        "active_sides": [side for side in SIDES if side in active],
        "dominant_direction": direction,
        "confidence": round(max(0.0, min(0.99, evidence)), 3),
        "route_count": len(routes),
    }


def _mean(values, default=0.0):
    return sum(values) / len(values) if values else default


def _quality(result, frame_quality):
    diagnostics = result.get("diagnostics") or {}
    frame_quality = frame_quality or {}
    sharpness = float(frame_quality.get("sharpness", 0.0))
    brightness = float(frame_quality.get("brightness", 128.0))
    contrast = float(frame_quality.get("contrast", 32.0))
    detector_confidence = float(diagnostics.get("mean_detection_confidence", 0.0))
    tracks = max(1, int(diagnostics.get("tracks", 0)))
    unknown = int(diagnostics.get("unknown_tracks", 0))
    discarded_short = int(diagnostics.get("discarded_short_tracks", 0))
    discarded_stationary = int(diagnostics.get("discarded_stationary_tracks", 0))
    discarded = discarded_short + discarded_stationary
    sharpness_score = min(1.0, sharpness / 120.0) if frame_quality else 0.65
    brightness_score = max(0.0, 1.0 - abs(brightness - 128.0) / 128.0) if frame_quality else 0.65
    contrast_score = min(1.0, contrast / 64.0) if frame_quality else 0.65
    confidence_score = max(0.0, min(1.0, detector_confidence / 0.85)) if detector_confidence else 0.55
    tracking_score = max(0.0, 1.0 - (unknown + discarded) / tracks)
    score = (
        0.25 * sharpness_score
        + 0.15 * brightness_score
        + 0.15 * contrast_score
        + 0.25 * confidence_score
        + 0.20 * tracking_score
    )
    return {
        "score": round(max(0.0, min(1.0, score)), 3),
        "sharpness": round(sharpness, 2),
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "detector_confidence": round(detector_confidence, 3),
        "unknown_track_ratio": round(unknown / tracks, 3),
        "discarded_track_ratio": round(discarded / tracks, 3),
        "discarded_stationary_ratio": round(discarded_stationary / tracks, 3),
        "samples": int(frame_quality.get("samples", 0)),
    }


def _safe_corrections(result):
    """Apply only corrections that cannot fabricate traffic counts."""
    applied = []
    movements = result.get("movements", [])
    movement_total = sum(max(0, int(movement.get("total", 0))) for movement in movements)
    movement_pedestrians = sum(max(0, int(movement.get("pedestrians", 0))) for movement in movements)
    if result.get("total_vehicles") != movement_total:
        result["total_vehicles"] = movement_total
        applied.append("Сверен общий итог транспорта с направлениями")
    if result.get("pedestrians") != movement_pedestrians:
        result["pedestrians"] = movement_pedestrians
        applied.append("Сверен общий итог пешеходов с направлениями")
    counts = result.get("counts")
    if isinstance(counts, dict):
        for class_name in counts:
            value = sum(max(0, int(movement.get("counts", {}).get(class_name, 0))) for movement in movements)
            if counts[class_name] != value:
                counts[class_name] = value
                applied.append(f"Сверен класс объектов: {class_name}")
    for movement in result.get("movements", []):
        path = movement.get("path") or []
        corrected = []
        changed = False
        for point in path:
            if len(point) < 2:
                changed = True
                continue
            x, y = max(0.0, min(1.0, float(point[0]))), max(0.0, min(1.0, float(point[1])))
            rest = list(point[2:])
            new_point = [x, y, *rest]
            corrected.append(new_point)
            changed = changed or new_point != list(point)
        if changed:
            movement["path"] = corrected
            applied.append(f"Ограничены координаты траектории: {movement.get('name', movement.get('id', 'неизвестно'))}")
        if movement.get("reliability", 0.0) < 0.7 and movement.get("id") != "unknown":
            movement["requires_review"] = True
    return applied


def audit_result(result, frame_quality=None):
    """Return an explainable local verdict and safely correct malformed geometry."""
    intersection = _intersection(result)
    video = _quality(result, frame_quality)
    corrections = _safe_corrections(result)
    checks = []
    if video["score"] < 0.5:
        checks.append({"level": "error", "message": "Качество видео недостаточно для автоматического доверенного подсчёта."})
    elif video["score"] < 0.7:
        checks.append({"level": "warning", "message": "Видео требует проверки: есть признаки потери объектов или плохой резкости."})
    else:
        checks.append({"level": "ok", "message": "Качество кадров и уверенность детектора приемлемы."})
    if video["unknown_track_ratio"] > 0.35:
        checks.append({"level": "warning", "message": "Много траекторий не получили направление; значения оставлены для проверки."})
    if video["discarded_stationary_ratio"] > 0.2:
        checks.append(
            {
                "level": "warning",
                "message": "Много неподвижных ложных треков исключено; проверьте дальний план и перекрытия на видео.",
            }
        )
    if intersection["type"] == "Конфигурация не определена":
        checks.append({"level": "warning", "message": "Тип перекрёстка не удалось уверенно определить по траекториям."})
    else:
        checks.append({"level": "ok", "message": f"Гипотеза по траекториям: {intersection['type']}. Не заменяет визуальный анализ дороги."})
    if corrections:
        checks.append({"level": "warning", "message": "Исправлены только арифметические и геометрические несоответствия; новые объекты не добавлялись."})
    score = 0.65 * video["score"] + 0.35 * intersection["confidence"]
    if any(check["level"] == "error" for check in checks):
        verdict = "Низкая достоверность"
    elif score < 0.7 or any(check["level"] == "warning" for check in checks):
        verdict = "Требуется проверка"
    else:
        verdict = "Можно использовать"
    return {
        "verdict": verdict,
        "confidence": round(max(0.0, min(0.99, score)), 3),
        "intersection": intersection,
        "video_quality": video,
        "checks": checks,
        "corrections_applied": corrections,
    }
