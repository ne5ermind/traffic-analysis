

import json
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from ..storage import connection, rows
from .common import geometry_check, now, one
from .schemas import SceneIn

app = APIRouter()

@app.post("/api/scenes", tags=["Зоны"], summary="Создать зону подсчёта")
def create_scene(payload: SceneIn):
    try:
        geometry_check(payload.geometry)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    identity = str(uuid4())
    with connection() as db:
        one(db, "videos", payload.video_id)
        db.execute("INSERT INTO scenes VALUES(?,?,?,?,?)",
                   (identity, payload.video_id, payload.name, json.dumps(payload.geometry), now()))
        return one(db, "scenes", identity)

@app.get("/api/scenes", tags=["Зоны"], summary="Получить зоны подсчёта")
def scenes(video_id: str | None = None):
    with connection() as db:
        output = rows(db, "SELECT * FROM scenes WHERE video_id=? ORDER BY created_at DESC", (video_id,)) if video_id else rows(db, "SELECT * FROM scenes ORDER BY created_at DESC")
    for scene in output:
        scene["geometry"] = json.loads(scene["geometry"])
    return output

@app.put("/api/scenes/{scene_id}", tags=["Зоны"], summary="Изменить зону подсчёта")
def update_scene(scene_id: str, payload: SceneIn):
    try:
        geometry_check(payload.geometry)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    with connection() as db:
        old = one(db, "scenes", scene_id)
        if old["video_id"] != payload.video_id:
            raise HTTPException(409, "Запись сцены нельзя привязать к другому видео")
        db.execute("UPDATE scenes SET name=?,geometry=? WHERE id=?",
                   (payload.name, json.dumps(payload.geometry), scene_id))
        return {**one(db, "scenes", scene_id), "geometry": payload.geometry}

