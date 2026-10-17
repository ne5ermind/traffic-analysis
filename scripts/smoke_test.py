"""Small real-model upload → queue → independent worker → export check."""
import io
import os
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
DATA = PROJECT / "data" / "smoke"
DATA.mkdir(parents=True, exist_ok=True)
os.environ["INNOVA_DATA"] = str(DATA)
os.environ["YOLO_CONFIG_DIR"] = str(DATA)

import av  # noqa: E402
from PIL import Image  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

memory = io.BytesIO()
with av.open(memory, mode="w", format="mp4") as output:
    stream = output.add_stream("mpeg4", rate=2)
    stream.width = 64
    stream.height = 64
    for i in range(4):
        frame = av.VideoFrame.from_image(Image.new("RGB", (64, 64), (i * 25, 15, 20)))
        for packet in stream.encode(frame):
            output.mux(packet)
    for packet in stream.encode():
        output.mux(packet)

with TestClient(app) as client:
    video = client.post("/api/videos", files={"file": ("synthetic.mp4", memory.getvalue(), "video/mp4")})
    assert video.status_code == 200, video.text
    scene = client.post("/api/scenes", json={"video_id": video.json()["id"], "name": "Smoke",
        "geometry": {"entries": [{"name": "N", "points": [[0.2, 0], [0.2, 1]]}],
                     "exits": [{"name": "S", "points": [[0.8, 0], [0.8, 1]]}], "roi": []}})
    assert scene.status_code == 200, scene.text
    task = client.post("/api/runs", json={"scene_id": scene.json()["id"]})
    assert task.status_code == 200, task.text
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "1"
    env["ATEN_CPU_CAPABILITY"] = "default"
    subprocess.run([sys.executable, "-m", "app.worker", "--once"], cwd=PROJECT,
                   env=env, check=True, timeout=180)
    result = client.get(f"/api/runs/{task.json()['id']}").json()
    assert result["status"] == "completed", result["message"]
    event = client.post(f"/api/runs/{result['id']}/events", json={"category": "bus",
        "from_direction": "N", "to_direction": "S", "time_s": 0.5})
    assert event.status_code == 200, event.text
    assert client.get(f"/api/runs/{result['id']}/results?view=summary").json()["total"] == 1
    assert client.get(f"/api/runs/{result['id']}/export/xlsx").status_code == 200
    print("PASS: real YOLO ensemble worker, API, manual event, Excel export")
