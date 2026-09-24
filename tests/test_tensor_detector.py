"""Custom adapter contract is exercised with a tiny TorchScript model, no weights download."""

import numpy as np
import pytest


def test_torchscript_adapter_contract_and_class_normalization(tmp_path, monkeypatch):
    import torch
    from ml.detectors.factory import create_detector

    class TinyModel(torch.nn.Module):
        def forward(self, image):
            # This deliberate fixture exercises coordinate scaling and NMS only.
            return torch.tensor([[48.0, 48.0, 96.0, 96.0, 0.9, 0.0], [49.0, 49.0, 97.0, 97.0, 0.8, 0.0]])

    path = tmp_path / "contract.torchscript"
    model = torch.jit.trace(TinyModel(), torch.zeros(1, 3, 480, 480))
    model.save(str(path))
    monkeypatch.setenv("DETECTOR", "torchscript")
    monkeypatch.setenv("MODEL_PATH", str(path))
    monkeypatch.setenv("MODEL_CLASSES", '["person"]')
    monkeypatch.setenv("DEVICE", "cpu")
    detector = create_detector("fast")
    detections = detector.predict(np.zeros((240, 320, 3), dtype=np.uint8))
    assert len(detections) == 1
    assert detections[0].class_name == "pedestrian"
    assert detections[0].bbox == pytest.approx((32, 24, 64, 48))


def test_invalid_detector_is_not_silently_mocked(monkeypatch):
    from ml.detectors.factory import create_detector

    monkeypatch.setenv("DETECTOR", "mock")
    with pytest.raises(ValueError):
        create_detector()
