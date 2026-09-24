import math
import numpy as np


def xy(p):
    return (p["x"], p["y"]) if isinstance(p, dict) else p[:2]


def point_in_zone(point, polygon):
    x, y = xy(point)
    points = [xy(p) for p in polygon]
    inside = False
    for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
        cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
        if abs(cross) < 1e-9 and min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by):
            return True
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
    return inside


def cross_direction(a, b, line, margin=0.003):
    """Finite segment crossing with a dead band. +1/-1 are image-space signs."""
    a, b = np.array(xy(a)), np.array(xy(b))
    c, d = [np.array(xy(p)) for p in line]
    v = d - c
    length = float(np.linalg.norm(v))
    if length < 1e-9:
        return 0

    def cross(u, w):
        return float(u[0] * w[1] - u[1] * w[0])

    s1, s2 = cross(v, a - c) / length, cross(v, b - c) / length
    if s1 * s2 >= 0 or min(abs(s1), abs(s2)) < margin:
        return 0
    hit = a + (b - a) * abs(s1) / (abs(s1) + abs(s2))
    u = float(np.dot(hit - c, v) / (length * length))
    return (1 if s2 > s1 else -1) if 0 <= u <= 1 else 0


def line_events(trajectory, lines):
    """Keep the last stable side while traversing the dead band; count each line once."""
    events = []
    for line in lines:
        anchor = None
        c, d = [xy(p) for p in line["points"]]
        length = math.dist(c, d)
        for p in trajectory:
            x, y = xy(p)
            distance = ((d[0] - c[0]) * (y - c[1]) - (d[1] - c[1]) * (x - c[0])) / max(length, 1e-9)
            if abs(distance) < 0.003:
                continue
            if anchor is not None:
                direction = cross_direction(anchor, p, line["points"])
                if direction:
                    events.append({"id": line["id"], "name": line["name"], "direction": direction, "time": p[2]})
                    break
            anchor = p
    return sorted(events, key=lambda e: e["time"])


def zone_events(trajectory, zones):
    """Include polygon crossings between sampled points, in timestamp order."""
    events = []

    def cross(a, b):
        return a[0] * b[1] - a[1] * b[0]

    for zone in zones:
        if point_in_zone(trajectory[0], zone["points"]):
            events.append((trajectory[0][2], zone))
        polygon = [xy(p) for p in zone["points"]]
        for a, b in zip(trajectory, trajectory[1:]):
            if point_in_zone(a, polygon):
                continue
            delta = (b[0] - a[0], b[1] - a[1])
            fractions = []
            for c, d in zip(polygon, polygon[1:] + polygon[:1]):
                edge = (d[0] - c[0], d[1] - c[1])
                den = cross(delta, edge)
                if abs(den) < 1e-12:
                    continue
                rel = (c[0] - a[0], c[1] - a[1])
                t, u = cross(rel, edge) / den, cross(rel, delta) / den
                if 0 <= t <= 1 and 0 <= u <= 1:
                    fractions.append(t)
            if fractions:
                events.append((a[2] + min(fractions) * (b[2] - a[2]), zone))
    return sorted(events, key=lambda item: item[0])


def manual_assignment(trajectory, config):
    entry = None
    for when, z in zone_events(trajectory, config.get("zones", [])):
        if z["kind"] == "entry" and entry is None:
            entry = (z, when)
        elif z["kind"] == "exit" and entry and when > entry[1]:
            a = entry[0]
            return f"zone_{a['id']}_{z['id']}", f"{a['name']} → {z['name']}", a["id"], z["id"], when
    if not config.get("zones"):
        events = line_events(trajectory, config.get("lines", []))
        if events:
            e = events[0]
            return f"line_{e['id']}_{e['direction']}", f"{e['name']} · {'A → B' if e['direction'] > 0 else 'B → A'}", None, None, e["time"]
    return "unknown", "Не определено", entry[0]["id"] if entry else None, None, trajectory[-1][2]


def resample(trajectory, n=8):
    points = np.array([p[:2] for p in trajectory], dtype=float)
    if np.linalg.norm(np.ptp(points, axis=0)) < 0.03:
        return None
    dist = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    if dist[-1] < 0.03:
        return None
    unique = np.r_[True, np.diff(dist) > 1e-8]
    return np.column_stack([np.interp(np.linspace(0, dist[-1], n), dist[unique], points[unique, dim]) for dim in (0, 1)])
