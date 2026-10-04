import importlib
import os
from ml.detectors.base import Detector


def create_detector(profile="balanced") -> Detector:
    kind = os.getenv("DETECTOR", "yolo")
    if kind == "yolo":
        from ml.detectors.yolo_detector import YoloDetector

        return YoloDetector(profile)
    if kind in ("onnx", "torchscript"):
        from ml.detectors.tensor_detector import TensorDetector

        return TensorDetector(profile, backend=kind)
    if kind == "custom":
        module, name = os.environ["CUSTOM_DETECTOR"].split(":")
        detector = getattr(importlib.import_module(module), name)(profile=profile)
        if not isinstance(detector, Detector):
            raise TypeError("Custom detector должен наследовать Detector")
        return detector
    raise ValueError(f"Неизвестный DETECTOR: {kind}")
