from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np

CLASSES = ("car", "truck", "bus", "motorcycle", "bicycle", "pedestrian")
NORMALIZE = {"person": "pedestrian", "motorbike": "motorcycle", **{c: c for c in CLASSES}}


@dataclass(frozen=True)
class Detection:
    bbox: tuple[float, float, float, float]  # xyxy, original frame pixels
    class_id: int  # canonical index in CLASSES
    class_name: str
    confidence: float


class Detector(ABC):
    device: str = "cpu"
    model_name: str = "custom"

    @abstractmethod
    def predict(self, frame: np.ndarray) -> list[Detection]: ...
