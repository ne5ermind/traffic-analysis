"""COCO YOLO detections -> optional WBF -> one persistent ByteTrack."""
from math import ceil, isfinite
from pathlib import Path

import numpy as np
import supervision as sv
from ensemble_boxes import weighted_boxes_fusion

from .model import load_yolo

TARGET_CLASSES = (0, 1, 2, 3, 5, 7)  # person, bicycle, car, motorcycle, bus, truck

# ByteTrack deliberately uses low-confidence detections to keep an existing
# identity through blur and short occlusions.  New tracks still need to clear
# its activation threshold (and its internal +0.1 threshold), so forwarding
# 0.10..0.25 detections improves continuity without creating weak tracks.
DETECTION_CONFIDENCE = 0.10
TRACK_ACTIVATION_THRESHOLD = 0.25
NMS_IOU_THRESHOLD = 0.70
TRACK_MEMORY_SECONDS = 1.0


def _frame_size(frame: np.ndarray) -> tuple[int, int]:
    if not isinstance(frame, np.ndarray) or frame.ndim < 2:
        raise ValueError("Некорректный кадр")
    height, width = frame.shape[:2]
    if width <= 0 or height <= 0:
        raise ValueError("Пустой кадр")
    return width, height


def _validated_detections(result, width: int, height: int) -> sv.Detections:
    """Convert an Ultralytics result and discard unsafe/degenerate boxes."""
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return sv.Detections.empty()

    xyxy = np.asarray(boxes.xyxy.cpu().numpy(), dtype=np.float32)
    scores = np.asarray(boxes.conf.cpu().numpy(), dtype=np.float32).reshape(-1)
    raw_classes = np.asarray(boxes.cls.cpu().numpy(), dtype=np.float32).reshape(-1)
    if xyxy.ndim != 2 or xyxy.shape[1] != 4:
        return sv.Detections.empty()
    count = min(len(xyxy), len(scores), len(raw_classes))
    xyxy, scores, raw_classes = xyxy[:count], scores[:count], raw_classes[:count]
    finite_classes = np.isfinite(raw_classes)
    safe_classes = finite_classes & (raw_classes >= 0) & (raw_classes <= max(TARGET_CLASSES))
    class_ids = np.full(len(raw_classes), -1, dtype=np.int64)
    class_ids[safe_classes] = raw_classes[safe_classes].astype(np.int64)
    valid = (
        np.isfinite(xyxy).all(axis=1)
        & np.isfinite(scores)
        & safe_classes
        & (raw_classes == class_ids)
        & np.isin(class_ids, TARGET_CLASSES)
        & (scores >= DETECTION_CONFIDENCE)
    )
    if not valid.any():
        return sv.Detections.empty()

    xyxy, scores, class_ids = xyxy[valid], scores[valid], class_ids[valid]
    xyxy[:, [0, 2]] = np.clip(xyxy[:, [0, 2]], 0, width)
    xyxy[:, [1, 3]] = np.clip(xyxy[:, [1, 3]], 0, height)
    positive_area = (xyxy[:, 2] > xyxy[:, 0]) & (xyxy[:, 3] > xyxy[:, 1])
    return sv.Detections(
        xyxy=xyxy[positive_area],
        confidence=scores[positive_area],
        class_id=class_ids[positive_area],
    )


def _new_tracker(fps: float) -> sv.ByteTrack:
    if not isfinite(fps) or fps <= 0:
        raise ValueError("Частота кадров должна быть положительной")
    tracker = sv.ByteTrack(
        track_activation_threshold=TRACK_ACTIVATION_THRESHOLD,
        lost_track_buffer=30,
        frame_rate=max(1, round(fps)),
    )
    _set_tracker_rate(tracker, fps)
    return tracker


def _set_tracker_rate(tracker, fps: float) -> None:
    """Keep ByteTrack's frame-count buffer equal to a stable wall-clock time."""
    if not isfinite(fps) or fps <= 0:
        raise ValueError("Частота кадров должна быть положительной")
    if hasattr(tracker, "max_time_lost"):
        tracker.max_time_lost = max(1, ceil(fps * TRACK_MEMORY_SECONDS))


class FastFrameProcessor:
    """One lightweight YOLO and persistent ByteTrack for sampled video frames."""

    def __init__(self, weights: str | Path, fps: float, image_size: int = 640,
                 model=None, tracker: sv.ByteTrack | None = None):
        if model is None:
            if not Path(weights).is_file():
                raise FileNotFoundError(
                    f"Нет весов модели: {weights}. Загрузите их командой "
                    f"python3 scripts/fetch_weights.py --model {Path(weights).name}")
            model = load_yolo(weights)
        self.model = model
        self.image_size = image_size
        self.tracker = tracker if tracker is not None else _new_tracker(fps)

    def set_frame_rate(self, fps: float) -> None:
        """Update time-based tracker settings when adaptive sampling changes."""
        _set_tracker_rate(self.tracker, fps)

    def process_frame(self, frame: np.ndarray) -> sv.Detections:
        width, height = _frame_size(frame)
        result = self.model.predict(
            frame, imgsz=self.image_size, conf=DETECTION_CONFIDENCE,
            iou=NMS_IOU_THRESHOLD, classes=list(TARGET_CLASSES), verbose=False,
        )[0]
        detections = _validated_detections(result, width, height)
        return self.tracker.update_with_detections(detections)


class EnsembleFrameProcessor:
    """Process BGR frames; return sv.Detections with xyxy, class_id and tracker_id.

    Instantiate once per video. The same ByteTrack instance must see every frame,
    including frames without detections, so tracks age consistently.
    """

    def __init__(self, primary: str | Path, secondary: str | Path, fps: float,
                 models: tuple | None = None, tracker: sv.ByteTrack | None = None):
        paths = (Path(primary), Path(secondary))
        if paths[0].resolve() == paths[1].resolve():
            raise ValueError("Для ансамбля нужны две разные модели YOLO")
        if models is None:
            for path in paths:
                if not path.is_file():
                    raise FileNotFoundError(
                        f"Нет весов модели: {path}. Загрузите веса командой "
                        "python3 scripts/fetch_weights.py --ensemble")
            models = tuple(load_yolo(path) for path in paths)
        if len(models) != 2:
            raise ValueError("Ансамблю нужны ровно две модели")
        self.models = models
        self.tracker = tracker if tracker is not None else _new_tracker(fps)

    def process_frame(self, frame: np.ndarray) -> sv.Detections:
        width, height = _frame_size(frame)
        boxes_list, scores_list, labels_list = [], [], []
        for model in self.models:
            result = model.predict(
                frame, conf=DETECTION_CONFIDENCE, iou=NMS_IOU_THRESHOLD,
                classes=list(TARGET_CLASSES), verbose=False,
            )[0]
            detections = _validated_detections(result, width, height)
            scale = np.asarray([width, height, width, height], dtype=np.float32)
            boxes_list.append((detections.xyxy / scale).tolist())
            scores_list.append(detections.confidence.tolist())
            labels_list.append(detections.class_id.tolist())

        if any(boxes_list):
            # WBF expects 0..1 coords; it fuses only boxes of the same COCO class.
            fused_boxes, fused_scores, fused_labels = weighted_boxes_fusion(
                boxes_list, scores_list, labels_list, iou_thr=0.55,
                skip_box_thr=DETECTION_CONFIDENCE, conf_type="max",
            )
            detections = sv.Detections(
                xyxy=(np.asarray(fused_boxes) * [width, height, width, height]).astype(np.float32),
                confidence=np.asarray(fused_scores, dtype=np.float32),
                class_id=np.asarray(fused_labels, dtype=np.int64))
        else:
            detections = sv.Detections.empty()
        return self.tracker.update_with_detections(detections)
