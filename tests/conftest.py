import os
import tempfile
import pytest

_TEST_ROOT = tempfile.TemporaryDirectory(prefix="traffic-tests-")
os.environ["STORAGE_PATH"] = _TEST_ROOT.name
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_ROOT.name}/test.db"
os.environ["YOLO_CONFIG_DIR"] = f"{_TEST_ROOT.name}/yolo"
os.environ["MPLCONFIGDIR"] = f"{_TEST_ROOT.name}/matplotlib"


@pytest.fixture
def video(tmp_path):
    import cv2
    import numpy as np

    path = tmp_path / "intersection.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    for frame in range(60):
        image = np.full((240, 320, 3), 120, dtype=np.uint8)
        cv2.rectangle(image, (20 + frame * 3, 100), (60 + frame * 3, 140), (220, 220, 220), -1)
        writer.write(image)
    writer.release()
    return path


@pytest.fixture
def client():
    from backend.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client
