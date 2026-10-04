from contextlib import asynccontextmanager
import io
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse, JSONResponse
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError
from sqlalchemy import select, update, delete
from backend.config import REDIS_URL, ACTIVE, MAX_UPLOAD_BYTES
from backend.db import Session, Project, init_db, serialize
from backend.schemas import ProjectCreate, AnalysisRequest, Calibration, Rename
from backend.storage import storage
from backend.locking import project_lock
from backend.video import inspect_video
from backend.model_status import model_status
from backend.exports import csv_export, xlsx_export, cartogram_svg
from backend.validation import parse_ground_truth, compare
from ml.artifacts import TrackStore
from ml.movements import aggregate

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mts", ".m2ts"}


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="InnovaTransport · Анализ транспортных потоков", version="1.0.0", root_path="/api", lifespan=lifespan)
connection = Redis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=5)
queue = Queue("analysis", connection=connection)


@app.exception_handler(OSError)
async def disk_error(request, exc):
    return JSONResponse(
        status_code=507 if exc.errno == 28 else 500,
        content={"detail": "Недостаточно места на диске" if exc.errno == 28 else "Ошибка хранилища. Проверьте журнал сервера."},
    )


@app.exception_handler(ValueError)
async def bad_value(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def get_project(project_id):
    with Session() as s:
        p = s.get(Project, project_id)
        if not p:
            raise HTTPException(404, "Проект не найден")
        return p


def ready(project_id):
    p = get_project(project_id)
    if not p.result_run or not p.result:
        raise HTTPException(409, "Результаты ещё не готовы")
    return p


def artifact_db(p):
    return storage.path(p.id, f"runs/{p.result_run}/tracks.sqlite")


def reconcile(p):
    if p.status not in ACTIVE:
        return p
    reason = None
    if p.status == "processing" and time.time() - p.heartbeat > 180:
        reason = "Worker перестал отвечать. Перезапустите обработчик и анализ."
    if p.status == "queued" and p.job_id and time.time() - p.heartbeat > 30:
        try:
            job = Job.fetch(p.job_id, connection=connection)
            status = job.get_status(refresh=True)
            if status in ("failed", "stopped", "canceled", "finished"):
                reason = "Задание очереди завершилось без результата. Повторите анализ."
        except NoSuchJobError:
            reason = "Задание потеряно в очереди. Повторите анализ."
        except RedisError:
            pass
    if reason:
        with Session() as s:
            s.execute(
                update(Project)
                .where(Project.id == p.id, Project.run_id == p.run_id, Project.status == p.status, Project.heartbeat == p.heartbeat)
                .values(status="failed", error=reason)
            )
            s.commit()
        return get_project(p.id)
    return p


@app.get("/health")
def health():
    try:
        connection.ping()
        from rq import Worker

        workers = len(Worker.all(connection=connection))
        redis_ok = True
    except RedisError:
        workers, redis_ok = 0, False
    return {
        "api": True,
        "redis": redis_ok,
        "workers": workers,
        "detector": os.getenv("DETECTOR", "yolo"),
        "model": os.getenv("MODEL_PATH", "yolo11n.pt"),
        "local_ai": model_status(),
    }


@app.post("/projects", status_code=201)
def create_project(body: ProjectCreate):
    with Session() as s:
        p = Project(**body.model_dump())
        s.add(p)
        s.commit()
        return serialize(p)


@app.get("/projects")
def projects():
    with Session() as s:
        all_projects = s.scalars(select(Project).order_by(Project.created_at.desc())).all()
    # List stays small: detailed tracks and intervals are fetched on the project page.
    return [
        {k: v for k, v in serialize(reconcile(p)).items() if k not in ("ground_truth", "result")} | {"total_vehicles": p.result.get("total_vehicles")}
        for p in all_projects
    ]


@app.get("/projects/{project_id}")
def project(project_id: str):
    return serialize(reconcile(get_project(project_id)))


@app.post("/projects/{project_id}/video")
def upload_video(project_id: str, file: UploadFile = File(...)):
    p = get_project(project_id)
    extension = Path(file.filename or "").suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        raise HTTPException(415, "Поддерживаются MP4, MOV, M4V, MKV, AVI, WebM, MTS и M2TS")
    if p.status in ACTIVE:
        raise HTTPException(409, "Сначала остановите анализ")
    with project_lock(project_id):
        p = get_project(project_id)
        if p.status in ACTIVE:
            raise HTTPException(409, "Проект занят")
        temporary = storage.path(project_id, f"upload-{uuid4()}.mp4")
        preview = temporary.with_suffix(".jpg")
        try:
            size = 0
            with temporary.open("wb") as out:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, "Файл превышает лимит загрузки")
                    out.write(chunk)
            metadata = inspect_video(temporary, preview)
            metadata["filename"] = Path(file.filename).name
            temporary.replace(storage.path(project_id, "source.mp4"))
            preview.replace(storage.path(project_id, "preview.jpg"))
            storage.path(project_id, "playback.mp4").unlink(missing_ok=True)
            shutil.rmtree(storage.path(project_id, "runs"), ignore_errors=True)
            with Session() as s:
                s.execute(
                    update(Project)
                    .where(Project.id == project_id)
                    .values(
                        video=metadata,
                        status="uploaded",
                        result={},
                        result_run=None,
                        run_id=None,
                        progress={},
                        error=None,
                        ground_truth=[],
                        config={"zones": [], "lines": []},
                    )
                )
                s.commit()
        finally:
            temporary.unlink(missing_ok=True)
            preview.unlink(missing_ok=True)
            file.file.close()
    return project(project_id)


@app.post("/projects/{project_id}/analysis", status_code=202)
def start_analysis(project_id: str, body: AnalysisRequest):
    p = reconcile(get_project(project_id))
    if not p.video:
        raise HTTPException(409, "Сначала загрузите видео")
    if p.status in ACTIVE:
        raise HTTPException(409, "Анализ уже запущен")
    if body.recalculate and not p.result_run:
        raise HTTPException(409, "Нет траекторий для пересчёта")
    try:
        connection.ping()
    except RedisError as e:
        raise HTTPException(503, "Очередь недоступна. Запустите Redis.") from e
    run_id, job_id = str(uuid4()), str(uuid4())
    with project_lock(project_id):
        p = reconcile(get_project(project_id))
        if not p.video:
            raise HTTPException(409, "Сначала загрузите видео")
        if body.recalculate and not p.result_run:
            raise HTTPException(409, "Нет траекторий для пересчёта")
        with Session() as s:
            changed = s.execute(
                update(Project)
                .where(Project.id == project_id, Project.status.not_in(ACTIVE))
                .values(
                    status="queued",
                    run_id=run_id,
                    job_id=job_id,
                    heartbeat=time.time(),
                    error=None,
                    progress={"percent": 0, "stage": "queued", "processed_frames": 0, "total_frames": p.video["frame_count"], "elapsed": 0},
                )
            ).rowcount
            s.commit()
            if not changed:
                raise HTTPException(409, "Анализ уже запущен")
        try:
            queue.enqueue(
                "worker.tasks.analyze",
                project_id,
                run_id,
                body.profile,
                body.recalculate,
                job_id=job_id,
                job_timeout=7 * 24 * 3600,
                result_ttl=86400,
                failure_ttl=7 * 86400,
            )
        except RedisError as e:
            with Session() as s:
                s.execute(
                    update(Project)
                    .where(Project.id == project_id, Project.run_id == run_id, Project.status == "queued")
                    .values(status="failed", error="Не удалось поставить видео в очередь. Повторите запуск.")
                )
                s.commit()
            raise HTTPException(503, "Не удалось поставить видео в очередь") from e
    return project(project_id)


@app.get("/projects/{project_id}/analysis")
def analysis(project_id: str):
    p = reconcile(get_project(project_id))
    return {"status": p.status, "error": p.error, **p.progress}


@app.post("/projects/{project_id}/analysis/cancel")
def cancel_analysis(project_id: str):
    p = get_project(project_id)
    with Session() as s:
        s.execute(update(Project).where(Project.id == project_id, Project.status.in_(ACTIVE)).values(status="cancelled"))
        s.commit()
    if p.status == "queued" and p.job_id:
        try:
            Job.fetch(p.job_id, connection=connection).cancel()
        except (RedisError, NoSuchJobError):
            pass
    return project(project_id)


@app.get("/projects/{project_id}/calibration")
def calibration(project_id: str):
    return get_project(project_id).config


@app.put("/projects/{project_id}/calibration")
def save_calibration(project_id: str, body: Calibration):
    with project_lock(project_id):
        p = get_project(project_id)
        if p.status in ACTIVE:
            raise HTTPException(409, "Дождитесь завершения анализа")
        with Session() as s:
            s.execute(update(Project).where(Project.id == project_id).values(config=body.model_dump()))
            s.commit()
    return body


@app.get("/projects/{project_id}/results")
def results(project_id: str):
    return ready(project_id).result


@app.get("/projects/{project_id}/movements")
def movements(project_id: str):
    return ready(project_id).result["movements"]


@app.patch("/projects/{project_id}/movements/{movement_id}")
def rename_movement(project_id: str, movement_id: str, body: Rename):
    with project_lock(project_id):
        p = ready(project_id)
        if p.status in ACTIVE:
            raise HTTPException(409, "Дождитесь завершения анализа")
        result = p.result
        found = False
        for m in result["movements"]:
            if m["id"] == movement_id:
                m["name"] = body.name
                found = True
        if not found:
            raise HTTPException(404, "Направление не найдено")
        with Session() as s:
            s.execute(update(Project).where(Project.id == project_id).values(result=result))
            s.commit()
    return result["movements"]


@app.get("/projects/{project_id}/intervals")
def intervals(project_id: str, minutes: int = Query(15, ge=1, le=1440)):
    p = ready(project_id)
    if minutes == 15:
        return p.result["intervals"]
    store = TrackStore(artifact_db(p))
    try:
        return aggregate(store, {}, p.video["duration"], minutes * 60)["intervals"]
    finally:
        store.close()


@app.get("/projects/{project_id}/tracks")
def tracks(project_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)):
    p = ready(project_id)
    with sqlite3.connect(artifact_db(p)) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute("SELECT * FROM tracks ORDER BY id LIMIT ? OFFSET ?", (limit, offset))]
        for row in rows:
            row["trajectory"] = json.loads(row["trajectory"])
        return {"items": rows, "total": db.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]}


@app.get("/projects/{project_id}/overlay")
def overlay(project_id: str, start: float = Query(0, ge=0), seconds: float = Query(5, gt=0, le=10)):
    p = ready(project_id)
    with sqlite3.connect(artifact_db(p)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT o.*,t.class_name,t.movement_id,t.entry_zone,t.exit_zone FROM observations o JOIN tracks t ON t.id=o.track_id WHERE o.t>=? AND o.t<? ORDER BY o.t LIMIT 50000",
            (max(0, start - 2), start + seconds),
        ).fetchall()
        return [dict(r) | {"bbox": json.loads(r["bbox"]), "point": json.loads(r["point"])} for r in rows]


@app.get("/projects/{project_id}/media/{kind}")
def media(project_id: str, kind: str):
    p = get_project(project_id)
    if kind not in ("source", "preview", "playback"):
        raise HTTPException(404)
    path = storage.path(p.id, f"{kind}.jpg" if kind == "preview" else f"{kind}.mp4")
    if not path.exists():
        raise HTTPException(404, "Файл ещё не готов")
    return FileResponse(path, media_type="image/jpeg" if kind == "preview" else "video/mp4")


@app.post("/projects/{project_id}/ground-truth")
def ground_truth(project_id: str, file: UploadFile = File(...)):
    p = ready(project_id)
    content = file.file.read(10 * 1024 * 1024 + 1)
    file.file.close()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Эталон не должен превышать 10 МБ")
    try:
        data = parse_ground_truth(content, file.filename or "")
        compare(p.result, data, 10)
    except (ValueError, UnicodeError) as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:
        raise HTTPException(422, "Не удалось прочитать таблицу. Проверьте формат файла.") from e
    with Session() as s:
        s.execute(update(Project).where(Project.id == project_id).values(ground_truth=data))
        s.commit()
    return {"rows": len(data)}


@app.get("/projects/{project_id}/validation")
def validation(project_id: str, threshold: float = Query(10, ge=0, le=1000, allow_inf_nan=False)):
    p = ready(project_id)
    if not p.ground_truth:
        raise HTTPException(404, "Загрузите ручной эталон")
    return compare(p.result, p.ground_truth, threshold)


@app.get("/projects/{project_id}/ground-truth/template")
def truth_template(project_id: str):
    p = ready(project_id)
    import csv

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["movement_id", "class", "count"])
    for m in p.result["movements"]:
        for c in m["counts"]:
            writer.writerow([m["id"], c, ""])
    return Response(
        "\ufeff" + out.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=ground_truth_template.csv"}
    )


@app.get("/projects/{project_id}/export/{format}")
def export(project_id: str, format: str):
    p = ready(project_id)
    headers = {"Content-Disposition": f"attachment; filename=result.{format}"}
    if format == "csv":
        return Response(csv_export(p.result), media_type="text/csv", headers=headers)
    if format == "svg":
        return Response(cartogram_svg(p.result), media_type="image/svg+xml", headers=headers)
    if format == "json":

        def stream():
            yield (
                '{"project":'
                + json.dumps({"id": p.id, "name": p.name, "metadata": p.video}, ensure_ascii=False)
                + ',"result":'
                + json.dumps(p.result, ensure_ascii=False)
                + ',"tracks":['
            )
            store = TrackStore(artifact_db(p))
            try:
                first = True
                for t in store.tracks():
                    yield ("" if first else ",") + json.dumps(t, ensure_ascii=False)
                    first = False
            finally:
                store.close()
            yield "]}"

        return StreamingResponse(stream(), media_type="application/json", headers=headers)
    if format == "xlsx":
        path = storage.path(project_id, f"runs/{p.result_run}/export-{uuid4()}.xlsx")
        xlsx_export(p, artifact_db(p), path)
        from starlette.background import BackgroundTask

        return FileResponse(path, filename="result.xlsx", background=BackgroundTask(path.unlink, missing_ok=True))
    raise HTTPException(404, "Поддерживаются XLSX, CSV, JSON и SVG")


@app.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str):
    p = get_project(project_id)
    if p.status in ACTIVE:
        raise HTTPException(409, "Сначала отмените анализ и дождитесь остановки worker")
    with project_lock(project_id):
        if get_project(project_id).status in ACTIVE:
            raise HTTPException(409, "Сначала отмените анализ и дождитесь остановки worker")
        storage.delete_project(project_id)
        with Session() as s:
            s.execute(delete(Project).where(Project.id == project_id))
            s.commit()
