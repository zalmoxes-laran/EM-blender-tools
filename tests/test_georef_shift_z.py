"""E.D.'s rule on heights (23 Oct 2026): **shift Z is 0 for a project** — the
absolute heights are in the models' vertices (E.D. never shifts in z, save
extreme cases). A shift.txt without z is a shift with z 0; a non-zero shift Z
stays possible but the panel says it as an explicit choice.

Measured on the GT16 (GreatTemple_2026_v2.blend): the reconstruction models
carry their heights (493–504 m); with the anchor's Z at 0 nothing is added, and
EM Tools never applies the shift Z to models already in the scene.
"""

import importlib.util
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"_emtools_test_{name}_z", _REPO / "georef_manager" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module          # @dataclass looks its module up
    spec.loader.exec_module(module)
    return module


shift_io = _load("shift_io")
propagation = _load("propagation")


def test_a_shift_txt_without_z_is_z_zero(tmp_path):
    p = tmp_path / "shift.txt"
    p.write_text("EPSG::3844 327372.56 448682.65\n")
    rec = shift_io.parse_shift_file(str(p))
    assert (rec.epsg, rec.x, rec.y, rec.z) == ("3844", 327372.56, 448682.65, 0.0)


def test_a_shift_txt_with_z_keeps_it(tmp_path):
    p = tmp_path / "shift.txt"
    p.write_text("EPSG::31700 327300 448370 500\n")
    rec = shift_io.parse_shift_file(str(p))
    assert (rec.epsg, rec.z) == ("31700", 500.0)


def test_the_gt16_shift_txt_as_written_by_emstudio(tmp_path):
    p = tmp_path / "SHIFT.txt"
    p.write_text("EPSG::3844 327372.56 448682.65 0\n")
    rec = shift_io.parse_shift_file(str(p))
    assert (rec.x, rec.y, rec.z) == (327372.56, 448682.65, 0.0)
    out = tmp_path / "back.txt"
    shift_io.write_shift_file(str(out), rec)
    assert shift_io.parse_shift_file(str(out)) == rec


def test_extra_spaces_are_tolerated(tmp_path):
    p = tmp_path / "shift.txt"
    p.write_text("EPSG::3844  327372.56   448682.65  0\n")
    assert shift_io.parse_shift_file(str(p)).y == 448682.65


def test_zero_says_nothing_another_value_is_an_explicit_choice():
    assert propagation.shift_z_note(0.0) is None
    assert propagation.shift_z_note(None) is None
    note = propagation.shift_z_note(500.0)
    assert note.startswith("Shift Z = 500.000: an explicit choice")
    assert "rule is 0" in note
