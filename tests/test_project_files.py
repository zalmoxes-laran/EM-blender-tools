"""Proxies and models as files of the EM project (E.D., 23 Oct 2026): where
they go, their names, and the fallbacks (bpy-free)."""

import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "sync_manager"))

import project_files as pf  # noqa: E402


def test_the_standard_tree_wins(tmp_path):
    root = tmp_path / "Tempio"
    where = pf.project_folders(str(root), str(root / "EM" / "x.em.json"))
    assert where["proxies"] == os.path.join(str(root), "EM", "proxies")
    assert where["models"] == os.path.join(str(root), "RM")
    assert where["standard"] is True


def test_without_a_tree_beside_the_emjson(tmp_path):
    where = pf.project_folders(None, str(tmp_path / "a" / "x.em.json"))
    assert where["proxies"] == os.path.join(str(tmp_path / "a"), "proxies")
    assert where["models"] == os.path.join(str(tmp_path / "a"), "RM")
    assert where["standard"] is False


def test_never_saved_has_no_place():
    assert pf.project_folders(None, "") is None
    assert pf.project_folders(None, None) is None


def test_the_proxy_file_is_the_url_the_graph_writes(tmp_path):
    path = pf.proxy_file(str(tmp_path), "US004")
    assert path == os.path.join(str(tmp_path), "US004.glb")
    # the graph's url, relative to the EM folder, names the same file
    assert pf.relative_url(os.path.dirname(str(tmp_path)), path).endswith(
        os.path.basename(str(tmp_path)) + "/US004.glb")
    assert pf.proxy_file(str(tmp_path), "a/b") is None
    assert pf.proxy_file(str(tmp_path), "") is None


def test_a_model_goes_in_its_container_folder(tmp_path):
    rm = str(tmp_path / "RM")
    assert pf.model_folder(rm, "Survey 2015") == os.path.join(rm, "Survey 2015")
    assert pf.model_folder(rm, "Reconstruction: 2nd c. AD/ver") == \
        os.path.join(rm, "Reconstruction_ 2nd c. AD_ver")
    assert pf.model_folder(rm, "") == os.path.join(rm, pf.NO_CONTAINER)
    assert pf.model_folder(rm, None) == os.path.join(rm, pf.NO_CONTAINER)


def test_object_and_unit_meet_as_the_old_exporter_did():
    units = ["US1", "US12", "USV100"]
    assert pf.unit_for_object("US1", units) == "US1"
    assert pf.unit_for_object("TM.US12", units) == "US12"
    assert pf.unit_for_object("US1.001", units) is None
    assert pf.unit_for_object("Cube", units) is None
    assert pf.unit_for_object("A.B.USV100", units) == "USV100"
