from ml.detectors.base import Detector, Detection


class MockDetector(Detector):
    """Deterministic detections for generated test videos; never registered in production."""

    model_name = "test-only"
    device = "cpu"

    def __init__(self, step=3):
        self.frame = 0
        self.step = step

    def predict(self, frame):
        x = 20 + self.frame * self.step
        self.frame += 1
        return [Detection((x, 100, x + 40, 140), 0, "car", 0.95)]
