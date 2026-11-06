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
                          counts={"changed_here": 1}) == "⚠ master not stamped · 1 version · ↑1"
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



# ── MICRO-TIMBRA-MASTER (6 Nov 2026) ─────────────────────────────────────────

def test_the_master_not_stamped_is_seen_with_its_kind_and_its_gesture():
    assert BO.status_line(master_stamped=False, versions=0, kind="very_high_resolution") == \
        "⚠ master not stamped · very high resolution · 0 versions"
    assert BO.status_line(master_stamped=True, versions=3, kind="complete") == \
        "master stamped · complete · 3 versions"
    s = BO.master_sign(master_url="blend://a.blend#Object/T", stamp_exists=None)
    assert s["stamped"] is False and s["gesture"] == "export_master" and s["say"].startswith("⚠")
    s = BO.master_sign(master_url="../SB/T/master/T.glb", stamp_exists=False)
    assert s["stamped"] is False and s["gesture"] == "stamp_master"
    assert BO.master_sign(master_url="../SB/T/master/T.glb", stamp_exists=True)["stamped"] is True
    assert BO.master_sign(master_url="", stamp_exists=None)["stamped"] is None


def test_a_new_version_of_the_master_is_a_new_file_beside_it():
    p = BO.master_version_path("/p/SB/T/master/Tempio.glb", taken=[], day="2026-11-06")
    assert p == "/p/SB/T/master/Tempio_rev-2026-11-06.glb"
    p = BO.master_version_path("/p/SB/T/master/Tempio.glb", taken=["Tempio_rev-2026-11-06.glb"], day="2026-11-06")
    assert p.endswith("Tempio_rev-2026-11-06-2.glb")
    # a revision of a revision keeps one stem
    p = BO.master_version_path("/p/RB/T/master/Templu_rev-2026-11-01.obj", taken=[], day="2026-11-06")
    assert p.endswith("/Templu_rev-2026-11-06.obj")


def test_the_radar_offers_the_gesture_the_panel_knows():
    from s3dgraphy.resources import blend_folder as BF
    assert BF.EXPORT_MASTER_VERSION == BO.EXPORT_MASTER_VERSION
    src = (_REPO / "sync_manager" / "blend_officina.py").read_text(encoding="utf-8")
    assert '("export_master_version", "Export as a new version of the master"' in src
    assert "elif act == EXPORT_MASTER_VERSION:" in src


def test_kind_of_file(tmp_path):
    obj = tmp_path / "T.obj"
    obj.write_text("mtllib T.mtl\nv 0 0 0\n")
    (tmp_path / "T.mtl").write_text("newmtl m\nmap_Kd T.jpg\n")
    assert BO.kind_of_file(str(obj)) == "complete"
    (tmp_path / "T.mtl").write_text("newmtl m\nKd 1 1 1\n")
    assert BO.kind_of_file(str(obj)) == "very_high_resolution"
