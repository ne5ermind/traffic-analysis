
import io
from pathlib import Path
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from ..storage import ROOT, connection, portable_data_path, resolve_data_path, rows
from .common import ALLOWED_VIDEO, VIDEO_MEDIA_TYPES, now, one

app = APIRouter()

@app.post("/api/videos", tags=["Видео"], summary="Загрузить видео")
async def upload(file: UploadFile = File(...)):
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_VIDEO:
        raise HTTPException(422, "Поддерживаются MP4, MOV, MKV, AVI и WebM")
    identity = str(uuid4())
    folder = ROOT / "uploads"
    folder.mkdir(exist_ok=True)
    destination = folder / (identity + extension)
    with destination.open("wb") as target:
        while chunk := await file.read(1024 * 1024):
            target.write(chunk)
    if destination.stat().st_size == 0:
        destination.unlink()
        raise HTTPException(422, "Пустой файл")
    try:
        import av
        with av.open(str(destination)) as source:
            stream = source.streams.video[0]
            width, height = stream.width, stream.height
            duration = (float(stream.duration * stream.time_base) if stream.duration is not None
                        else float(source.duration or 0) / 1_000_000)
            fps = float(stream.average_rate or 25)
            if duration <= 0 and stream.frames:
                duration = stream.frames / fps
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(422, f"Невозможно прочесть видео: {exc}") from exc
    with connection() as db:
        db.execute("INSERT INTO videos VALUES(?,?,?,?,?,?,?,?)",
                   (identity, file.filename, portable_data_path(destination),
                    width, height, duration, fps, now()))
        return one(db, "videos", identity)

@app.get("/api/videos", tags=["Видео"], summary="Получить каталог видео")
def videos():
    with connection() as db:
        result = rows(db, "SELECT id,name,path,width,height,duration,fps,created_at FROM videos ORDER BY created_at DESC")
    for video in result:
        video["available"] = resolve_data_path(video.pop("path")).is_file()
    return result

def video_file(video_id: str):
    with connection() as db:
        video = one(db, "videos", video_id)
    path = resolve_data_path(video["path"])
    if not path.is_file():
        raise HTTPException(404, "Файл видеозаписи не найден в хранилище")
    return FileResponse(path, media_type=VIDEO_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream"))

def frame(video_id: str, time_s: float = Query(0, ge=0)):
    import av
    from PIL import Image
    with connection() as db:
        video = one(db, "videos", video_id)
    path = resolve_data_path(video["path"])
    if not path.is_file():
        raise HTTPException(404, "Файл видеозаписи не найден в хранилище")
    with av.open(str(path)) as source:
        stream = source.streams.video[0]
        try:
            source.seek(int(time_s / float(stream.time_base)), stream=stream, backward=True)
        except Exception:
            source.seek(0)
        found = None
        for item in source.decode(stream):
            found = item
            if item.pts is None or float(item.pts * item.time_base) >= time_s:
                break
        if found is None:
            raise HTTPException(422, "Нет кадров")
        result = io.BytesIO()
        Image.fromarray(found.to_ndarray(format="rgb24")).save(result, format="JPEG", quality=85)
        return Response(result.getvalue(), media_type="image/jpeg")

@app.get(
    "/api/videos/{video_id}/media",
    tags=["Видео"],
    summary="Получить видео или preview-кадр",
    description="`kind=file` возвращает исходное видео, `kind=frame` — JPEG-кадр на моменте `time_s`.",
)
def video_media(
    video_id: str,
    kind: Literal["file", "frame"] = "file",
    time_s: float = Query(0, ge=0),
):
    return frame(video_id, time_s) if kind == "frame" else video_file(video_id)

