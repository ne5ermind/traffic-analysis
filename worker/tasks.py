import json
import logging
import shutil
import subprocess
import threading
import time
from sqlalchemy import update
from backend.db import Session, Project, init_db
from backend.storage import storage
from backend.locking import project_lock
from ml.pipeline import run_pipeline, Cancelled
from ml.artifacts import TrackStore
from ml.movements import classify, aggregate
from ml.audit import audit_result
from ml.local_vlm import analyze_scene, apply_review_flags, review_video, LOCAL_VLM_MODEL, LOCAL_VLM_ENABLED

from ml.topology import select_topology, attach_routes

logger = logging.getLogger(__name__)


def analyze(project_id, run_id, profile="balanced", recalculate=False):
    init_db()
    stop = threading.Event()
    started = time.monotonic()

    def patch(**values):
        with Session() as s:
            s.execute(
                update(Project)
                .where(Project.id == project_id, Project.run_id == run_id, Project.status.in_(["queued", "processing"]))
                .values(**values)
            )
            s.commit()

    def check():
        with Session() as s:
            p = s.get(Project, project_id)
            if p is None or p.run_id != run_id or p.status not in ("processing", "queued"):
                raise Cancelled()

    def report(**values):
        check()
        with Session() as s:
            p = s.get(Project, project_id)
            progress = {**p.progress, **values}
        patch(progress=progress, heartbeat=time.time())

    def heartbeat():
        while not stop.wait(5):
            try:
                patch(heartbeat=time.time())
            except Exception:
                logger.exception("Heartbeat failed")

    pulse = threading.Thread(target=heartbeat, daemon=True)
    run_dir = storage.path(project_id, f"runs/{run_id}")
    try:
        with project_lock(project_id, blocking=True):
            check()
            with Session() as s:
                p = s.get(Project, project_id)
            patch(status="processing", heartbeat=time.time(), error=None)
            pulse.start()
            run_dir.mkdir(parents=True, exist_ok=True)
            target = run_dir / "tracks.sqlite"
            report(stage="scene_analysis", percent=0, eta=None)
            scene = analyze_scene(storage.path(project_id, "source.mp4"), check)
            topology = select_topology(p.config, scene)
            if LOCAL_VLM_ENABLED and not topology.get("usable"):
                report(stage="scene_refinement", percent=0, eta=None)
                second_scene = analyze_scene(storage.path(project_id, "source.mp4"), check, model=LOCAL_VLM_MODEL)
                if second_scene.get("status") == "ok":
                    second_scene["first_opinion"] = scene
                    scene = second_scene
                    topology = select_topology(p.config, scene)
            (run_dir / "scene.json").write_text(json.dumps({"scene": scene, "intersection": topology}, ensure_ascii=False), encoding="utf-8")
            analysis_config = {**p.config, "topology": topology}
            if recalculate:
                if not p.result_run:
                    raise ValueError("Сначала выполните анализ видео")
                source = storage.path(project_id, f"runs/{p.result_run}/tracks.sqlite")
                # SQLite backup includes WAL and is consistent even after interruption.
                import sqlite3

                with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
                    src.backup(dst)
                report(stage="movements", percent=50)
                store = TrackStore(target)
                try:
                    definitions, lines = classify(store, analysis_config, check)
                    result = aggregate(store, definitions, p.video["duration"])
                    result.update({k: p.result[k] for k in ("model", "device", "profile", "duration") if k in p.result})
                    result.update(calibration=p.config, line_crossings=lines, elapsed=round(time.monotonic() - started, 2))
                    result["diagnostics"]["detections"] = p.result.get("diagnostics", {}).get("detections", 0)
                    result["ai_audit"] = audit_result(result, p.result.get("ai_audit", {}).get("video_quality"))
                finally:
                    store.close()
            else:
                result = run_pipeline(storage.path(project_id, "source.mp4"), target, p.video, analysis_config, profile, report=report, check=check)
            result.update(scene_analysis=scene, intersection=topology, calibration=p.config)
            attach_routes(result)
            report(stage="ai_review", percent=97, eta=None)
            result["local_vlm"] = review_video(storage.path(project_id, "source.mp4"), result, target, check)
            apply_review_flags(result, result["local_vlm"])
            # Browser compatible video; overlay is streamed separately and toggled in UI.
            playback = storage.path(project_id, "playback.mp4")
            if not playback.exists():
                report(stage="preparing_video", percent=98, eta=None)
                temp = run_dir / "playback.mp4"
                log_path = run_dir / "ffmpeg.log"
                with log_path.open("w") as log:
                    proc = subprocess.Popen(
                        [
                            "ffmpeg",
                            "-nostdin",
                            "-y",
                            "-v",
                            "error",
                            "-i",
                            str(storage.path(project_id, "source.mp4")),
                            "-an",
                            "-vf",
                            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                            "-c:v",
                            "libx264",
                            "-preset",
                            "veryfast",
                            "-crf",
                            "24",
                            "-pix_fmt",
                            "yuv420p",
                            "-movflags",
                            "+faststart",
                            str(temp),
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=log,
                    )
                    try:
                        while proc.poll() is None:
                            check()
                            time.sleep(0.3)
                        if proc.returncode:
                            raise ValueError("Не удалось подготовить видео для браузера. Проверьте запись и свободное место.")
                    finally:
                        if proc.poll() is None:
                            proc.terminate()
                            try:
                                proc.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                                proc.wait()
                check()
                temp.replace(playback)
            result["elapsed"] = round(time.monotonic() - started, 2)
            (run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            check()
            patch(
                result=result,
                result_run=run_id,
                status="completed",
                progress={
                    **p.progress,
                    "percent": 100,
                    "stage": "completed",
                    "processed_frames": p.video["frame_count"],
                    "total_frames": p.video["frame_count"],
                    "elapsed": result["elapsed"],
                    "model": result.get("model"),
                    "device": result.get("device"),
                },
            )
    except Cancelled:
        shutil.rmtree(run_dir, ignore_errors=True)
    except Exception as e:
        logger.exception("Analysis failed for %s", project_id)
        message = str(e)
        if isinstance(e, OSError) and e.errno == 28:
            message = "Недостаточно места на диске"
        patch(status="failed", error=f"Анализ не завершён: {message[:800]}")
    finally:
        stop.set()
        if pulse.is_alive():
            pulse.join(timeout=6)
