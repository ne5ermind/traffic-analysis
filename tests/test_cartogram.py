from app.cartogram import (arm_for_point, build_cartogram, infer_topology,
                           reference_topology, route_catalog)


def test_triangle_routes_are_distinct_from_four_way_and_never_invented():
    tracks = {
        "7": {"start": [0.1, 0.8], "end": [0.9, 0.8], "seen": 7},
        "8": {"start": [0.51, 0.5], "end": [0.9, 0.8], "seen": 7},
    }
    events = [{"tracker_id": 7, "category": "car"},
              {"tracker_id": 8, "category": "pedestrian"},
              {"tracker_id": None, "category": "car"}]
    result = build_cartogram(events, tracks, {"topology": "three_way"})
    assert result["arms"] == ["Север", "Юго-восток", "Юго-запад"]
    assert result["matrix"] == [{"from": "Юго-запад", "to": "Юго-восток",
                                  "category": "car", "count": 1}]
    assert result["routed"] == 1 and result["unresolved"] == 2
    assert result["routed"] + result["unresolved"] == result["total"]
    assert result["coverage"] == 0.3333
    assert result["direction_matrix"] == [{"direction": 6, "from": "Юго-запад",
                                            "to": "Юго-восток", "category": "car",
                                            "count": 1}]
    assert result["unresolved_by_category"] == [
        {"category": "car", "count": 1}, {"category": "pedestrian", "count": 1}]
    auto = build_cartogram(events, tracks, {"topology": "auto"})
    assert auto["topology"] == "unknown" and auto["matrix"] == []
    assert arm_for_point([0.1, 0.5], "four_way") == "Запад"
    assert arm_for_point([0.9, 0.5], "four_way") == "Восток"


def test_four_arm_topology_only_inferred_when_all_approaches_observed():
    locations = [[0.5, 0], [1, 0.5], [0.5, 1], [0, 0.5]]
    tracks = {str(i): {"start": locations[i % 4], "end": locations[(i + 1) % 4], "seen": 5}
              for i in range(12)}
    assert infer_topology(tracks) == "four_way"
    assert infer_topology({key: value for key, value in tracks.items()
                           if value["start"] != locations[3] and value["end"] != locations[3]}) == "unknown"


def test_supplied_example_schemes_determine_the_shape_not_arbitrary_videos():
    assert reference_topology("Пример 4_утро_1.MOV") == "three_way"
    assert reference_topology("Пример 1_вечер_2.mp4") == "four_way"
    assert reference_topology("Пример 2_вечер_1_ракурс 1.mp4") == "four_way"
    assert reference_topology("Пример 3_вечер_1.mov") == "four_way"
    assert reference_topology("intersection_y.mp4") is None


def test_perspective_keeps_tracks_on_same_side_but_motion_is_visible():
    track = {"start": [0.69, 0.57], "end": [0.88, 0.55], "seen": 7}
    event = {"tracker_id": 7, "category": "car"}
    result = build_cartogram([event], {"7": track}, {"topology": "four_way"})
    assert result["matrix"] == [{"from": "Запад", "to": "Восток", "category": "car", "count": 1}]
    assert result["motion_estimated"] == 1
    result = build_cartogram([event], {"7": track}, {"topology": "three_way"})
    assert result["matrix"] == [{"from": "Юго-запад", "to": "Юго-восток",
                                  "category": "car", "count": 1}]
    assert result["motion_estimated"] == 1


def test_named_user_zone_directions_override_camera_projection():
    geometry = {"mode": "manual", "topology": "four_way"}
    events = [{"tracker_id": None, "category": "bus", "from_direction": "Север",
               "to_direction": "Восток"}]
    result = build_cartogram(events, {}, geometry)
    assert result["routed"] == 1 and result["user_directions"] == 1
    assert result["routed"] + result["unresolved"] == result["total"]
    assert result["matrix"] == [{"from": "Север", "to": "Восток", "category": "bus", "count": 1}]


def test_route_numbers_are_complete_stable_and_bad_legacy_tracks_are_unresolved():
    four_way = route_catalog("four_way")
    assert len(four_way) == 12
    assert four_way[0] == {"direction": 1, "from": "Север", "to": "Восток"}
    assert four_way[-1] == {"direction": 12, "from": "Запад", "to": "Юг"}
    result = build_cartogram(
        [{"tracker_id": 1, "category": "truck"}],
        {"1": {"start": [0.1], "end": [float("nan"), 0.5], "seen": "old"}},
        {"topology": "four_way"})
    assert result["routed"] == 0 and result["unresolved"] == 1
    assert result["unresolved_by_category"] == [{"category": "truck", "count": 1}]
