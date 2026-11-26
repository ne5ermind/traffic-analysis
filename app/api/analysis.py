

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from ..storage import ROOT, connection, portable_model_path, rows
from .common import now, one
from .schemas import RunIn, RunUpdate, TopologyIn

app = APIRouter()

@app.post("/api/runs", tags=["Анализ"], summary="Запустить анализ")
def create_run(payload: RunIn):
    identity = str(uuid4())
    with connection() as db:
        if payload.scene_id:
            scene = one(db, "scenes", payload.scene_id)
            if payload.video_id and scene["video_id"] != payload.video_id:
                raise HTTPException(422, "Сцена относится к другому видео")
        elif payload.video_id:
            one(db, "videos", payload.video_id)
            automatic = json.dumps({"mode": "automatic", "entries": [], "exits": [], "roi": []})
            scene = db.execute("SELECT * FROM scenes WHERE video_id=? AND geometry=? LIMIT 1",
                               (payload.video_id, automatic)).fetchone()
            if scene is None:
                scene_id = str(uuid4())
                db.execute("INSERT INTO scenes VALUES(?,?,?,?,?)",
                           (scene_id, payload.video_id, "Автоматический подсчёт", automatic, now()))
                scene = one(db, "scenes", scene_id)
            else:
                scene = dict(scene)
        else:
            raise HTTPException(422, "Выберите видео или сцену")
        # Snapshot the scene so later editor changes do not rewrite old analyses.
        project = Path(__file__).resolve().parents[2]
        def model_path(value):
            raw = Path(value)
            if raw.is_absolute():
                path = raw.resolve()
            elif raw.parts[:2] == ("data", "models"):
                path = (project / raw).resolve()
            elif raw.parts[:1] == ("models",):
                path = (project / "data" / raw).resolve()
            else:
                raise HTTPException(422, "Вес модели должен быть в data/models/*.pt")
            roots = ((project / "data" / "models").resolve(), (ROOT / "models").resolve())
            if path.suffix.lower() != ".pt" or not any(path.is_relative_to(root) for root in roots):
                raise HTTPException(422, "Вес модели должен быть в data/models/*.pt")
            return portable_model_path(path)

        primary = model_path(payload.model or (
            "data/models/yolo11s.pt" if payload.profile == "fast" and
            payload.tracker == "supervision-bytetrack" else "data/models/yolo11m.pt"))
        if payload.tracker != "supervision-bytetrack":
            model = primary
        elif payload.profile == "ensemble":
            secondary = model_path(payload.model_secondary or "data/models/yolov10m.pt")
            if secondary == primary:
                raise HTTPException(422, "Для ансамбля выберите две разные модели")
            model = json.dumps({"models": [primary, secondary], "fusion": "wbf"})
        else:
            model = json.dumps({"pipeline": "fast", "models": [primary],
                                "sample_fps": payload.sample_fps, "imgsz": 640})
        stored_tracker = payload.tracker
        if stored_tracker == "supervision-bytetrack":
            configuration = json.loads(model)
            configuration["lighting"] = payload.lighting
            configuration["night_model"] = model_path(payload.night_model) if payload.night_model else None
            model = json.dumps(configuration)
        run_geometry = json.loads(scene["geometry"])
        from ..cartogram import reference_topology

        example_layout = reference_topology(one(db, "videos", scene["video_id"])["name"])
        run_geometry["topology"] = example_layout if payload.topology == "auto" and example_layout else payload.topology
        run_geometry["topology_source"] = "reference" if payload.topology == "auto" and example_layout else "user"
        db.execute("""INSERT INTO runs(id,scene_id,video_id,geometry,status,model,tracker,created_at)
                      VALUES(?,?,?,?,?,?,?,?)""",
                   (identity, scene["id"], scene["video_id"], json.dumps(run_geometry),
                    "queued", model, stored_tracker, now()))
        return one(db, "runs", identity)

@app.get("/api/runs", tags=["Анализ"], summary="Получить список анализов")
def runs(video_id: str | None = None):
    with connection() as db:
        result = rows(db, "SELECT * FROM runs WHERE video_id=? ORDER BY created_at DESC", (video_id,)) if video_id else rows(db, "SELECT * FROM runs ORDER BY created_at DESC")
    return [run_state(item) for item in result]

def run_state(item):
    """Report a dead worker without rewriting the saved run or its results."""
    if item["status"] == "running" and item["heartbeat"]:
        heartbeat = datetime.fromisoformat(item["heartbeat"])
        if heartbeat < datetime.now(timezone.utc) - timedelta(seconds=295):
            return {**item, "status": "stalled",
                    "message": "Worker не отвечает более пяти минут. Перезапустите Docker и запустите анализ снова."}
        if item["started_at"] and item["progress"] and item["progress"] >= 0.05:
            elapsed = max(0, (datetime.now(timezone.utc) -
                              datetime.fromisoformat(item["started_at"])).total_seconds())
            item["eta_s"] = round(elapsed * (1 - item["progress"]) / item["progress"])
    return item

@app.get("/api/runs/{run_id}", tags=["Анализ"], summary="Получить статус анализа")
def run_detail(run_id: str):
    with connection() as db:
        item = run_state(one(db, "runs", run_id))
        item["geometry"] = json.loads(item["geometry"])
        return item

def change_topology(run_id: str, payload: TopologyIn):
    with connection() as db:
        run = one(db, "runs", run_id)
        geometry = json.loads(run["geometry"])
        geometry["topology"] = payload.topology
        geometry["topology_source"] = "user"
        db.execute("UPDATE runs SET geometry=? WHERE id=?", (json.dumps(geometry), run_id))
        return {"run_id": run_id, "topology": payload.topology}

def cancel(run_id: str):
    with connection() as db:
        one(db, "runs", run_id)
        db.execute("UPDATE runs SET cancelled=1,status=CASE WHEN status IN ('queued','running') "
                   "THEN 'cancelled' ELSE status END WHERE id=?", (run_id,))
        return one(db, "runs", run_id)

@app.patch(
    "/api/runs/{run_id}",
    tags=["Анализ"],
    summary="Изменить анализ",
    description="Один endpoint для остановки анализа или смены вида перекрёстка.",
)
def update_run(run_id: str, payload: RunUpdate):
    if payload.action == "cancel":
        return cancel(run_id)
    return change_topology(run_id, TopologyIn(topology=payload.topology))

