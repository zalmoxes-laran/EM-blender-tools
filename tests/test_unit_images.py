"""U5 · the images of the units: the convention, the proposals, the cache — without Blender.
The gesture is measured headless in tests/blender_smoke_unit_images.py."""
import importlib.util
import os
import pathlib

_P = pathlib.Path(__file__).resolve().parent.parent / "unit_images" / "core.py"
spec = importlib.util.spec_from_file_location("_unit_images_core", _P)
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)

UNITS = [("n1", "US12"), ("n2", "1.US10"), ("n3", "GT16.USV118"), ("n4", "SF300")]


def test_a_code_is_compared_without_case_and_leading_zeros():
    assert ui.normal_code("US012") == "us12" == ui.normal_code("us12")
    assert ui.normal_code("USV118a") == "usv118a"


def test_a_unit_answers_to_its_name_and_its_last_part():
    assert ui.unit_keys("1.US10") == ["1.us10", "us10"]
    assert ui.unit_keys("US12") == ["us12"]


def test_the_convention_reads_the_code_of_a_file_name():
    assert ui.code_in_filename("/x/US012_north.jpg") == "us12"
    assert ui.code_in_filename("/x/US012.jpg") is None          # {unit}_* wants the underscore
    assert ui.code_in_filename("/x/foto_US12.jpg") is None
    assert ui.code_in_filename("/x/foto_US12.jpg", "foto_{unit}") == "us12"
    assert ui.code_in_filename("/x/US12-a.png", "{unit}-*") == "us12"
    assert ui.code_in_filename("/x/USM100_west.jpg") == "usm100"
    assert ui.code_in_filename("/x/US12_a.jpg", "{unit}_*.jpg") == "us12"
    assert ui.code_in_filename("/x/US12_a.png", "{unit}_*.jpg") is None


def test_the_proposals_are_one_per_image_of_a_known_unit():
    files = ["/d/US012_a.jpg", "/d/US10_b.JPG", "/d/USV118_c.png", "/d/US99_x.jpg",
             "/d/SF300_d.tif", "/d/notes.txt", "/d/US012_a.pdf"]
    got = ui.propose(files, UNITS)
    assert [(os.path.basename(p["path"]), p["unit_name"]) for p in got] == [
        ("SF300_d.tif", "SF300"), ("US012_a.jpg", "US12"), ("US10_b.JPG", "1.US10"),
        ("USV118_c.png", "GT16.USV118")]


def test_the_search_starts_in_the_em_tree(tmp_path):
    for rel in ("EM/DosCo", "RB"):
        (tmp_path / rel).mkdir(parents=True)
    assert ui.start_folders(str(tmp_path)) == [str(tmp_path / "EM" / "DosCo"), str(tmp_path / "EM"),
                                               str(tmp_path / "RB")]
    assert ui.start_folders(None) == []


def test_a_file_of_the_project_is_written_as_a_path_of_the_study(tmp_path):
    p = tmp_path / "EM" / "DosCo" / "US12_a.jpg"
    assert ui.locator_for(str(p), str(tmp_path)) == "/EM/DosCo/US12_a.jpg"
    assert ui.locator_for("/elsewhere/US12_a.jpg", str(tmp_path)) == "/elsewhere/US12_a.jpg"


def test_the_thumbnail_is_keyed_by_the_sha256():
    h = "ab" + "0" * 62
    assert ui.thumb_path("/c", "sha256:" + h) == os.path.join("/c", "ab", h + "_256.png")
