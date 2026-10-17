"""Build an honest schematic of observed routes from saved track endpoints."""
from collections import Counter
from math import hypot
from pathlib import Path
import re

ARMS = {
    "three_way": {"Север": (0, -1), "Юго-восток": (0.866, 0.5),
                  "Юго-запад": (-0.866, 0.5)},
    "four_way": {"Север": (0, -1), "Восток": (1, 0),
                 "Юг": (0, 1), "Запад": (-1, 0)},
}


def route_catalog(topology):
    """Return deterministic schematic route numbers for report tables.

    The numbering is local to the generated schematic.  Supplied reference maps
    use site-specific numbers, so those must not be claimed without an explicit
    camera-to-map mapping.
    """
    if topology not in ARMS:
        return []
    arms = list(ARMS[topology])
    return [{"direction": index, "from": source, "to": target}
            for index, (source, target) in enumerate(
                ((source, target) for source in arms for target in arms if source != target), 1)]


def _category_rows(counts):
    return [{"category": category, "count": count}
            for category, count in sorted(counts.items())]


def _track_endpoints(track):
    """Read a saved track defensively; diagnostics may come from older runs."""
    try:
        if int(track.get("seen", 0)) < 3:
            return None
        start, end = track["start"], track["end"]
        if len(start) < 2 or len(end) < 2:
            return None
        values = tuple(float(value) for value in (start[0], start[1], end[0], end[1]))
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    if not all(value == value and abs(value) != float("inf") for value in values):
        return None
    return values[:2], values[2:]


def reference_topology(filename):
    """Use the supplied example schematics, not a guess based on camera pixels."""
    match = re.match(r"Пример\s*([1-4])[_\s]", Path(filename).name, re.IGNORECASE)
    if not match:
        return None
    return "three_way" if match.group(1) == "4" else "four_way"


def arm_for_point(point, topology, center=(0.5, 0.5)):
    """Map an observed endpoint to a schematic arm, or return None if ambiguous."""
    x, y = point[0] - center[0], point[1] - center[1]
    distance = hypot(x, y)
    if distance < 0.16:
        return None
    bearings = sorted(((x * dx + y * dy) / distance, name)
                      for name, (dx, dy) in ARMS[topology].items())
    best, name = bearings[-1]
    if best < (0.58 if topology == "three_way" else 0.72) or best - bearings[-2][0] < 0.12:
        return None
    return name


def infer_topology(tracks):
    """Only infer four arms when all are observed; missing traffic cannot prove a T junction."""
    totals = Counter()
    for track in tracks.values():
        endpoints = _track_endpoints(track)
        if endpoints is None:
            continue
        for point in endpoints:
            arm = arm_for_point(point, "four_way")
            if arm:
                totals[arm] += 1
    if sum(totals.values()) >= 20 and all(totals[arm] >= 3 for arm in ARMS["four_way"]):
        return "four_way"
    return "unknown"


def motion_route(start, end, topology):
    """Infer a schematic axis from dominant image motion, never a geographic road."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    if abs(dx) >= 1.5 * abs(dy) and abs(dx) >= 0.10:
        left, right = ("Запад", "Восток") if topology == "four_way" else ("Юго-запад", "Юго-восток")
        return (left, right) if dx > 0 else (right, left)
    if abs(dy) >= 1.5 * abs(dx) and abs(dy) >= 0.10:
        if topology == "four_way":
            return ("Север", "Юг") if dy > 0 else ("Юг", "Север")
        # Without a visible branch we cannot distinguish the two lower arms.
        x = (start[0] + end[0]) / 2
        branch = "Юго-запад" if x < 0.38 else "Юго-восток" if x > 0.62 else None
        if branch is not None:
            return ("Север", branch) if dy > 0 else (branch, "Север")
    return None


def build_cartogram(events, tracks, geometry):
    preference = geometry.get("topology", "auto")
    topology = infer_topology(tracks) if preference == "auto" else preference
    counted_by_category = Counter(event.get("category", "unknown") for event in events)
    if topology not in ARMS:
        return {"topology": "unknown", "preference": preference, "arms": [], "matrix": [],
                "directions": [], "direction_matrix": [],
                "source": geometry.get("topology_source", "auto"),
                "routed": 0, "motion_estimated": 0, "user_directions": 0,
                "unresolved": len(events), "total": len(events), "coverage": 0.0,
                "counted_by_category": _category_rows(counted_by_category),
                "unresolved_by_category": _category_rows(counted_by_category)}
    matrix = Counter()
    unresolved = 0
    unresolved_by_category = Counter()
    motion_estimated = 0
    user_directions = 0
    for event in events:
        category = event.get("category", "unknown")
        if (geometry.get("mode", "manual") == "manual" and event.get("from_direction") in ARMS[topology]
                and event.get("to_direction") in ARMS[topology]
                and event["from_direction"] != event["to_direction"]):
            matrix[(event["from_direction"], event["to_direction"], category)] += 1
            user_directions += 1
            continue
        track = tracks.get(str(event["tracker_id"])) if event.get("tracker_id") is not None else None
        endpoints = _track_endpoints(track) if track is not None else None
        if endpoints is None:
            # A manually added event has no track; direction names alone do not
            # tell us where its line lies in the frame.
            unresolved += 1
            unresolved_by_category[category] += 1
            continue
        start, end = endpoints
        if hypot(end[0] - start[0], end[1] - start[1]) < 0.10:
            unresolved += 1
            unresolved_by_category[category] += 1
            continue
        source = arm_for_point(start, topology)
        target = arm_for_point(end, topology)
        if not source or not target or source == target:
            route = motion_route(start, end, topology)
            if route is None:
                unresolved += 1
                unresolved_by_category[category] += 1
                continue
            source, target = route
            motion_estimated += 1
        matrix[(source, target, category)] += 1
    directions = route_catalog(topology)
    direction_numbers = {(row["from"], row["to"]): row["direction"] for row in directions}
    matrix_rows = [{"from": source, "to": target, "category": category, "count": count}
                   for (source, target, category), count in sorted(matrix.items())]
    direction_rows = sorted(
        ({"direction": direction_numbers[(row["from"], row["to"])], **row}
         for row in matrix_rows),
        key=lambda row: (row["direction"], row["category"]))
    routed = sum(matrix.values())
    return {"topology": topology, "preference": preference,
            "source": geometry.get("topology_source", "auto"),
            "arms": list(ARMS[topology]), "total": len(events),
            "routed": routed, "motion_estimated": motion_estimated,
            "user_directions": user_directions,
            "unresolved": unresolved, "coverage": round(routed / len(events), 4) if events else 0.0,
            "counted_by_category": _category_rows(counted_by_category),
            "unresolved_by_category": _category_rows(unresolved_by_category),
            "directions": directions, "direction_matrix": direction_rows,
            "matrix": matrix_rows}
