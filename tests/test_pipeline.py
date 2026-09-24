import pytest
from backend.video import inspect_video
from ml.pipeline import run_pipeline, Cancelled
from ml.artifacts import TrackStore
from ml.trackers.bytetrack import ByteTracker
from ml.detectors.base import Detection
from tests.mock_detector import MockDetector


def test_real_tracker_retains_id_through_short_occlusion():
    tracker = ByteTracker(10)
    ids = []
    for i in range(20):
        detections = [] if i in (8, 9, 10) else [Detection((20 + i, 30, 60 + i, 80), 0, "car", 0.9)]
        rows = tracker.update(detections, (240, 320))
        ids.extend(r["track_id"] for r in rows)
    assert len(set(ids)) == 1


def test_pipeline_smoke_with_actual_video_and_tracker(video, tmp_path):
    meta = inspect_video(video, tmp_path / "preview.jpg")
    progress = []
    result = run_pipeline(
        video,
        tmp_path / "tracks.db",
        meta,
        {"zones": [], "lines": []},
        profile="accurate",
        detector=MockDetector(),
        report=lambda **v: progress.append(v),
    )
    assert result["total_vehicles"] == 1
    assert result["counts"]["car"] == 1
    assert result["diagnostics"]["detections"] == 60
    assert result["diagnostics"]["unknown_tracks"] == 1
    assert result["model"] == "test-only"
    store = TrackStore(tmp_path / "tracks.db")
    t = list(store.tracks())[0]
    assert len(t["trajectory"]) > 40
    assert t["last_seen"] > 5
    assert store.db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] > 40
    store.close()


def test_pipeline_cancellation(video, tmp_path):
    meta = inspect_video(video, tmp_path / "preview.jpg")

    def cancel():
        raise Cancelled()

    with pytest.raises(Cancelled):
        run_pipeline(video, tmp_path / "tracks.db", meta, {}, detector=MockDetector(), check=cancel)


def test_low_fps_gap_preserves_full_track(tmp_path):
    import cv2
    import numpy as np

    video = tmp_path / "slow.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 1, (320, 240))
    for _ in range(11):
        writer.write(np.zeros((240, 320, 3), dtype=np.uint8))
    writer.release()

    class SparseDetector(MockDetector):
        def predict(self, frame):
            detections = super().predict(frame)
            return [] if self.frame in (3, 4) else detections

    metadata = inspect_video(video, tmp_path / "slow.jpg")
    result = run_pipeline(video, tmp_path / "slow.sqlite", metadata, {}, detector=SparseDetector())
    assert result["total_vehicles"] == 1
    store = TrackStore(tmp_path / "slow.sqlite")
    tracks = list(store.tracks())
    store.close()
    assert len(tracks) == 1
    assert tracks[0]["first_seen"] == 0
    assert tracks[0]["last_seen"] == 10


def test_corrupt_video_rejected(tmp_path):
    path = tmp_path / "broken.mp4"
    path.write_bytes(b"not a video")
    with pytest.raises(ValueError):
        inspect_video(path, tmp_path / "preview.jpg")
