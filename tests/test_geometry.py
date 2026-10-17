import pytest

from app.geometry import PassageCounter, UniqueTrackCounter, inside, segment_crossing


def test_finite_segment_crossing_and_polygon():
    assert segment_crossing((0.1, 0.5), (0.9, 0.5), [(0.5, 0.2), (0.5, 0.8)]) == 0.5
    assert segment_crossing((0.1, 0.9), (0.9, 0.9), [(0.5, 0.2), (0.5, 0.8)]) is None
    assert segment_crossing((0.1, 0.5), (0.5, 0.5), [(0.5, 0.2), (0.5, 0.8)]) == 1
    assert segment_crossing((0.5, 0.5), (0.9, 0.5), [(0.5, 0.2), (0.5, 0.8)]) is None
    assert inside((0.5, 0.5), [(0, 0), (1, 0), (1, 1), (0, 1)])
    assert inside((1, 0.5), [(0, 0), (1, 0), (1, 1), (0, 1)])
    assert not inside((1.1, 0.5), [(0, 0), (1, 0), (1, 1), (0, 1)])


def test_exit_time_interpolated_before_confirmation():
    counter = PassageCounter({"N": [[0.25, 0], [0.25, 1]]},
                             {"S": [[0.75, 0], [0.75, 1]]}, [], confirmation=2)
    assert counter.feed(7, (0.1, 0.5), 0, "car", 0.8) == []
    assert counter.feed(7, (0.4, 0.5), 1, "car", 0.8) == []
    assert counter.feed(7, (0.9, 0.5), 2, "car", 0.8) == []
    events = counter.feed(7, (0.95, 0.5), 3, "car", 0.8)
    assert len(events) == 1
    assert abs(events[0]["time_s"] - 1.7) < 1e-9
    assert events[0]["from_direction"] == "N"
    assert events[0]["to_direction"] == "S"


def test_half_open_bins():
    assert int(899.999 // 900) == 0
    assert int(900 // 900) == 1


def test_automatic_count_uses_stable_track_once_and_filters_short_detections():
    counter = UniqueTrackCounter(minimum_observations=3)
    assert counter.feed(1, (0.2, 0.3), 0, "car", 0.9) == []
    assert counter.feed(2, (0.4, 0.7), 0, "pedestrian", 0.8) == []
    assert counter.feed(1, (0.3, 0.3), 0.1, "car", 0.8) == []
    assert counter.feed(1, (0.4, 0.3), 0.2, "car", 0.9) == []  # Too brief at 12 fps.
    found = counter.feed(1, (0.45, 0.3), 0.5, "car", 0.9)
    assert len(found) == 1
    assert found[0]["category"] == "car"
    assert found[0]["start_s"] == 0
    assert found[0]["motion"]["duration_s"] == 0.5
    assert found[0]["motion"]["displacement"] > found[0]["motion"]["required_displacement"]
    assert (found[0]["from_direction"], found[0]["to_direction"]) == ("В кадре", "В кадре")
    assert counter.feed(1, (0.6, 0.3), 1, "car", 0.9) == []
    assert counter.feed(2, (0.42, 0.8), 0.2, "pedestrian", 0.9) == []
    assert counter.feed(2, (0.45, 0.8), 0.5, "pedestrian", 0.9)[0]["category"] == "pedestrian"


def test_passage_handles_exact_touch_and_both_lines_between_sampled_frames():
    counter = PassageCounter({"N": [[0.25, 0], [0.25, 1]]},
                             {"S": [[0.75, 0], [0.75, 1]]}, [], confirmation=2)
    assert counter.feed(1, (0.1, 0.5), 0, "car", 0.8) == []
    # At low sampling rates a vehicle can pass both boundaries in one interval.
    assert counter.feed(1, (0.9, 0.5), 1, "truck", 0.9) == []
    events = counter.feed(1, (0.95, 0.5), 2, "truck", 0.7)
    assert len(events) == 1
    assert events[0]["from_direction"] == "N" and events[0]["to_direction"] == "S"
    assert events[0]["start_s"] == pytest.approx(0.1875)
    assert events[0]["time_s"] == pytest.approx(0.8125)
    assert events[0]["category"] == "truck"  # Majority vote, not the last raw class.
    assert events[0]["confidence"] == 0.8

    touching = PassageCounter({"N": [[0.25, 0], [0.25, 1]]},
                              {"S": [[0.75, 0], [0.75, 1]]}, [], confirmation=2)
    for point, pts in [((0.1, 0.5), 0), ((0.25, 0.5), 1),
                       ((0.4, 0.5), 2), ((0.75, 0.5), 3)]:
        assert touching.feed(2, point, pts, "car", 0.9) == []
    event = touching.feed(2, (0.8, 0.5), 4, "car", 0.9)
    assert len(event) == 1 and event[0]["time_s"] == 3


def test_automatic_counter_rejects_static_and_duplicate_timestamp_tracks():
    counter = UniqueTrackCounter()
    assert counter.feed(10, (0.5, 0.5), 0, "car", 0.9, box_size=(0.2, 0.1)) == []
    assert counter.feed(10, (0.5, 0.5), 0, "car", 0.9, box_size=(0.2, 0.1)) == []
    assert counter.feed(10, (0.501, 0.5), .5, "car", 0.9, box_size=(0.2, 0.1)) == []
    assert counter.feed(10, (0.499, 0.5), 1, "car", 0.9, box_size=(0.2, 0.1)) == []
    assert sum(counter.tracks[10]["votes"].values()) == 3

    small = UniqueTrackCounter()
    assert small.feed(11, (0.1, 0.5), 0, "car", 0.8, box_size=(0.01, 0.01)) == []
    assert small.feed(11, (0.103, 0.5), .2, "car", 0.8, box_size=(0.01, 0.01)) == []
    assert len(small.feed(11, (0.106, 0.5), .5, "car", 0.8,
                          box_size=(0.01, 0.01))) == 1

    large = UniqueTrackCounter()
    large.feed(12, (0.1, 0.5), 0, "car", 0.8, box_size=(0.2, 0.2))
    large.feed(12, (0.103, 0.5), .2, "car", 0.8, box_size=(0.2, 0.2))
    assert large.feed(12, (0.106, 0.5), .5, "car", 0.8,
                      box_size=(0.2, 0.2)) == []


def test_automatic_confirmation_is_duration_based_across_sample_rates():
    for fps in (2, 6, 12):
        counter = UniqueTrackCounter()
        events = []
        for index in range(fps + 1):
            pts = index / fps
            events.extend(counter.feed(20, (0.1 + 0.05 * pts, 0.5), pts,
                                       "car", 0.8, box_size=(0.04, 0.02)))
            if events:
                break
        assert len(events) == 1
        assert 0.4 <= events[0]["motion"]["duration_s"] <= 1.0
