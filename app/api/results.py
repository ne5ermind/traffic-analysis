

import json
from bisect import bisect_right
from collections import Counter
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Query
from ..storage import ROOT, connection, parse_event, rows
from .common import now, one
from .schemas import EventEdit, EventIn

app = APIRouter()

def cartogram(run_id: str):
    return cartogram_data(aggregate_data(run_id))

def cartogram_data(result):
    from ..cartogram import build_cartogram

    track_file = ROOT / "runs" / result["run_id"] / "tracks.json"
    tracks = json.loads(track_file.read_text(encoding="utf-8")) if track_file.is_file() else {}
    return build_cartogram(result["events"], tracks, result["geometry"])

def detections(run_id: str, time_s: float = Query(0, ge=0)):
    """Return tracked boxes at playback time from the finished run, not a new inference."""
    with connection() as db:
        run = one(db, "runs", run_id)
        video = one(db, "videos", run["video_id"])
    folder = ROOT / "runs" / run_id
    index_path = folder / "detections-index.json"
    trace_path = folder / "detections.jsonl"
    if not index_path.is_file() or not trace_path.is_file():
        return {"time_s": time_s, "objects": []}
    index = json.loads(index_path.read_text(encoding="utf-8"))
    seconds = sorted(int(key) for key in index)
    position = bisect_right(seconds, int(time_s)) - 1
    if position < 0:
        return {"time_s": time_s, "objects": []}
    latest = None
    with trace_path.open("rb") as traces:
        traces.seek(index[str(seconds[position])])
        for line in traces:
            frame = json.loads(line)
            if frame["t"] > time_s:
                break
            latest = frame
    # Fast runs may automatically sample down to 2 fps, so retain the last box
    # briefly through the next sampled frame during playback.
    fast_run = run["model"].startswith("{") and json.loads(run["model"]).get("pipeline") == "fast"
    max_age = 0.75 if fast_run else max(0.5, 2 / (video["fps"] or 25))
    if latest is None or time_s - latest["t"] > max_age:
        return {"time_s": time_s, "objects": []}
    return latest

def events(run_id: str, status: str | None = None):
    with connection() as db:
        one(db, "runs", run_id)
        values = rows(db, "SELECT * FROM events WHERE run_id=? AND status=? ORDER BY time_s", (run_id, status)) if status else rows(db, "SELECT * FROM events WHERE run_id=? ORDER BY time_s", (run_id,))
        return [parse_event(item) for item in values]

def validate_route(run_id, item, db):
    run = one(db, "runs", run_id)
    geometry = json.loads(run["geometry"])
    if geometry.get("mode") == "automatic":
        if (item.from_direction, item.to_direction) != ("В кадре", "В кадре"):
            raise HTTPException(422, "В автоматическом режиме направление: В кадре")
    else:
        if item.from_direction not in {line["name"] for line in geometry["entries"]}:
            raise HTTPException(422, "Неизвестное направление въезда")
        if item.to_direction not in {line["name"] for line in geometry["exits"]}:
            raise HTTPException(422, "Неизвестное направление выезда")
    video = one(db, "videos", run["video_id"])
    if item.time_s > video["duration"] + 1:
        raise HTTPException(422, "Время вне видео")

@app.post("/api/runs/{run_id}/events", tags=["Результаты"], summary="Добавить событие")
def add_event(run_id: str, item: EventIn):
    identity = str(uuid4())
    with connection() as db:
        validate_route(run_id, item, db)
        db.execute("""INSERT INTO events(id,run_id,category,from_direction,to_direction,time_s,start_s,
                      status,origin,details,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (identity, run_id, item.category, item.from_direction, item.to_direction,
                    item.time_s, item.start_s, item.status, "manual", "{}", now(), now()))
        row = parse_event(one(db, "events", identity))
        db.execute("INSERT INTO revisions(event_id,new_value,reason,created_at) VALUES(?,?,?,?)",
                   (identity, json.dumps(row), item.reason, now()))
        return row

@app.patch("/api/runs/{run_id}/events", tags=["Результаты"], summary="Изменить событие")
def edit_event(run_id: str, item: EventEdit):
    with connection() as db:
        old = parse_event(one(db, "events", item.id))
        if old["run_id"] != run_id:
            raise HTTPException(404, "Событие не относится к указанному анализу")
        validate_route(run_id, item, db)
        updated = db.execute("""UPDATE events SET category=?,from_direction=?,to_direction=?,time_s=?,
                        start_s=?,status=?,version=version+1,updated_at=? WHERE id=? AND version=?""",
                     (item.category, item.from_direction, item.to_direction, item.time_s,
                      item.start_s, item.status, now(), item.id, item.version))
        if updated.rowcount != 1:
            raise HTTPException(409, "Запись изменена в другой вкладке. Обновите список.")
        new = parse_event(one(db, "events", item.id))
        db.execute("INSERT INTO revisions(event_id,old_value,new_value,reason,created_at) VALUES(?,?,?,?,?)",
                   (item.id, json.dumps(old), json.dumps(new), item.reason, now()))
        return new

def aggregate_data(run_id, mode="effective", interval=900):
    if interval <= 0 or interval > 86400:
        raise HTTPException(422, "Некорректный интервал")
    with connection() as db:
        run = one(db, "runs", run_id)
        video = one(db, "videos", run["video_id"])
        scene = one(db, "scenes", run["scene_id"])
        all_events = [parse_event(row) for row in rows(db, "SELECT * FROM events WHERE run_id=? ORDER BY time_s", (run_id,))]
    if mode == "effective":
        selected = [event for event in all_events if event["status"] in ("confirmed", "auto_accept")]
    elif mode == "confirmed":
        selected = [event for event in all_events if event["status"] == "confirmed"]
    elif mode == "candidates":
        selected = [event for event in all_events if event["status"] != "discarded"]
    else:
        raise HTTPException(422, "Неизвестный режим агрегирования")
    matrix = Counter((e["from_direction"], e["to_direction"], e["category"]) for e in selected)
    bins = Counter((int(e["time_s"] // interval), e["category"]) for e in selected)
    categories = Counter(event["category"] for event in selected)
    return {"run_id": run_id, "mode": mode, "interval_s": interval,
            "total": len(selected), "statuses": dict(Counter(e["status"] for e in all_events)),
            "category_totals": [{"category": category, "count": count}
                                for category, count in sorted(categories.items())],
            "transport_total": sum(count for category, count in categories.items()
                                   if category != "pedestrian"),
            "pedestrian_total": categories.get("pedestrian", 0),
            "matrix": [{"from": src, "to": dst, "category": cat, "count": n}
                       for (src, dst, cat), n in sorted(matrix.items())],
            "intervals": [{"start_s": idx * interval, "end_s": (idx + 1) * interval,
                          "category": cat, "count": n}
                          for (idx, cat), n in sorted(bins.items())], "events": selected,
            "geometry": json.loads(run["geometry"]),
            "video": {key: video[key] for key in
                      ("id", "name", "width", "height", "duration", "fps", "created_at")},
            "scene": {"id": scene["id"], "name": scene["name"]}}

def aggregate(run_id: str, mode: str = "effective", interval: int = 900):
    return aggregate_data(run_id, mode, interval)

@app.get(
    "/api/runs/{run_id}/results",
    tags=["Результаты"],
    summary="Получить результаты анализа",
    description=(
        "По умолчанию возвращает сводку, события и картограмму одним ответом. "
        "Параметр `view` позволяет запросить только один раздел или рамки объектов для кадра."
    ),
)
def results(
    run_id: str,
    view: Literal["all", "summary", "events", "cartogram", "detections", "clusters", "performance"] = "all",
    mode: Literal["effective", "confirmed", "candidates"] = "effective",
    interval: int = Query(900, gt=0, le=86400),
    time_s: float = Query(0, ge=0),
    status: str | None = None,
):
    if view == "detections":
        return detections(run_id, time_s)
    if view == "events":
        return events(run_id, status)
    summary = aggregate_data(run_id, mode, interval)
    if view == "summary":
        return summary
    clusters, performance = load_artifacts(summary)
    if view == "clusters":
        return clusters
    if view == "performance":
        return performance
    diagram = cartogram_data(summary)
    if view == "cartogram":
        return diagram
    return {"summary": summary, "events": events(run_id, status), "cartogram": diagram,
            "clusters": clusters, "performance": performance}



def load_artifacts(summary):
    from ..clustering import cluster_counts
    folder = ROOT / "runs" / summary["run_id"]
    def artifact(name, default):
        path = folder / name
        return json.loads(path.read_text()) if path.is_file() else default
    clusters = cluster_counts(artifact("clusters.json", {"clusters": [], "assignments": {}}), summary["events"])
    performance = artifact("performance.json", None)
    return clusters, performance
