import io
from unittest.mock import Mock
from openpyxl import load_workbook
from backend.storage import storage
from tests.mock_detector import MockDetector


def create_uploaded(client, video):
    p = client.post("/projects", json={"name": "Тестовый перекрёсток", "description": "Проверка"}).json()
    with video.open("rb") as f:
        response = client.post(f"/projects/{p['id']}/video", files={"file": ("intersection.mp4", f, "video/mp4")})
    assert response.status_code == 200, response.text
    return p["id"]


def test_create_upload_invalid_and_empty(client, video):
    assert client.post("/projects", json={"name": "   "}).status_code == 422
    pid = create_uploaded(client, video)
    p = client.get(f"/projects/{pid}").json()
    assert p["video"]["frame_count"] == 60
    assert p["video"]["width"] == 320
    assert client.get(f"/projects/{pid}/results").status_code == 409
    assert client.post(f"/projects/{pid}/video", files={"file": ("test.txt", b"bad")}).status_code == 415
    assert client.post(f"/projects/{pid}/video", files={"file": ("bad.mp4", b"bad")}).status_code == 422
    assert client.get(f"/projects/{pid}/media/preview").status_code == 200
    assert client.get("/projects/missing").status_code == 404
    mov = client.post("/projects", json={"name": "MOV-проверка"}).json()
    with video.open("rb") as f:
        response = client.post(
            f"/projects/{mov['id']}/video",
            files={"file": ("intersection.MOV", f, "video/quicktime")},
        )
    assert response.status_code == 200, response.text
    assert response.json()["video"]["filename"] == "intersection.MOV"


def test_full_api_worker_export_recalculate_and_delete(client, video, monkeypatch):
    import backend.main as api_module
    from worker.tasks import analyze

    monkeypatch.setattr(api_module.connection, "ping", lambda: True)
    enqueued = Mock()
    monkeypatch.setattr(api_module.queue, "enqueue", enqueued)
    monkeypatch.setattr("ml.pipeline.create_detector", lambda profile: MockDetector(step=6))
    pid = create_uploaded(client, video)
    response = client.post(f"/projects/{pid}/analysis", json={"profile": "balanced"})
    assert response.status_code == 202, response.text
    assert client.post(f"/projects/{pid}/analysis", json={}).status_code == 409
    assert client.delete(f"/projects/{pid}").status_code == 409
    p = response.json()
    analyze(pid, p["run_id"], "balanced")
    p = client.get(f"/projects/{pid}").json()
    assert p["status"] == "completed", p["error"]
    result = client.get(f"/projects/{pid}/results").json()
    assert result["total_vehicles"] == 1
    assert client.get(f"/projects/{pid}/tracks").json()["total"] == 1
    assert len(client.get(f"/projects/{pid}/overlay").json()) > 0
    assert client.get(f"/projects/{pid}/media/playback", headers={"Range": "bytes=0-99"}).status_code == 206
    for ext in ("csv", "json", "xlsx", "svg"):
        response = client.get(f"/projects/{pid}/export/{ext}")
        assert response.status_code == 200, response.text[:100]
        if ext == "xlsx":
            assert "Tracks" in load_workbook(io.BytesIO(response.content)).sheetnames
        if ext == "json":
            assert len(response.json()["tracks"]) == 1
    response = client.post(f"/projects/{pid}/ground-truth", files={"file": ("manual.csv", b"movement_id,class,count\nunknown,car,2\n")})
    assert response.status_code == 200, response.text
    assert client.get(f"/projects/{pid}/validation").json()["total"]["absolute_error"] == 1
    line = {"lines": [{"id": "L", "name": "Пересечение", "points": [{"x": 0.5, "y": 0}, {"x": 0.5, "y": 1}]}], "zones": []}
    assert client.put(f"/projects/{pid}/calibration", json=line).status_code == 200
    response = client.post(f"/projects/{pid}/analysis", json={"recalculate": True})
    assert response.status_code == 202
    analyze(pid, response.json()["run_id"], recalculate=True)
    p = client.get(f"/projects/{pid}").json()
    assert p["status"] == "completed", p["error"]
    assert p["result"]["movements"][0]["id"] == "line_L_-1"
    assert p["result"]["total_vehicles"] == 1
    assert client.get(f"/projects/{pid}/intervals?minutes=5").status_code == 200
    assert client.delete(f"/projects/{pid}").status_code == 204
    assert not storage.path(pid).exists()
    assert client.get(f"/projects/{pid}").status_code == 404


def test_redis_unavailable_and_cancel(client, video, monkeypatch):
    import backend.main as api_module
    from redis.exceptions import ConnectionError

    pid = create_uploaded(client, video)
    monkeypatch.setattr(api_module.connection, "ping", Mock(side_effect=ConnectionError()))
    assert client.post(f"/projects/{pid}/analysis", json={}).status_code == 503
    assert client.get(f"/projects/{pid}").json()["status"] == "uploaded"
    monkeypatch.setattr(api_module.connection, "ping", lambda: True)
    monkeypatch.setattr(api_module.queue, "enqueue", Mock())
    p = client.post(f"/projects/{pid}/analysis", json={}).json()
    response = client.post(f"/projects/{pid}/analysis/cancel")
    assert response.json()["status"] == "cancelled"
    from worker.tasks import analyze

    analyze(pid, p["run_id"])
    assert client.get(f"/projects/{pid}").json()["status"] == "cancelled"


def test_worker_error_is_visible(client, video, monkeypatch):
    import backend.main as api_module
    from worker.tasks import analyze

    monkeypatch.setattr(api_module.connection, "ping", lambda: True)
    monkeypatch.setattr(api_module.queue, "enqueue", Mock())

    def fail(profile):
        raise FileNotFoundError("weights missing")

    monkeypatch.setattr("ml.pipeline.create_detector", fail)
    pid = create_uploaded(client, video)
    p = client.post(f"/projects/{pid}/analysis", json={}).json()
    analyze(pid, p["run_id"])
    p = client.get(f"/projects/{pid}").json()
    assert p["status"] == "failed"
    assert "weights missing" in p["error"]
