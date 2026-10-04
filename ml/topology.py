"""Conservative mapping from image trajectories to visually identified approaches."""
import math

TYPE_LABELS = {"t": "Т-образный", "y": "Y-образный", "four_way": "Четырёхсторонний", "multi_way": "Многосторонний", "roundabout": "Кольцевой", "straight": "Прямой участок", "unknown": "Не определён"}


def select_topology(config, scene):
    manual = config.get("intersection")
    if manual:
        center = manual["center"]
        approaches = [{**a, "angle": round(math.degrees(math.atan2(a["x"]-center["x"], center["y"]-a["y"])) % 360, 1)} for a in manual["approaches"]]
        return {**manual, "approaches": approaches, "source": "manual", "requires_review": False, "usable": True}
    # User calibration has priority. Merge entry and exit polygons belonging to the same arm.
    groups = []
    for zone in config.get("zones", []):
        points = zone.get("points", [])
        if not points:
            continue
        x = sum(p["x"] for p in points) / len(points)
        y = sum(p["y"] for p in points) / len(points)
        angle = math.degrees(math.atan2(x - .5, .5 - y)) % 360
        group = next((g for g in groups if min(abs(g["angle"] - angle), 360 - abs(g["angle"] - angle)) < 40), None)
        if group:
            group["zone_ids"].append(zone.get("id"))
        else:
            groups.append(dict(id=f"arm{len(groups)+1}", label=zone.get("name") or f"Подход {len(groups)+1}", x=x, y=y, angle=angle, zone_ids=[zone.get("id")]))
    if len(groups) >= 2:
        kind = {2: "straight", 4: "four_way"}.get(len(groups), "multi_way")
        if len(groups) == 3:
            angles = sorted(g["angle"] for g in groups)
            gaps = [(angles[(i+1) % 3] - angles[i]) % 360 for i in range(3)]
            kind = "t" if max(gaps) >= 165 else "y"
        return {"source": "calibration", "intersection_type": kind, "approaches": groups,
                "center": {"x": .5, "y": .5}, "requires_review": True, "usable": True,
                "review_reason": "Схема по вашим зонам. Проверьте расположение подходов; форма дороги не восстанавливается по зонам."}
    if scene.get("status") == "ok":
        usable = scene["confidence"] >= .75 and scene["camera_static"] and scene["fully_visible"] and scene["intersection_type"] not in ("unknown", "roundabout")
        return {**scene, "source": "local_vlm", "requires_review": not usable, "usable": usable,
                "review_reason": "Проверьте геометрию: низкая уверенность, неполный обзор или движение камеры." if not usable else ""}
    return {"source": "unavailable", "intersection_type": "unknown", "approaches": [], "requires_review": True, "usable": False,
            "review_reason": "Геометрия не определена. Задайте зоны въезда и выезда или включите локальную модель."}


def match_approach(point, topology):
    if not topology.get("usable"):
        return None
    distances = sorted((math.hypot(point[0] - a["x"], point[1] - a["y"]), i) for i, a in enumerate(topology["approaches"]))
    if not distances or distances[0][0] > .24:
        return None
    if len(distances) > 1 and distances[1][0] - distances[0][0] < .08:
        return None
    return topology["approaches"][distances[0][1]]


def assign_path(path, topology):
    if len(path) < 3:
        return None
    start, end = match_approach(path[0], topology), match_approach(path[-1], topology)
    if not start or not end or start["id"] == end["id"]:
        return None
    return start, end


def attach_routes(result):
    topology = result.get("intersection", {})
    zones = {z: a for a in topology.get("approaches", []) for z in a.get("zone_ids", []) if z}
    for m in result.get("movements", []):
        if m["id"] == "unknown":
            continue
        start, end = zones.get(m.get("entry_zone")), zones.get(m.get("exit_zone"))
        route = (start, end) if start and end and start != end else assign_path(m.get("path", []), topology)
        if route:
            m["source_approach"], m["target_approach"] = route[0]["id"], route[1]["id"]
