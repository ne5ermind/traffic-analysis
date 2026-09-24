import pytest
from ml.geometry import point_in_zone, cross_direction, line_events, manual_assignment, resample
from ml.pipeline import can_stitch
from backend.schemas import Calibration

POLYGON = [{"x": 0, "y": 0}, {"x": 0.3, "y": 0}, {"x": 0.3, "y": 1}, {"x": 0, "y": 1}]
LINE = {"id": "L", "name": "Контроль", "points": [{"x": 0.5, "y": 0}, {"x": 0.5, "y": 1}]}


def test_zone_inside_outside_boundary():
    assert point_in_zone((0.1, 0.4), POLYGON)
    assert point_in_zone((0.3, 0.4), POLYGON)
    assert not point_in_zone((0.6, 0.4), POLYGON)


def test_finite_line_and_jitter():
    assert cross_direction((0.2, 0.5), (0.8, 0.5), LINE["points"]) == -1
    assert cross_direction((0.2, 1.5), (0.8, 1.5), LINE["points"]) == 0
    assert cross_direction((0.499, 0.5), (0.501, 0.5), LINE["points"]) == 0


def test_slow_crossing_dead_band_and_repeat_count_once():
    path = [[0.4, 0.5, 0], [0.499, 0.5, 1], [0.5, 0.5, 2], [0.501, 0.5, 3], [0.6, 0.5, 4], [0.4, 0.5, 5], [0.6, 0.5, 6]]
    assert len(line_events(path, [LINE])) == 1
    assert line_events(path, [LINE])[0]["time"] == 4


def test_entry_before_exit():
    config = {
        "zones": [
            {"id": "A", "name": "Въезд", "kind": "entry", "points": POLYGON},
            {"id": "B", "name": "Выезд", "kind": "exit", "points": [{"x": p["x"] + 0.7, "y": p["y"]} for p in POLYGON]},
        ]
    }
    path = [[0.1, 0.5, 0], [0.5, 0.5, 1], [0.9, 0.5, 2]]
    assert manual_assignment(path, config)[0] == "zone_A_B"
    assert manual_assignment([[0.9, 0.5, 0], [0.5, 0.5, 1], [0.1, 0.5, 2]], config)[0] == "unknown"
    assert manual_assignment([[0.5, 0.5, 0], [0.9, 0.5, 1]], config)[0] == "unknown"


def test_stationary_resampling_and_u_turn():
    assert resample([[0.5, 0.5, 0], [0.5, 0.5, 1]]) is None
    assert resample([[0.1, 0.5, 0], [0.8, 0.5, 1], [0.1, 0.5, 2]]).shape == (8, 2)


def test_fragment_stitch_does_not_merge_reentry_or_concurrent():
    t = {"last_seen": 1, "votes": {"car": 3}, "trajectory": [[0.1, 0.5, 0], [0.2, 0.5, 0.5], [0.3, 0.5, 1]]}
    assert can_stitch(t, [0.4, 0.5], 1.5, "car")
    assert not can_stitch(t, [0.3, 0.5], 1, "car")
    assert not can_stitch(t, [0.4, 0.5], 4, "car")
    assert not can_stitch(t, [0.4, 0.5], 1.5, "pedestrian")
    assert not can_stitch(t, [0.1, 0.5], 1.5, "car")


def test_invalid_shapes():
    with pytest.raises(ValueError):
        Calibration.model_validate({"lines": [{"id": "a", "name": "a", "points": [{"x": 0.5, "y": 0.5}] * 2}]})
    with pytest.raises(ValueError):
        Calibration.model_validate({"zones": [{"id": "a", "name": "a", "kind": "entry", "points": [{"x": 0.5, "y": 0.5}] * 3}]})


def test_zone_crossing_between_samples():
    from ml.geometry import zone_events

    zone = {
        "id": "thin",
        "name": "Тонкая зона",
        "kind": "entry",
        "points": [{"x": 0.45, "y": 0}, {"x": 0.55, "y": 0}, {"x": 0.55, "y": 1}, {"x": 0.45, "y": 1}],
    }
    events = zone_events([[0.1, 0.5, 0], [0.9, 0.5, 1]], [zone])
    assert len(events) == 1
    assert events[0][0] == pytest.approx(0.4375)


def test_jitter_does_not_form_a_direction():
    assert resample([[0.5 + (i % 2) * 0.002, 0.5, i] for i in range(100)]) is None
