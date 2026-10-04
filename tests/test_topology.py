import xml.etree.ElementTree as ET
import pytest
from pydantic import ValidationError
from ml.local_vlm import Scene
from ml.topology import select_topology, assign_path
from backend.cartogram import cartogram_svg


def scene():
    return dict(status="ok", intersection_type="t", confidence=.9, camera_static=True, fully_visible=True,
                center={"x": .5, "y": .5}, approaches=[
                    dict(id="a", label="Сверху", x=.5, y=.08, angle=0.),
                    dict(id="b", label="Справа", x=.92, y=.5, angle=90.),
                    dict(id="c", label="Слева", x=.08, y=.5, angle=270.)], explanation="Три подхода")


def test_visual_three_way_not_inferred_from_traffic():
    topology = select_topology({}, scene())
    assert len(topology["approaches"]) == 3
    path = [[.5, .08], [.5, .5], [.92, .5]]
    assert [a["id"] for a in assign_path(path, topology)] == ["a", "b"]
    assert assign_path([[.5, .5], [.6, .5], [.92, .5]], topology) is None
    assert assign_path(path, select_topology({}, {**scene(), "fully_visible": False})) is None
    assert assign_path(path, select_topology({}, {**scene(), "camera_static": False})) is None


def test_inconsistent_schema_rejected():
    value = scene(); value.pop("status"); value["approaches"].pop()
    with pytest.raises(ValidationError):
        Scene.model_validate(value)


def test_cartogram_numbers_totals_escaping_and_zero_flow():
    topology = select_topology({}, scene())
    topology["approaches"][0]["label"] = '<script>alert(1)</script>'
    result = {"intersection": topology, "movements": [
        dict(id="m1", path=[[.5,.08],[.5,.5],[.92,.5]], name="A", total=10, source_approach="a", target_approach="b"),
        dict(id="m2", path=[], name="zero", total=0, source_approach="b", target_approach="a"),
        dict(id="unknown", total=2)]}
    root = ET.fromstring(cartogram_svg(result))
    text = ''.join(root.itertext())
    assert text.count("Въезд") == 6
    assert "Без направления на схеме: 2" in text
    assert len(root.findall('.//{http://www.w3.org/2000/svg}script')) == 0
    assert len(root.findall('.//{http://www.w3.org/2000/svg}path[@marker-end]')) == 1


def test_unknown_scene_does_not_invent_fourth_road():
    svg = cartogram_svg({"movements": []})
    assert "Геометрия перекрёстка не определена" in svg
    assert "marker-end=" not in svg


def test_manual_geometry_has_priority_over_model():
    from backend.schemas import Calibration
    model_scene = scene()
    manual = {"intersection_type": "t", "center": model_scene["center"],
              "approaches": [{k: v for k, v in a.items() if k != "angle"} for a in model_scene["approaches"]]}
    config = Calibration.model_validate({"intersection": manual}).model_dump()
    topology = select_topology(config, {**model_scene, "confidence": .1})
    assert topology["source"] == "manual"
    assert topology["usable"]
    assert assign_path([[.5,.08],[.5,.5],[.92,.5]], topology)
    manual["approaches"].pop()
    with pytest.raises(ValidationError):
        Calibration.model_validate({"intersection": manual})


def test_empty_fully_visible_multiroad_geometry_rejected():
    value = scene(); value.pop("status"); value.update(intersection_type="multi_way", approaches=[])
    with pytest.raises(ValidationError):
        Scene.model_validate(value)


def test_impossible_junction_center_is_rejected():
    value = scene(); value.pop("status")
    value["approaches"] = [dict(id="a", label="A", x=.25,y=.35),dict(id="b",label="B",x=.75,y=.35),dict(id="c",label="C",x=.5,y=.15)]
    with pytest.raises(ValidationError, match="центр"):
        Scene.model_validate(value)


def test_disputed_ai_scheme_does_not_publish_numeric_flows():
    topology = {**select_topology({},scene()), "requires_review": True}
    result = {"intersection":topology,"movements":[dict(id="a_b",name="A",total=10,source_approach="a",target_approach="b")]}
    svg = cartogram_svg(result)
    assert "Без направления на схеме: 10" in svg
    assert 'marker-end="' not in svg
