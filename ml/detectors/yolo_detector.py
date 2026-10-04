import json
import os
from pathlib import Path
from ml.detectors.base import Detector, Detection, NORMALIZE, CLASSES

PROFILES = {
    "fast": {"imgsz": 480, "stride": 3, "confidence": 0.15},
    "balanced": {"imgsz": 640, "stride": 2, "confidence": 0.10},
    "accurate": {"imgsz": 960, "stride": 1, "confidence": 0.08},
}


class YoloDetector(Detector):
    """Ultralytics .pt and exported YOLO .onnx models use the same interface."""

    def __init__(self, profile="balanced"):
        import torch
        from ultralytics import YOLO

        self.options = PROFILES[profile]
        self.model_name = os.getenv("MODEL_PATH", "yolo11n.pt")
        if ("/" in self.model_name or self.model_name.endswith(".onnx")) and not Path(self.model_name).is_file():
            raise FileNotFoundError(f"Не найдены веса модели: {self.model_name}")
        self.model = YOLO(self.model_name, task="detect")
        requested = os.getenv("DEVICE", "auto")
        self.device = ("0" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu") if requested == "auto" else requested
        if self.device != "cpu" and self.device != "mps" and not torch.cuda.is_available():
            self.device = "cpu"
        self.names = {**NORMALIZE, **json.loads(os.getenv("CLASS_MAP", "{}"))}

    def predict(self, frame):
        try:
            return self._predict(frame)
        except RuntimeError as e:
            if self.device != "cpu" and ("cuda" in str(e).lower() or "memory" in str(e).lower() or "mps" in str(e).lower()):
                self.device = "cpu"
                self.model.to("cpu")
                return self._predict(frame)
            raise

    def _predict(self, frame):
        results = self.model.predict(frame, imgsz=self.options["imgsz"], conf=self.options["confidence"], device=self.device, verbose=False)[0]
        detections = []
        for box in results.boxes.cpu().numpy().data:
            x1, y1, x2, y2, conf, cls = box[:6]
            name = self.names.get(results.names[int(cls)])
            if name in CLASSES:
                detections.append(Detection((float(x1), float(y1), float(x2), float(y2)), CLASSES.index(name), name, float(conf)))
        return detections
