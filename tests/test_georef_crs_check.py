"""Deprecated EPSG codes and «ballpark» transformations, from PROJ's database
(MICRO georiferimento dal grafo, 23 Oct 2026).

The GT16 was in EPSG:31700 (deprecated): PROJ reaches WGS 84 from it only with a
«ballpark» (no datum shift), ~127 m off there. EPSG:3844 is the same grid
(Stereo 70 on Krassowsky 1940) with Pulkovo 1942(58) to WGS 84 (19), ±3 m. The
replacement is read from PROJ's `deprecation` / `supersession` tables — never a
table written by hand; 31700 → 3844 is the test case, not a rule of the code.

Needs pyproj (Blender 5.2 here has it through 3D Survey Collection's wheels);
skipped where it is missing, as in the dev venv. Run with Blender's Python,
with a folder holding a copy of pytest, _pytest, pluggy, iniconfig and pygments
(pure Python, copied from the dev venv) as <pt>:

    PYTHONPATH="$HOME/Library/Application Support/Blender/5.2/extensions/.local/lib/python3.13/site-packages:<pt>" \\
    "/Applications/Blender 520.app/Contents/Resources/5.2/python/bin/python3.13" -m pytest tests/test_georef_crs_check.py
"""

import importlib.util
import pathlib

import pytest

pytest.importorskip("pyproj", reason="pyproj not installed in this Python")

_REPO = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "_emtools_test_crs_check", _REPO / "georef_manager" / "crs_check.py")
crs_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crs_check)

GT16 = (327372.56, 448682.65)


def test_31700_is_deprecated_ballpark_and_3844_is_proposed_on_the_same_grid():
    p = crs_check.proposal("31700", *GT16)
    assert p["warn"] is True
    assert p["info"]["deprecated"] is True
    assert "ballpark" in p["operation"].lower()
    assert p["accuracy"] == "unknown (ballpark)"
    repl = p["replacement"]
    assert repl["epsg"] == 3844 and repl["same_grid"] is True
    assert crs_check.accuracy_words(repl["to_wgs84"]) == "±3 m"


def test_3844_says_nothing_but_its_accuracy():
    p = crs_check.proposal("3844", *GT16)
    assert p["warn"] is False
    assert p["accuracy"] == "±3 m"
    assert "(19)" in p["operation"]


def test_the_same_grid_keeps_the_numbers():
    c = crs_check.convert_point(31700, 3844, *GT16)
    assert c["ok"] and c["same_grid"] and (c["x"], c["y"]) == GT16


def test_another_grid_reprojects_and_says_the_accuracy():
    c = crs_check.convert_point(3844, 32634, *GT16)
    assert c["ok"] and not c["same_grid"]
    assert c["x"] == pytest.approx(639685.86, abs=0.05)
    assert c["y"] == pytest.approx(5041873.94, abs=0.05)
    assert c["op"]["accuracy"] == 3.0


def test_a_current_utm_code_is_not_flagged():
    p = crs_check.proposal("32633", 291960.5, 4640631.8)
    assert p["warn"] is False and p["replacement"] is None


def test_no_epsg_no_answer():
    assert crs_check.proposal("", 0, 0) is None
    assert crs_check.proposal(None, 0, 0) is None
