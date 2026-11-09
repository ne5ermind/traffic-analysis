from types import SimpleNamespace

import numpy as np
import pytest
import supervision as sv

from app.ensemble import EnsembleFrameProcessor, TARGET_CLASSES


class Tensor:
    def __init__(self, values):
        self.values = np.asarray(values)

    def cpu(self):
        return self

    def numpy(self):
        return self.values


class Model:
    def __init__(self, frames):
        self.frames = iter(frames)

    def predict(self, image, **kwargs):
        assert kwargs["classes"] == list(TARGET_CLASSES)
        assert kwargs["conf"] == 0.10
        assert kwargs["iou"] == 0.70
        boxes = next(self.frames)
        class Boxes(SimpleNamespace):
            def __len__(self):
                return len(self.cls.values)

        return [SimpleNamespace(boxes=Boxes(
            xyxy=Tensor([box[0] for box in boxes] if boxes else np.empty((0, 4))),
            conf=Tensor([box[1] for box in boxes]),
            cls=Tensor([box[2] for box in boxes])))]


class CapturingTracker:
    def __init__(self):
        self.received = []

    def update_with_detections(self, detections):
        self.received.append(detections)
        detections.tracker_id = np.arange(len(detections), dtype=np.int64)
        return detections


def test_wbf_fuses_only_matching_coco_classes_before_tracking():
    tracker = CapturingTracker()
    models = (
        Model([[([10, 10, 40, 40], 0.9, 2), ([20, 20, 50, 50], 0.9, 1),
                ([60, 10, 80, 30], 0.99, 4)], []]),
        Model([[([12, 12, 42, 42], 0.8, 2), ([10, 10, 40, 40], 0.9, 0)], []]),
    )
    processor = EnsembleFrameProcessor("first.pt", "second.pt", fps=25, models=models, tracker=tracker)
    detections = processor.process_frame(np.zeros((100, 100, 3), dtype=np.uint8))
    assert isinstance(detections, sv.Detections)
    assert set(detections.class_id) == {0, 1, 2}  # Bicycle is required by reference reports.
    assert len(detections) == 3  # Same position, different class: not fused.
    car = detections.xyxy[detections.class_id == 2][0]
    assert 10 < car[0] < 12 and 40 < car[2] < 42
    # A confident detection unique to one model is not artificially halved.
    assert detections.confidence[detections.class_id == 1][0] == pytest.approx(0.9)
    assert len(tracker.received) == 1
    assert detections.tracker_id.tolist() == [0, 1, 2]
    empty = processor.process_frame(np.zeros((100, 100, 3), dtype=np.uint8))
    assert len(empty) == 0
    assert len(tracker.received) == 2  # Empty frames still reach ByteTrack.


def test_real_bytetrack_keeps_identity_across_frames():
    frames = [[([10 + offset, 10, 40 + offset, 40], 0.9, 2)] for offset in (0, 1, 2)]
    models = (Model(frames), Model(frames))
    processor = EnsembleFrameProcessor("first.pt", "second.pt", fps=5, models=models)
    ids = []
    for _ in range(3):
        tracked = processor.process_frame(np.zeros((100, 100, 3), dtype=np.uint8))
        assert tracked.xyxy.shape == (1, 4)
        assert tracked.class_id.tolist() == [2]
        assert tracked.tracker_id is not None
        ids.append(int(tracked.tracker_id[0]))
    assert len(set(ids)) == 1


def test_missing_and_duplicate_models_fail_explicitly(tmp_path):
    with pytest.raises(ValueError, match="две разные"):
        EnsembleFrameProcessor(tmp_path / "one.pt", tmp_path / "one.pt", fps=25)
    with pytest.raises(FileNotFoundError, match="fetch_weights.py --ensemble"):
        EnsembleFrameProcessor(tmp_path / "one.pt", tmp_path / "two.pt", fps=25)


def test_fast_processor_filters_coco_and_updates_tracker_on_empty_frame():
    from app.ensemble import FastFrameProcessor

    tracker = CapturingTracker()
    model = Model([[([10, 5, 30, 30], 0.9, 2), ([40, 5, 60, 30], 0.8, 1)], []])
    processor = FastFrameProcessor("test.pt", fps=6, image_size=640, model=model, tracker=tracker)
    first = processor.process_frame(np.zeros((80, 100, 3), dtype=np.uint8))
    assert len(first) == 2 and set(first.class_id) == {1, 2}
    assert first.tracker_id.tolist() == [0, 1]
    assert len(processor.process_frame(np.zeros((80, 100, 3), dtype=np.uint8))) == 0
    assert len(tracker.received) == 2


def test_fast_processor_reports_missing_weights(tmp_path):
    from app.ensemble import FastFrameProcessor

    with pytest.raises(FileNotFoundError, match="fetch_weights.py --model yolo11s.pt"):
        FastFrameProcessor(tmp_path / "yolo11s.pt", fps=6)


def test_fast_processor_forwards_low_scores_but_drops_invalid_boxes():
    from app.ensemble import FastFrameProcessor

    tracker = CapturingTracker()
    model = Model([[
        ([-5, 4, 15, 30], 0.12, 2),       # useful to ByteTrack for association
        ([20, 4, 20, 30], 0.9, 2),        # zero width after validation
        ([30, 4, float("nan"), 30], 0.9, 2),
        ([40, 4, 60, 30], 0.09, 2),       # below detector/tracker floor
    ]])
    processor = FastFrameProcessor("test.pt", fps=6, model=model, tracker=tracker)
    found = processor.process_frame(np.zeros((40, 80, 3), dtype=np.uint8))
    assert len(found) == 1
    assert found.xyxy.tolist() == [[0.0, 4.0, 15.0, 30.0]]
    assert found.confidence[0] == pytest.approx(0.12)


def test_adaptive_sampling_updates_bytetrack_memory_in_video_seconds():
    from app.ensemble import FastFrameProcessor

    tracker = CapturingTracker()
    tracker.max_time_lost = 99
    processor = FastFrameProcessor("test.pt", fps=6, model=Model([[]]), tracker=tracker)
    processor.set_frame_rate(2.5)
    assert tracker.max_time_lost == 3
    with pytest.raises(ValueError, match="положительной"):
        processor.set_frame_rate(0)


def test_processors_reject_empty_or_malformed_frames():
    tracker = CapturingTracker()
    processor = EnsembleFrameProcessor(
        "first.pt", "second.pt", fps=5,
        models=(Model([[]]), Model([[]])), tracker=tracker,
    )
    with pytest.raises(ValueError, match="Пустой"):
        processor.process_frame(np.zeros((0, 10, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match="Некорректный"):
        processor.process_frame(None)
