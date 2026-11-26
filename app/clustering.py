"""Deterministic DBSCAN on directed, spatially resampled image trajectories."""
from collections import Counter
import numpy as np
from scipy.spatial import cKDTree


def trajectory_features(track, samples=12):
    points = np.asarray(track.get("points", [track.get("start"), track.get("end")]), dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 2 or not np.isfinite(points).all():
        return None
    if np.any(points < 0) or np.any(points > 1):
        return None
    lengths = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    if lengths[-1] < 0.08 or track.get("seen", 0) < 3:
        return None
    keep = np.r_[True, np.diff(lengths) > 1e-8]
    lengths, points = lengths[keep], points[keep]
    positions = np.linspace(0, lengths[-1], samples)
    curve = np.column_stack([np.interp(positions, lengths, points[:, axis]) for axis in (0, 1)])
    # Directed ordering distinguishes opposing flows, including along one lane.
    return curve.reshape(-1) / np.sqrt(samples)


def cluster_tracks(tracks, eps=0.12, min_samples=3):
    ids, features = [], []
    for identity, track in sorted(tracks.items()):
        try:
            feature = trajectory_features(track)
        except (ValueError, TypeError):
            feature = None
        if feature is not None:
            ids.append(identity)
            features.append(feature)
    if not features:
        return {"method": "DBSCAN", "eps": eps, "min_samples": min_samples,
                "assignments": {}, "clusters": [], "noise_tracks": len(tracks)}
    tree = cKDTree(features)
    labels = np.full(len(ids), -2, dtype=int)
    cluster = 0
    for index in range(len(ids)):
        if labels[index] != -2:
            continue
        neighbors = sorted(tree.query_ball_point(features[index], eps))
        if len(neighbors) < min_samples:
            labels[index] = -1
            continue
        labels[index] = cluster
        pending, visited = list(neighbors), set(neighbors)
        while pending:
            neighbor = pending.pop()
            if labels[neighbor] == -1:
                labels[neighbor] = cluster
            if labels[neighbor] != -2:
                continue
            labels[neighbor] = cluster
            adjacent = sorted(tree.query_ball_point(features[neighbor], eps))
            if len(adjacent) >= min_samples:
                pending.extend(item for item in adjacent if item not in visited)
                visited.update(adjacent)
        cluster += 1
    assignments = {identity: int(label) + 1 for identity, label in zip(ids, labels) if label >= 0}
    summaries = []
    for label in range(cluster):
        members = [identity for identity, current in zip(ids, labels) if current == label]
        centroid = np.mean([features[i] for i, current in enumerate(labels) if current == label], axis=0)
        summaries.append({"id": label + 1, "track_count": len(members),
                          "polyline": (centroid.reshape(-1, 2) * np.sqrt(12)).round(5).tolist()})
    return {"method": "DBSCAN", "eps": eps, "min_samples": min_samples,
            "assignments": assignments, "clusters": summaries,
            "noise_tracks": len(tracks) - len(assignments)}


def cluster_counts(artifact, events):
    counts = Counter()
    unresolved = 0
    for event in events:
        cluster = artifact.get("assignments", {}).get(str(event.get("tracker_id")))
        if cluster is None:
            unresolved += 1
        else:
            counts[cluster, event["category"]] += 1
    return {**artifact, "counts": [{"cluster": cluster, "category": category, "count": count}
                                    for (cluster, category), count in sorted(counts.items())],
            "unresolved_events": unresolved, "total": len(events)}
