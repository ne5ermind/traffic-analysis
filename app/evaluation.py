"""Count errors and CLEAR-style tracking metrics on explicit annotated frames.

Frame IDs/times must be aligned by the annotator. Unannotated frames are excluded.
Tracking association first preserves valid previous matches, then maximizes IoU.
IDF1 uses a global one-to-one trajectory assignment, not the framewise ID switches.
"""
from collections import Counter
import math
import numpy as np
from scipy.optimize import linear_sum_assignment


def count_metrics(expected, actual):
    keys = sorted(expected.keys() | actual.keys())
    errors = [actual[key] - expected[key] for key in keys]
    total = sum(expected.values())
    absolute = sum(abs(error) for error in errors)
    return {"ground_truth": total, "predicted": sum(actual.values()), "absolute_error": absolute,
            "mae": absolute / len(keys) if keys else 0.0,
            "rmse": math.sqrt(sum(error * error for error in errors) / len(keys)) if keys else 0.0,
            "wape": absolute / total if total else None,
            "relative_error": (sum(actual.values()) - total) / total if total else None,
            "rows": [{"from": a, "to": b, "category": c, "ground_truth": expected[a, b, c],
                      "predicted": actual[a, b, c]} for a, b, c in keys]}


def iou(a, b):
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, right - left) * max(0, bottom - top)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0.0


def validate_frames(frames):
    if not isinstance(frames, list) or not frames:
        raise ValueError("Нужен непустой массив frames с t и objects")
    previous = -1.0
    for frame in frames:
        t = float(frame["t"])
        if not math.isfinite(t) or t < 0 or t <= previous:
            raise ValueError("Время frames должно возрастать и быть конечным")
        previous = t
        identities = set()
        for item in frame["objects"]:
            identity = str(item["tracker_id"])
            box = item["box"]
            if identity in identities:
                raise ValueError("Повтор tracker_id в одном кадре")
            identities.add(identity)
            if (len(box) != 4 or not all(math.isfinite(x) and 0 <= x <= 1 for x in box)
                    or box[0] >= box[2] or box[1] >= box[3]):
                raise ValueError("box: нормализованные x1,y1,x2,y2, положительная площадь")
            if item["category"] not in ("pedestrian", "bicycle", "car", "motorcycle", "bus", "truck"):
                raise ValueError("Неизвестная категория эталона")


def tracking_metrics(reference, predicted, threshold=0.5):
    validate_frames(reference)
    predicted_by_time = {round(float(frame["t"]), 4): frame["objects"] for frame in predicted}
    gt_counts, prediction_counts, overlaps = Counter(), Counter(), Counter()
    last_match = {}
    true_positive = false_positive = false_negative = switches = 0
    for frame in reference:
        gt = frame["objects"]
        prediction = predicted_by_time.get(round(float(frame["t"]), 4), [])
        for item in gt:
            gt_counts[str(item["tracker_id"])] += 1
        for item in prediction:
            prediction_counts[str(item["tracker_id"])] += 1
        scores = np.zeros((len(gt), len(prediction)))
        for g, truth in enumerate(gt):
            for p, estimate in enumerate(prediction):
                if truth["category"] == estimate["category"]:
                    scores[g, p] = iou(truth["box"], estimate["box"])
                if scores[g, p] >= threshold:
                    overlaps[str(truth["tracker_id"]), str(estimate["tracker_id"])] += 1
        matched = []
        used_gt, used_prediction = set(), set()
        for g, truth in enumerate(gt):
            old = last_match.get(str(truth["tracker_id"]))
            for p, estimate in enumerate(prediction):
                if old == str(estimate["tracker_id"]) and scores[g, p] >= threshold and p not in used_prediction:
                    matched.append((g, p)); used_gt.add(g); used_prediction.add(p)
                    break
        available_g = [g for g in range(len(gt)) if g not in used_gt]
        available_p = [p for p in range(len(prediction)) if p not in used_prediction]
        if available_g and available_p:
            subset = scores[np.ix_(available_g, available_p)]
            # Match cardinality before IoU; invalid matches are dropped.
            reward = np.where(subset >= threshold, 1000 + subset, 0)
            row, column = linear_sum_assignment(-reward)
            matched.extend((available_g[g], available_p[p]) for g, p in zip(row, column)
                           if subset[g, p] >= threshold)
        for g, p in matched:
            gid, pid = str(gt[g]["tracker_id"]), str(prediction[p]["tracker_id"])
            switches += gid in last_match and last_match[gid] != pid
            last_match[gid] = pid
        true_positive += len(matched)
        false_negative += len(gt) - len(matched)
        false_positive += len(prediction) - len(matched)
    gids, pids = sorted(gt_counts), sorted(prediction_counts)
    identity_true_positive = 0
    if gids and pids:
        matrix = np.array([[overlaps[g, p] for p in pids] for g in gids])
        row, column = linear_sum_assignment(-matrix)
        identity_true_positive = int(matrix[row, column].sum())
    gt_total, predicted_total = sum(gt_counts.values()), sum(prediction_counts.values())
    precision = true_positive / predicted_total if predicted_total else None
    recall = true_positive / gt_total if gt_total else None
    return {"iou_threshold": threshold, "annotated_frames": len(reference),
            "ground_truth_detections": gt_total, "predicted_detections": predicted_total,
            "tp": true_positive, "fp": false_positive, "fn": false_negative, "id_switches": switches,
            "precision": precision, "recall": recall,
            "f1": 2 * true_positive / (gt_total + predicted_total) if gt_total + predicted_total else None,
            "mota": 1 - (false_negative + false_positive + switches) / gt_total if gt_total else None,
            "idf1": 2 * identity_true_positive / (gt_total + predicted_total) if gt_total + predicted_total else None}
