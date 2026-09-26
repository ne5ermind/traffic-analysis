from backend.exports import cartogram_svg
from ml.audit import audit_result


def three_way_result():
    zones = [
        {"kind": "entry", "points": [{"x": 0.45, "y": 0.01}, {"x": 0.55, "y": 0.01}]},
        {"kind": "entry", "points": [{"x": 0.01, "y": 0.45}, {"x": 0.01, "y": 0.55}]},
        {"kind": "entry", "points": [{"x": 0.99, "y": 0.45}, {"x": 0.99, "y": 0.55}]},
    ]
    return {
        "calibration": {"zones": zones},
        "movements": [
            {"id": "m1", "name": "Сверху → слева", "path": [[0.5, 0.01], [0.01, 0.5]], "total": 10, "pedestrians": 0, "reliability": 0.9},
            {"id": "m2", "name": "Справа → сверху", "path": [[0.99, 0.5], [0.5, 0.01]], "total": 5, "pedestrians": 0, "reliability": 0.9},
        ],
        "diagnostics": {
            "tracks": 20,
            "unknown_tracks": 2,
            "discarded_short_tracks": 1,
            "discarded_stationary_tracks": 2,
            "mean_detection_confidence": 0.8,
        },
    }


def test_ai_audit_detects_t_intersection():
    audit = audit_result(three_way_result(), {"samples": 10, "sharpness": 200, "brightness": 128, "contrast": 48})
    assert audit["intersection"]["type"] == "Т‑образный перекрёсток"
    assert audit["intersection"]["approaches"] == ["сверху", "справа", "слева"]
    assert audit["confidence"] > 0.7
    assert audit["video_quality"]["discarded_track_ratio"] == 0.15
    assert audit["video_quality"]["discarded_stationary_ratio"] == 0.1
    assert not any("неподвижных ложных" in check["message"] for check in audit["checks"])


def test_ai_audit_warns_about_many_stationary_false_tracks():
    result = three_way_result()
    result["diagnostics"]["discarded_stationary_tracks"] = 8
    audit = audit_result(result, {"samples": 10, "sharpness": 200, "brightness": 128, "contrast": 48})
    assert any("неподвижных ложных" in check["message"] for check in audit["checks"])
    assert audit["verdict"] == "Требуется проверка"


def test_three_way_cartogram_has_three_approach_cards():
    svg = cartogram_svg(three_way_result())
    assert svg.count(">Въезд</text>") == 3
    assert 'x="420" y="350" width="160" height="350"' not in svg
