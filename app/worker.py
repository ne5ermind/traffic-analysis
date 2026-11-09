"""Run with `python -m app.worker`; inference stays outside the web process."""
import argparse
import fcntl
import json
import math
import os
import time
from datetime import datetime, timezone
from uuid import uuid4

from .geometry import PassageCounter, UniqueTrackCounter
from .sampling import FrameSampler, budgeted_fps
from .storage import ROOT, connection, init, resolve_data_path, resolve_model_path


CATEGORY_BY_CLASS = {
    0: "pedestrian",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


def clean_detection(identity, class_id, xyxy, confidence, width, height):
    """Validate and clip one tracker result before geometry/JSON processing."""
    try:
        raw_identity = float(identity)
        raw_class_id = float(class_id)
        confidence = float(confidence)
        x1, y1, x2, y2 = (float(value) for value in xyxy)
    except (TypeError, ValueError, OverflowError):
        return None
    if (not math.isfinite(raw_identity) or not raw_identity.is_integer()
            or not math.isfinite(raw_class_id) or not raw_class_id.is_integer()
            or raw_identity < 0
            or not math.isfinite(confidence)
            or not all(math.isfinite(value) for value in (x1, y1, x2, y2))
            or width <= 0 or height <= 0):
        return None
    identity, class_id = int(raw_identity), int(raw_class_id)
    if class_id not in CATEGORY_BY_CLASS:
        return None
    x1, x2 = max(0.0, min(float(width), x1)), max(0.0, min(float(width), x2))
    y1, y2 = max(0.0, min(float(height), y1)), max(0.0, min(float(height), y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return identity, class_id, (x1, y1, x2, y2), min(1.0, max(0.0, confidence))


def now():
    return datetime.now(timezone.utc).isoformat()


def claim():
    with connection() as db:
        db.execute("BEGIN IMMEDIATE")
        job = db.execute("SELECT * FROM runs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
        if job:
            db.execute("UPDATE runs SET status='running', started_at=?, heartbeat=? WHERE id=?", (now(), now(), job["id"]))
            return dict(job)


def run(job):
    import av

    with connection() as db:
        video = db.execute("SELECT * FROM videos WHERE id=?", (job["video_id"],)).fetchone()
        if not video:
            raise ValueError("Видеозапись удалена")
        video = dict(video)
    geometry = json.loads(job["geometry"])
    automatic = geometry.get("mode") == "automatic"
    if automatic:
        counter = UniqueTrackCounter()
    else:
        entry = {item["name"]: item["points"] for item in geometry["entries"]}
        exit_ = {item["name"]: item["points"] for item in geometry["exits"]}
        counter = PassageCounter(entry, exit_, geometry.get("roi", []), confirmation=2)
    ensemble = job["tracker"] == "supervision-bytetrack"
    sampler = None
    effective_fps = None
    if ensemble:
        from .ensemble import EnsembleFrameProcessor, FastFrameProcessor

        configuration = json.loads(job["model"])
        if configuration.get("pipeline") == "fast" and len(configuration.get("models", [])) == 1:
            target_fps = float(configuration["sample_fps"])
            effective_fps = target_fps
            sampler = FrameSampler(target_fps)
            weights = resolve_model_path(configuration["models"][0])
            processor = FastFrameProcessor(weights, fps=target_fps,
                                           image_size=int(configuration["imgsz"]))
        elif configuration.get("fusion") == "wbf" and len(configuration.get("models", [])) == 2:
            weights = [resolve_model_path(value) for value in configuration["models"]]
            processor = EnsembleFrameProcessor(*weights, fps=video["fps"] or 25)
        else:
            raise ValueError("Некорректная конфигурация ансамбля")
    else:
        # Runs queued before the ensemble upgrade retain their Ultralytics tracker.
        from .model import load_yolo

        weights = resolve_model_path(job["model"])
        if not weights.is_file():
            raise FileNotFoundError(f"Нет весов модели: {weights}. Скопируйте yolo11m.pt в data/models/.")
        model = load_yolo(weights)
    container = av.open(str(resolve_data_path(video["path"])))
    stream = container.streams.video[0]
    total = max(video["duration"] or 0, 0.001)
    diagnostics = ROOT / "runs" / job["id"]
    diagnostics.mkdir(parents=True, exist_ok=True)
    seen_tracks = set()
    track_paths = {}
    last_update = 0.0
    processed_frames = 0
    decoded_frames = 0
    started_wall = time.monotonic()
    first_sample_pts = None
    last_budget_check = None
    timestamp_origin = None

    def update_progress(pts):
        nonlocal last_update
        if pts - last_update < 1:
            return False
        last_update = pts
        with connection() as db:
            state = db.execute("SELECT cancelled FROM runs WHERE id=?", (job["id"],)).fetchone()
            if state and state["cancelled"]:
                db.execute("UPDATE runs SET status='cancelled',finished_at=?,message=? WHERE id=?",
                           (now(), "Остановлено пользователем", job["id"]))
                return True
            db.execute("UPDATE runs SET progress=?,heartbeat=? WHERE id=?",
                       (min(0.99, pts / total), now(), job["id"]))
        return False

    frame_index = {}
    with (diagnostics / "trajectories.jsonl").open("w", encoding="utf-8") as traces, \
         (diagnostics / "detections.jsonl").open("wb") as frames_file:
        for frame_num, frame in enumerate(container.decode(stream)):
            decoded_frames += 1
            raw_pts = (float(frame.pts * frame.time_base) if frame.pts is not None
                       else frame_num / float(video["fps"] or 25))
            if timestamp_origin is None:
                timestamp_origin = raw_pts
            # Uploaded video playback and the HTTP API use a zero-based clock;
            # container PTS may start at an arbitrary or negative offset.
            pts = max(0.0, raw_pts - timestamp_origin)
            if sampler is not None and not sampler.accept(pts):
                if update_progress(pts):
                    container.close()
                    return
                continue
            image = frame.to_ndarray(format="bgr24")
            processed_frames += 1
            if first_sample_pts is None:
                first_sample_pts = pts
                last_budget_check = pts
            if ensemble:
                detections = processor.process_frame(image)
                if (detections.tracker_id is None or detections.class_id is None
                        or detections.confidence is None):
                    tracked = iter(())
                else:
                    tracked = ((identity, class_id, box, confidence)
                               for box, confidence, class_id, identity in zip(
                                   detections.xyxy, detections.confidence,
                                   detections.class_id, detections.tracker_id))
            else:
                result = model.track(image, persist=True, tracker=job["tracker"], verbose=False,
                                     conf=0.10, iou=0.7,
                                     classes=list(CATEGORY_BY_CLASS))[0]
                tracked = ((box.id.item(), box.cls.item(), box.xyxy[0].tolist(),
                            box.conf.item()) for box in result.boxes if box.id is not None)
            # A malformed model row must never poison geometry or JSON with
            # NaN/Inf.  If a tracker emits the same ID twice, keep its strongest
            # detection so one video frame counts as one observation.
            cleaned = {}
            for raw_identity, raw_class, raw_box, raw_confidence in tracked:
                item = clean_detection(raw_identity, raw_class, raw_box, raw_confidence,
                                       frame.width, frame.height)
                if item is None:
                    continue
                previous = cleaned.get(item[0])
                if previous is None or item[3] > previous[3]:
                    cleaned[item[0]] = item
            objects = []
            for identity, class_id, xyxy, confidence in cleaned.values():
                category = CATEGORY_BY_CLASS[class_id]
                x1, y1, x2, y2 = xyxy
                anchor = ((x1 + x2) / (2 * frame.width), y2 / frame.height)
                seen_tracks.add(identity)
                path = track_paths.setdefault(str(identity), {"start": anchor, "first_s": pts,
                                                            "end": anchor, "last_s": pts, "seen": 0})
                path["end"] = anchor
                path["last_s"] = pts
                path["seen"] += 1
                objects.append({"id": identity, "tracker_id": identity, "class_id": class_id,
                                "category": category, "xyxy": [x1, y1, x2, y2],
                                "box": [round(x1 / frame.width, 5), round(y1 / frame.height, 5),
                                        round(x2 / frame.width, 5), round(y2 / frame.height, 5)],
                                "confidence": round(confidence, 3)})
                traces.write(json.dumps({"t": pts, "id": identity, "tracker_id": identity,
                                         "class_id": class_id, "class": category,
                                         "point": anchor, "box": [x1, y1, x2, y2],
                                         "confidence": confidence}, ensure_ascii=False) + "\n")
                box_size = ((x2 - x1) / frame.width, (y2 - y1) / frame.height)
                for event in counter.feed(
                        identity, anchor, pts, category, confidence, box_size=box_size):
                    details = {"trail": event["trail"]}
                    if event.get("motion"):
                        details["motion"] = event["motion"]
                    with connection() as db:
                        db.execute("""INSERT INTO events(id,run_id,tracker_id,category,from_direction,
                            to_direction,time_s,start_s,confidence,status,origin,details,created_at,updated_at)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (str(uuid4()), job["id"], identity, event["category"], event["from_direction"],
                             event["to_direction"], event["time_s"], event["start_s"],
                             event["confidence"],
                             "auto_accept" if automatic else "review", "automatic",
                             json.dumps(details), now(), now()))
            frame_index.setdefault(str(int(pts)), frames_file.tell())
            frames_file.write((json.dumps({"t": pts, "objects": objects}) + "\n").encode("utf-8"))
            if (sampler is not None and total >= 120 and
                    pts - last_budget_check >= 30):
                last_budget_check = pts
                adjusted = budgeted_fps(effective_fps, pts - first_sample_pts,
                                        time.monotonic() - started_wall)
                if adjusted < effective_fps:
                    sampler.set_rate(adjusted)
                    effective_fps = adjusted
                    set_frame_rate = getattr(processor, "set_frame_rate", None)
                    if set_frame_rate is not None:
                        set_frame_rate(effective_fps)
                    with connection() as db:
                        db.execute("UPDATE runs SET message=? WHERE id=?",
                                   (f"Для соблюдения времени частота анализа снижена до "
                                    f"{effective_fps:g} кадр/с. Короткие объекты могут быть пропущены.", job["id"]))
            if update_progress(pts):
                container.close()
                return
    container.close()
    for name, data in (("detections-index.json", frame_index), ("tracks.json", track_paths)):
        temporary = diagnostics / (name + ".tmp")
        temporary.write_text(json.dumps(data), encoding="utf-8")
        temporary.replace(diagnostics / name)
    with connection() as db:
        if db.execute("SELECT cancelled FROM runs WHERE id=?", (job["id"],)).fetchone()[0]:
            db.execute("UPDATE runs SET status='cancelled',finished_at=?,message=? WHERE id=?",
                       (now(), "Остановлено пользователем", job["id"]))
            return
        count = db.execute("SELECT COUNT(*) FROM events WHERE run_id=?", (job["id"],)).fetchone()[0]
        elapsed = max(0.001, time.monotonic() - started_wall)
        db.execute("UPDATE runs SET status='completed',progress=1,finished_at=?,message=? WHERE id=?",
                   (now(), f"Треков: {len(seen_tracks)}; кандидатов: {count}; "
                    f"кадров: {processed_frames}/{decoded_frames}; обработано за {elapsed:.0f} с"
                    + (f"; частота: до {effective_fps:g} кадр/с" if sampler else ""), job["id"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    options = parser.parse_args()
    init()
    lock_path = ROOT / "worker.lock"
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Другой worker уже выполняется")
        with connection() as db:
            db.execute("UPDATE runs SET status='failed', message='Worker interrupted', finished_at=? WHERE status='running'", (now(),))
        while True:
            job = claim()
            if job:
                try:
                    run(job)
                except Exception as exc:
                    with connection() as db:
                        db.execute("UPDATE runs SET status='failed', message=?, finished_at=? WHERE id=?",
                                   (str(exc)[:500], now(), job["id"]))
            elif options.once:
                return
            else:
                time.sleep(1)


if __name__ == "__main__":
    main()
