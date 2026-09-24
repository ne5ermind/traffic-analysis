import time
from collections import defaultdict
import cv2
import numpy as np
from ml.artifacts import TrackStore
from ml.detectors.base import CLASSES
from ml.detectors.factory import create_detector
from ml.detectors.yolo_detector import PROFILES
from ml.trackers.bytetrack import ByteTracker
from ml.movements import classify, aggregate
from ml.audit import audit_result


class Cancelled(Exception):
    pass


def can_stitch(track, point, when, cls):
    """Conservative short-gap motion gate; never merge concurrent tracks/re-entry."""
    gap = when - track["last_seen"]
    if gap <= 0.05 or gap > 1.0 or cls != max(track["votes"], key=track["votes"].get):
        return False
    path = track["trajectory"]
    if len(path) < 3:
        return False
    a, b = path[-3], path[-1]
    dt = b[2] - a[2]
    if dt <= 0:
        return False
    velocity = (np.array(b[:2]) - a[:2]) / dt
    if np.linalg.norm(velocity) < 0.01:
        return False
    prediction = np.array(b[:2]) + velocity * gap
    return float(np.linalg.norm(prediction - point)) < 0.025 and float(np.dot(np.array(point) - b[:2], velocity)) > 0


def run_pipeline(video_path, db_path, metadata, config, profile="balanced", detector=None, report=lambda **kw: None, check=lambda: None):
    start = time.monotonic()
    report(stage="loading_model", processed_frames=0, total_frames=metadata["frame_count"], percent=0, elapsed=0)
    detector = detector or create_detector(profile)
    stride = PROFILES[profile]["stride"]
    fps = metadata["fps"]
    tracker = ByteTracker(fps / stride)
    store = TrackStore(db_path)
    cap = cv2.VideoCapture(str(video_path))
    active, aliases = {}, {}
    frame_index = detections_count = 0
    quality_stats = {"samples": 0, "sharpness": 0.0, "brightness": 0.0, "contrast": 0.0}
    last_report = 0
    width, height = metadata["width"], metadata["height"]
    last_time = -1.0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_index += 1
            # Decoder presentation timestamps handle variable frame-rate phone footage.
            pts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            when = pts if pts > last_time else (frame_index - 1) / fps
            when = max(when, last_time)
            last_time = when
            if frame_index % stride != 1 % stride:
                continue
            check()
            height, width = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = cv2.resize(gray, (max(1, width // 4), max(1, height // 4)), interpolation=cv2.INTER_AREA)
            quality_stats["samples"] += 1
            quality_stats["sharpness"] += float(cv2.Laplacian(small, cv2.CV_64F).var())
            quality_stats["brightness"] += float(small.mean())
            quality_stats["contrast"] += float(small.std())
            detections = detector.predict(frame)
            detections_count += len(detections)
            tracked = tracker.update(detections, frame.shape[:2])
            present = {aliases.get(o["track_id"], o["track_id"]) for o in tracked}
            for obj in tracked:
                raw_id = obj["track_id"]
                tid = aliases.get(raw_id, raw_id)
                bbox = obj["bbox"]
                point = np.clip([(bbox[0] + bbox[2]) / (2 * width), bbox[3] / height], 0, 1)
                cls = CLASSES[obj["class_id"]]
                if tid not in active:
                    candidates = [k for k, t in active.items() if k not in present and can_stitch(t, point, when, cls)]
                    if len(candidates) == 1:
                        tid = candidates[0]
                        aliases[raw_id] = tid
                        active[tid]["fragments"] += 1
                    else:
                        active[tid] = dict(
                            id=tid, first_seen=when, last_seen=when, trajectory=[], votes=defaultdict(float), confidence_sum=0, samples=0, fragments=0
                        )
                t = active[tid]
                if t["trajectory"]:
                    point = 0.65 * point + 0.35 * np.array(t["trajectory"][-1][:2])
                t["last_seen"] = when
                t["votes"][cls] += obj["confidence"]
                t["confidence_sum"] += obj["confidence"]
                t["samples"] += 1
                t["trajectory"].append([float(point[0]), float(point[1]), when])
                if len(t["trajectory"]) > 512:
                    t["trajectory"] = t["trajectory"][::2] + [t["trajectory"][-1]]
                normalized_box = [bbox[0] / width, bbox[1] / height, bbox[2] / width, bbox[3] / height]
                store.observation(when, tid, normalized_box, point.tolist(), obj["confidence"])
                present.add(tid)
            for tid in list(active):
                if when - active[tid]["last_seen"] > tracker.buffer_seconds + 1:
                    store.save_track(active.pop(tid))
                    aliases = {k: v for k, v in aliases.items() if v != tid}
            if time.monotonic() - last_report >= 1:
                store.db.commit()
                elapsed = time.monotonic() - start
                report(
                    stage="detecting",
                    processed_frames=frame_index,
                    total_frames=metadata["frame_count"],
                    percent=min(94, round(frame_index / metadata["frame_count"] * 94, 1)),
                    elapsed=round(elapsed, 1),
                    device=detector.device,
                    model=detector.model_name,
                    eta=round(elapsed / frame_index * max(0, metadata["frame_count"] - frame_index)) if elapsed > 20 else None,
                )
                last_report = time.monotonic()
        if frame_index == 0:
            raise ValueError("Не удалось прочитать видео")
        if frame_index < metadata["frame_count"] * 0.9:
            raise ValueError(f"Декодирование прервано: прочитано {frame_index} из {metadata['frame_count']} кадров. Проверьте целостность видео.")
        for track in active.values():
            store.save_track(track)
        store.db.commit()
        report(stage="movements", percent=96, processed_frames=frame_index, total_frames=frame_index)
        definitions, lines = classify(store, config, check)
        result = aggregate(store, definitions, max(metadata["duration"], last_time))
        result.update(
            model=detector.model_name,
            device=detector.device,
            profile=profile,
            elapsed=round(time.monotonic() - start, 2),
            line_crossings=lines,
            calibration=config,
            duration=metadata["duration"],
        )
        result["diagnostics"]["detections"] = detections_count
        if quality_stats["samples"]:
            for key in ("sharpness", "brightness", "contrast"):
                quality_stats[key] /= quality_stats["samples"]
        result["ai_audit"] = audit_result(result, quality_stats)
        check()
        return result
    finally:
        cap.release()
        store.close()
