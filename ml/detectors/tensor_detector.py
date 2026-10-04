"""Adapter for a documented generic tensor contract, independent of YOLO.

Input: RGB float32 NCHW [1,3,H,W], range 0..1 (direct resize).
Output: [N,6] or [1,N,6]: x1,y1,x2,y2,score,class_index in resized pixels.
Classes configured with MODEL_CLASSES JSON; rows are postprocessed with class-wise NMS.
Models with another output contract should implement Detector directly.
"""

import json
import os
from pathlib import Path
import cv2
import numpy as np
from ml.detectors.base import Detector, Detection, CLASSES, NORMALIZE
from ml.detectors.yolo_detector import PROFILES


class TensorDetector(Detector):
    def __init__(self, profile="balanced", backend="onnx"):
        self.options = PROFILES[profile]
        self.backend = backend
        self.model_name = os.environ["MODEL_PATH"]
        if not Path(self.model_name).is_file():
            raise FileNotFoundError(f"Не найдены веса модели: {self.model_name}")
        self.names = json.loads(os.getenv("MODEL_CLASSES", json.dumps(list(CLASSES))))
        self.mapping = {**NORMALIZE, **json.loads(os.getenv("CLASS_MAP", "{}"))}
        self.device = "cpu"
        if backend == "torchscript":
            import torch

            if os.getenv("DEVICE", "auto") != "cpu" and torch.cuda.is_available():
                self.device = "cuda:0"
            self.model = torch.jit.load(self.model_name, map_location=self.device).eval()
            self.size = (self.options["imgsz"], self.options["imgsz"])
        else:
            import onnxruntime as ort

            providers = ["CPUExecutionProvider"]
            if os.getenv("DEVICE", "auto") != "cpu" and "CUDAExecutionProvider" in ort.get_available_providers():
                providers.insert(0, "CUDAExecutionProvider")
                self.device = "cuda:0"
            self.model = ort.InferenceSession(self.model_name, providers=providers)
            shape = self.model.get_inputs()[0].shape
            self.size = tuple(v if isinstance(v, int) and v > 0 else self.options["imgsz"] for v in shape[-2:])

    def predict(self, frame):
        h, w = self.size
        tensor = cv2.cvtColor(cv2.resize(frame, (w, h)), cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32) / 255
        if self.backend == "torchscript":
            import torch

            with torch.inference_mode():
                try:
                    output = self.model(torch.from_numpy(tensor).to(self.device)).detach().cpu().numpy()
                except RuntimeError as e:
                    if self.device != "cpu" and ("cuda" in str(e).lower() or "memory" in str(e).lower()):
                        self.device = "cpu"
                        self.model.to("cpu")
                        output = self.model(torch.from_numpy(tensor)).detach().numpy()
                    else:
                        raise
        else:
            output = self.model.run(None, {self.model.get_inputs()[0].name: tensor})[0]
        rows = np.asarray(output)
        if rows.ndim == 3 and rows.shape[0] == 1:
            rows = rows[0]
        if rows.ndim != 2 or rows.shape[1] != 6:
            raise ValueError("TensorDetector ожидает выход Nx6: xyxy, confidence, class_id. Реализуйте adapter для другого формата.")
        result = []
        for class_id in range(len(self.names)):
            name = self.mapping.get(self.names[class_id])
            if name not in CLASSES:
                continue
            candidates = rows[(rows[:, 5] == class_id) & (rows[:, 4] >= self.options["confidence"]) & np.isfinite(rows).all(axis=1)]
            if not len(candidates):
                continue
            boxes = [[float(r[0]), float(r[1]), max(0, float(r[2] - r[0])), max(0, float(r[3] - r[1]))] for r in candidates]
            indices = cv2.dnn.NMSBoxes(boxes, candidates[:, 4].astype(float).tolist(), self.options["confidence"], 0.5)
            for index in np.asarray(indices).reshape(-1):
                row = candidates[index]
                x1, y1, x2, y2 = row[:4] * [frame.shape[1] / w, frame.shape[0] / h, frame.shape[1] / w, frame.shape[0] / h]
                if x2 > x1 and y2 > y1:
                    result.append(Detection((float(x1), float(y1), float(x2), float(y2)), CLASSES.index(name), name, float(row[4])))
        return result
