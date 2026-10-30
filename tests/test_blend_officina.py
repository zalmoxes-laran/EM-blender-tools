"""MICRO-BLEND-OFFICINA-1 (31 Oct 2026) · EM Tools' half of «Blender as the
workshop»: the status row of a container, the way «Prepare in EMStudio»
reaches EMStudio, the presence of an open session (bpy-free)."""

import json
import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "sync_manager"))

import blend_officina as BO  # noqa: E402


def test_status_line():
    assert BO.status_line(master_stamped=True, versions=2) == "master stamped · 2 versions"
    assert BO.status_line(master_stamped=False, versions=1,
                          counts={"changed_here": 1}) == "master not stamped · 1 version · ↑1"
    assert BO.status_line(master_stamped=None, versions=0).startswith("no master")


def test_prepare_link_ways():
    p = BO.prepare_link(sidecar_clients=1, room={}, container="Reconstruction II AC", em_json="/a.em.json")
    assert p["way"] == "sidecar" and p["envelope"]["type"] == "open"
    assert p["envelope"]["container"] == "Reconstruction II AC"
    p = BO.prepare_link(sidecar_clients=0, room={"server": "https://n", "room": "r1"}, container="C 1")
    assert p["way"] == "link" and p["url"].startswith("stratigraph://open?")
    assert "node=C+1" in p["url"] and "tab=prepare" in p["url"]
    p = BO.prepare_link(sidecar_clients=0, room={}, container="C")
    assert p["way"] is None and "Sidecar" in p["say"]


def test_session_file_is_the_one_s3dgraphy_names(tmp_path):
    blend = tmp_path / "x.blend"
    blend.write_bytes(b"BLENDER")
    f = BO.session_file(str(blend), home=str(tmp_path))
    assert f.startswith(str(tmp_path / ".stratigraph" / "blender-sessions"))
    try:
        from s3dgraphy.resources import blend_folder as BF
    except ImportError:          # an s3dgraphy before 1.6.0.dev77: the copy alone
        return
    assert f == BF.session_file(str(blend), home=str(tmp_path))
    rec = BO.session_record(str(blend), dirty=True, pid=os.getpid(), host="h", now=1.0)
    os.makedirs(os.path.dirname(f))
    with open(f, "w") as fh:
        json.dump(rec, fh)
    assert BO.read_session(str(blend), home=str(tmp_path))["pid"] == os.getpid()


def test_relink_and_relative(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "t.jpg").write_bytes(b"x")
    assert BO.relink_in(str(tmp_path), "t.jpg") == str(tmp_path / "a" / "b" / "t.jpg")
    assert BO.relink_in(str(tmp_path), "none.jpg") == ""
    em = str(tmp_path / "EM")
    files = BO._relative([{"url": str(tmp_path / "SB" / "C" / "versions" / "x.glb")}, {"url": "rel.bin"}], em)
    assert files[0]["url"] == "../SB/C/versions/x.glb" and files[1]["url"] == "rel.bin"
