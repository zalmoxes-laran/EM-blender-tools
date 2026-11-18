"""MICRO-T-COLORI-NEL-FILE (E.D., 18 Nov 2026): EM Tools reads the colour
schemes an em.json carries (``presentation``, em.json 1.2 ED §2.8).

The module measured is ``visual_manager/file_schemes.py``, which does not
import ``bpy``. When s3Dgraphy is next door, the file is the one s3Dgraphy
writes (the format's reference) and the two readers must agree."""
import importlib.util
import json
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("_em_file_schemes", _REPO / "visual_manager" / "file_schemes.py")
fs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fs)

AAT = "http://vocab.getty.edu/aat/300011176"
EMC = {"metadata": {"property_name": "material", "created": "TempluMare_v10",
                    "description": "Color mapping for material values",
                    "value_codes": {"white rock": AAT}},
       "color_mapping": {"white rock": [0.0, 0.376262, 0.0, 1.0],
                         "empty property material node": [1.0, 0.0, 1.0, 1.0],
                         "no property material node": [0.5, 0.5, 0.5, 1.0]}}


def _doc(**pres):
    return {"header": {"format": "em.json", "version": "1.1"},
            "graphs": {"g1": {"graph_id": "g1", "nodes": [], "edges": []}},
            **({"presentation": pres} if pres else {})}


def test_a_file_without_the_section_has_no_scheme_and_says_nothing():
    section, warnings = fs.read_section(_doc())
    assert section == {"schemes": {}, "active": {}} and warnings == []
    assert fs.active_for(section, "g1") is None


def test_the_schemes_and_the_one_each_graph_uses(tmp_path):
    p = tmp_path / "a.em.json"
    p.write_text(json.dumps(_doc(colour_schemes={"material": EMC, "phase": {
        "metadata": {"property_name": "phase"}, "color_mapping": {"1": [0.1, 0.2, 0.3]}}},
        active_colour_scheme={"g1": "material"})), encoding="utf-8")
    section, warnings = fs.read_file(str(p))
    assert not warnings
    assert fs.active_for(section, "g1") == "material"
    assert fs.active_for(section, "g2") is None
    assert fs.scheme_list(section, "g1") == [
        {"name": "material", "property": "material", "values": 3, "active": True},
        {"name": "phase", "property": "phase", "values": 1, "active": False}]


def test_what_cannot_be_read_is_left_out_and_said():
    section, warnings = fs.read_section(_doc(
        colour_schemes={"ok": EMC, "bad": {"metadata": {}}},
        active_colour_scheme={"g1": "bad"}))
    assert list(section["schemes"]) == ["ok"] and section["active"] == {}
    assert len(warnings) == 2
    assert fs.read_section({"presentation": []})[1]
    assert fs.read_file("/no/such/file.em.json")[1]


def test_the_rows_of_the_list_by_code_then_text_then_grey():
    rows = dict(fs.rows_for(EMC, {"pietra bianca": AAT, "marble": None,
                                  "empty property material node": None,
                                  "no property material node": None}))
    assert rows["pietra bianca"] == (0.0, 0.376262, 0.0, 1.0)      # by its code
    assert rows["marble"] == fs.DEFAULT_COLOR                       # the scheme does not know it
    assert rows["empty property material node"] == (1.0, 0.0, 1.0, 1.0)
    assert rows["white rock"] == (0.0, 0.376262, 0.0, 1.0)          # the scheme's own entry, kept
    three = dict(fs.rows_for({"metadata": {"property_name": "p"}, "color_mapping": {"a": [0.1, 0.2, 0.3]}}, {"a": None}))
    assert three["a"] == (0.1, 0.2, 0.3, 1.0)                      # three floats: alpha 1, as «Load Schema»


def test_the_section_s3dgraphy_writes_is_read_the_same(tmp_path):
    s3d = _REPO.parent / "s3Dgraphy" / "src"
    if not (s3d / "s3dgraphy" / "presentation.py").exists():
        pytest.skip("s3Dgraphy with presentation.py not next door")
    sys.path.insert(0, str(s3d))
    try:
        from s3dgraphy import presentation as P
        from s3dgraphy.container import Container, save_container_file
        from s3dgraphy.graph import Graph
    finally:
        sys.path.remove(str(s3d))
    pres = P.empty()
    P.add_scheme(pres, "material", EMC)
    P.set_active(pres, "g1", "material")
    out = tmp_path / "s.em.json"
    save_container_file(Container(graphs={"g1": Graph(graph_id="g1")}, active_graph_id="g1",
                                  presentation=pres), str(out), bump=False)
    section, warnings = fs.read_file(str(out))
    assert not warnings
    assert fs.active_for(section, "g1") == "material"
    assert section["schemes"]["material"] == json.loads(json.dumps(P.canonical(EMC)))
