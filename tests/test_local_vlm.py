import copy
import json
import math
import pytest
from pydantic import ValidationError
from ml import local_vlm
from ml.pipeline import Cancelled


def review_value():
    return dict(verdict="review", confidence=.8, intersection_type="t", topology_consistent=True,
                video_issues=["Размытый кадр"], suspect_movements=[{"movement_id": "m1", "reason": "Окклюзия"}], explanation="Проверена выборка")


def test_disabled_skips_video_and_network(monkeypatch, tmp_path):
    monkeypatch.setattr(local_vlm, "LOCAL_VLM_ENABLED", False)
    assert local_vlm.review_video(tmp_path / "missing.mp4", {})["status"] == "disabled"
    assert local_vlm.analyze_scene(tmp_path / "missing.mp4")["status"] == "disabled"


@pytest.mark.parametrize("bad", [{}, {**review_value(), "confidence": 2}, {**review_value(), "confidence": math.nan}, {**review_value(), "verdict": "perfect"}, {**review_value(), "total_vehicles": 100}])
def test_rejects_malformed_or_invented_review(bad):
    with pytest.raises(ValidationError):
        local_vlm.Review.model_validate(bad)


def test_parses_fenced_json():
    assert local_vlm._extract_json('```json\n{"a":1}\n```') == {"a": 1}


def test_review_keeps_only_real_movement_ids(monkeypatch, tmp_path):
    monkeypatch.setattr(local_vlm, "LOCAL_VLM_ENABLED", True)
    monkeypatch.setattr(local_vlm, "_sample_frames", lambda *a, **kw: [{"image": "fake", "time": 1, "detections": []}])
    value = review_value()
    value["suspect_movements"].append({"movement_id": "invented", "reason": "Ошибка"})
    monkeypatch.setattr(local_vlm, "_chat", lambda *a: value)
    review = local_vlm.review_video(tmp_path / "video.mp4", {"movements": [{"id": "m1"}]})
    assert review["status"] == "ok"
    assert [s["movement_id"] for s in review["suspect_movements"]] == ["m1"]


def test_failure_is_visible_and_cancellation_propagates(monkeypatch, tmp_path):
    monkeypatch.setattr(local_vlm, "LOCAL_VLM_ENABLED", True)
    def fail(*args, **kwargs):
        raise ValueError("invalid JSON")
    monkeypatch.setattr(local_vlm, "_sample_frames", fail)
    assert local_vlm.review_video(tmp_path / "video.mp4", {})["status"] == "unavailable"
    def cancel(*args, **kwargs):
        raise Cancelled()
    monkeypatch.setattr(local_vlm, "_sample_frames", cancel)
    with pytest.raises(Cancelled):
        local_vlm.review_video(tmp_path / "video.mp4", {})


def test_flags_do_not_change_counts():
    result = {"total_vehicles": 12, "movements": [{"id": "m1", "total": 12, "requires_review": False}], "intersection": {"requires_review": False}}
    original = copy.deepcopy(result)
    local_vlm.apply_review_flags(result, {"status": "ok", **review_value(), "topology_consistent": False})
    assert result["movements"][0]["requires_review"]
    assert result["intersection"]["requires_review"]
    assert result["total_vehicles"] == original["total_vehicles"]
    assert result["movements"][0]["total"] == 12
    json.dumps(result, allow_nan=False)


def test_ollama_empty_content_structured_json_fallback():
    value = review_value()
    body = {"done_reason": "stop", "message": {"content": "", "thinking": json.dumps(value)}}
    assert local_vlm._decode_response(body, local_vlm.Review) == value
    body["message"]["thinking"] = "Unstructured internal reasoning"
    with pytest.raises(ValueError):
        local_vlm._decode_response(body, local_vlm.Review)
    body["message"]["content"] = json.dumps(value)
    body["done_reason"] = "length"
    with pytest.raises(local_vlm.LocalVLMError):
        local_vlm._decode_response(body, local_vlm.Review)


def test_cancel_terminates_http_process(monkeypatch):
    class Process:
        returncode = None
        terminated = False
        def poll(self):
            return self.returncode
        def terminate(self):
            self.terminated = True
        def wait(self, timeout=None):
            self.returncode = -15
    process = Process()
    monkeypatch.setattr(local_vlm.subprocess, "Popen", lambda *a, **kw: process)
    def cancel():
        raise Cancelled()
    with pytest.raises(Cancelled):
        local_vlm._chat("test", local_vlm.Review, "test", [], cancel)
    assert process.terminated
