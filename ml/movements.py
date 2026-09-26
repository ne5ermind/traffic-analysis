from collections import defaultdict
import random
import numpy as np
from sklearn.cluster import DBSCAN
from ml.geometry import resample, manual_assignment, line_events, meaningful_motion
from ml.detectors.base import CLASSES
from ml.topology import assign_path


class MovementClassifier:
    """Fit on a deterministic bounded reservoir, then classify every track."""

    def __init__(self):
        self.centers = []
        self.population = []
        self.kinds = []

    def fit(self, tracks, max_samples=4000):
        reservoir = []
        seen = 0
        rng = random.Random(42)
        for t in tracks:
            if not t["countable"]:
                continue
            feature = resample(t["trajectory"])
            if feature is None:
                continue
            item = (feature, t["class_name"] == "pedestrian")
            seen += 1
            if len(reservoir) < max_samples:
                reservoir.append(item)
            else:
                index = rng.randrange(seen)
                if index < max_samples:
                    reservoir[index] = item
        for pedestrian in (False, True):
            features = [f for f, kind in reservoir if kind == pedestrian]
            if len(features) < 3:
                continue
            data = np.array(features).reshape(-1, 16) / np.sqrt(8)
            labels = DBSCAN(eps=0.10, min_samples=3).fit_predict(data)
            for label in sorted(set(labels) - {-1}):
                cluster = np.array(features)[labels == label]
                self.centers.append(cluster.mean(axis=0))
                self.population.append(len(cluster))
                self.kinds.append(pedestrian)

    def assign(self, track):
        f = resample(track["trajectory"])
        if f is None or not self.centers:
            return "unknown", 0.0
        distances = [
            float(np.sqrt(np.mean(np.sum((f - c) ** 2, axis=1)))) if k == (track["class_name"] == "pedestrian") else float("inf")
            for c, k in zip(self.centers, self.kinds)
        ]
        i = int(np.argmin(distances))
        if distances[i] > 0.14:
            return "unknown", 0.0
        # A geometric diagnostic score, NOT a calibrated probability.
        reliability = min(0.95, max(0.1, 1 - distances[i] / 0.18) * min(1, self.population[i] / 8))
        return f"auto_{i + 1}", round(reliability, 3)


def classify(store, config, progress=lambda: None):
    manual = bool(config.get("zones") or config.get("lines"))
    classifier = MovementClassifier()
    if not manual:
        classifier.fit(store.tracks())
    definitions = {}
    path_sums, path_counts = {}, defaultdict(int)
    lines = defaultdict(int)
    for index, t in enumerate(store.tracks()):
        if index % 250 == 0:
            progress()
        entry = exit_zone = None
        when = t["last_seen"]
        if manual:
            mid, name, entry, exit_zone, when = manual_assignment(t["trajectory"], config)
            reliability = 0.9 if mid != "unknown" else 0
        else:
            route = assign_path(t["trajectory"], config.get("topology", {})) if t["class_name"] != "pedestrian" else None
            if route:
                mid, reliability = f"road_{route[0]['id']}_{route[1]['id']}", .75
            else:
                mid, reliability = classifier.assign(t)
            name = f"{route[0]['label']} → {route[1]['label']}" if route else (f"Направление {mid.split('_')[-1]}" if mid != "unknown" else "Не определено")
        if t["countable"] and mid == "unknown" and not meaningful_motion(t["trajectory"]):
            t["countable"] = 0
            store.db.execute("UPDATE tracks SET countable=0 WHERE id=?", (t["id"],))
        if not t["countable"]:
            mid, name, reliability = "unknown", "Не определено", 0
        store.db.execute(
            "UPDATE tracks SET movement_id=?,entry_zone=?,exit_zone=?,counted_at=?,reliability=? WHERE id=?",
            (mid, entry, exit_zone, when, reliability, t["id"]),
        )
        if t["countable"]:
            feature = resample(t["trajectory"])
            if mid not in definitions:
                definitions[mid] = dict(
                    id=mid, name=name, path=feature.tolist() if feature is not None else [], entry_zone=entry, exit_zone=exit_zone
                )
            if feature is not None:
                path_sums[mid] = path_sums.get(mid, np.zeros_like(feature)) + feature
                path_counts[mid] += 1
            for e in line_events(t["trajectory"], config.get("lines", [])):
                lines[f"{e['id']}:{e['direction']}"] += 1
    for mid, total in path_sums.items():
        definitions[mid]["path"] = (total / path_counts[mid]).tolist()
    store.db.commit()
    return definitions, dict(lines)


def aggregate(store, definitions, duration, interval=900):
    counts = {c: 0 for c in CLASSES}
    moves = {}
    intervals = [
        dict(start=start, end=min(start + interval, duration), **{c: 0 for c in CLASSES}, total=0, pedestrians=0)
        for start in range(0, max(1, int(np.ceil(duration))), interval)
    ]
    diagnostics = dict(
        tracks=0,
        completed_tracks=0,
        unknown_tracks=0,
        discarded_short_tracks=0,
        discarded_stationary_tracks=0,
        stitched_fragments=0,
    )
    confidence_values = []
    for t in store.tracks():
        diagnostics["tracks"] += 1
        diagnostics["stitched_fragments"] += t["fragments"]
        if t["samples"]:
            confidence_values.append(t.get("confidence", 0.0))
        if not t["countable"]:
            diagnostics["discarded_short_tracks" if t["samples"] < 3 else "discarded_stationary_tracks"] += 1
            continue
        cls, mid = t["class_name"], t["movement_id"]
        counts[cls] += 1
        diagnostics["unknown_tracks" if mid == "unknown" else "completed_tracks"] += 1
        if mid not in moves:
            moves[mid] = {
                **definitions.get(mid, {"id": mid, "name": mid}),
                "counts": {c: 0 for c in CLASSES},
                "total": 0,
                "pedestrians": 0,
                "reliability": 0,
                "_n": 0,
            }
        m = moves[mid]
        m["counts"][cls] += 1
        m["pedestrians" if cls == "pedestrian" else "total"] += 1
        m["reliability"] += t["reliability"]
        m["_n"] += 1
        bucket = intervals[min(len(intervals) - 1, int(t["counted_at"] // interval))]
        bucket[cls] += 1
        bucket["pedestrians" if cls == "pedestrian" else "total"] += 1
    for m in moves.values():
        m["reliability"] = round(m["reliability"] / m.pop("_n"), 3)
        m["requires_review"] = m["reliability"] < 0.7
    diagnostics["movements"] = len([m for m in moves if m != "unknown"])
    diagnostics["mean_detection_confidence"] = round(sum(confidence_values) / len(confidence_values), 3) if confidence_values else 0
    return dict(
        counts=counts,
        total_vehicles=sum(v for c, v in counts.items() if c != "pedestrian"),
        pedestrians=counts["pedestrian"],
        movements=list(moves.values()),
        intervals=intervals,
        interval_seconds=interval,
        diagnostics=diagnostics,
    )
