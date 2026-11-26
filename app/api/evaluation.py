import csv
import io
import json
from collections import Counter
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, File, HTTPException, UploadFile
from openpyxl import load_workbook
from ..storage import ROOT, connection
from .common import now, one
from .results import aggregate_data

app = APIRouter()

@app.post("/api/videos/{video_id}/ground-truth", include_in_schema=False)
async def ground_truth(video_id: str, file: UploadFile = File(...)):
    raw = await file.read(10_000_001)
    if len(raw) > 10_000_000:
        raise HTTPException(413, "Эталон больше 10 МБ")
    try:
        extension = Path(file.filename or "").suffix.lower()
        if extension == ".json":
            payload, format_ = json.loads(raw), "json"
        elif extension == ".csv":
            payload, format_ = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))), "csv"
        elif extension == ".xlsx":
            book = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            values = book.active.values
            header = [str(value) if value is not None else "" for value in next(values)]
            payload = [dict(zip(header, row)) for row in values]
            format_ = "xlsx"
        else:
            raise ValueError("Поддерживаются JSON, CSV, XLSX")
        if not isinstance(payload, (list, dict)):
            raise ValueError("Нужен массив событий или таблица")
    except (UnicodeError, ValueError) as exc:
        raise HTTPException(422, f"Некорректный эталон: {exc}") from exc
    identity = str(uuid4())
    with connection() as db:
        one(db, "videos", video_id)
        db.execute("INSERT INTO ground_truth VALUES(?,?,?,?,?,?)",
                   (identity, video_id, file.filename, format_, json.dumps(payload), now()))
    return {"id": identity, "format": format_}

@app.get("/api/runs/{run_id}/evaluate/{reference_id}", include_in_schema=False)
def evaluate(run_id: str, reference_id: str):
    with connection() as db:
        run = one(db, "runs", run_id)
        gt = one(db, "ground_truth", reference_id)
    if gt["video_id"] != run["video_id"]:
        raise HTTPException(422, "Эталон относится к другому видео")
    from ..evaluation import count_metrics, tracking_metrics
    reference = json.loads(gt["payload"])
    if isinstance(reference, dict) and "frames" in reference:
        path = ROOT / "runs" / run_id / "detections.jsonl"
        if run["status"] != "completed" or not path.is_file():
            raise HTTPException(409, "Сначала дождитесь завершения анализа")
        try:
            with path.open() as source:
                predicted = [json.loads(line) for line in source]
            metrics = tracking_metrics(reference["frames"], predicted)
            metrics["lighting"] = reference.get("lighting", "unspecified")
            return metrics
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(422, f"Некорректный эталон: {exc}") from exc
    if isinstance(reference, dict):
        reference = reference.get("events", reference.get("matrix", []))
    if not isinstance(reference, list):
        raise HTTPException(422, "Некорректный формат эталона")
    expected = Counter()
    try:
        for row in reference:
            src = row.get("from_direction", row.get("from"))
            dst = row.get("to_direction", row.get("to"))
            cat = row.get("category")
            count = float(row.get("count", 1))
            if (not all(isinstance(value, str) and value for value in (src, dst, cat))
                    or not count.is_integer() or count < 0):
                raise ValueError("Нужны from/to/category и целое неотрицательное count")
            expected[src, dst, cat] += int(count)
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise HTTPException(422, f"Некорректный эталон: {exc}") from exc
    actual = Counter({(row["from"], row["to"], row["category"]): row["count"]
                      for row in aggregate_data(run_id, "candidates")["matrix"]})
    return count_metrics(expected, actual)

