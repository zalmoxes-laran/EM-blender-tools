"""MICRO tileset-cartella (E.D., 25 Oct 2026) — a tileset as it arrives.

Outside Blender: the forms recognised (a folder with tileset.json, the
RealityScan pair chosen three ways, a zip holding the pair, a zip holding the
folder with its root beside it, a zip with nothing usable — the message says
what is inside), the package written beside the original (never inside, never
over a file, the original's bytes untouched), a .3tz through 3D Survey
Collection's writer when its checkout is on this disk, and the position line
with the Basilica Iulia's transform (lat 0.0001°, lon 10.51°: the warning).
"""

import hashlib
import importlib.util
import json
import os
import pathlib
import zipfile

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ts = _load("tileset_shape", _REPO / "rm_manager" / "tileset_shape.py")
_3DSC = _REPO.parent / "3D-survey-collection" / "cesium_exporter" / "archive_3tz.py"

#: the Basilica Iulia's root transform (RealityScan 2.2), as measured
BASILICA_T = [-0.18243234, 0.98321841, 0.0, 0.0, -0.00000197, -0.00000036, 1.0, 0.0,
              0.98321841, 0.18243234, 0.000002, 0.0,
              6271103.68898329, 1163587.9280063, 12.30476309, 1.0]


def _root(prefix, transform=BASILICA_T):
    return {"asset": {"version": "1.0", "extras": {"createdWith": "RealityScan 2.2.0.119430"}},
            "geometricError": 54.8,
            "root": {"boundingVolume": {"box": [0, 0, 0, 5, 0, 0, 0, 5, 0, 0, 0, 5]},
                     "geometricError": 0.9, "refine": "REPLACE", "transform": transform,
                     "content": {"url": f"{prefix}Geometry/lod1_0.b3dm"},
                     "children": [{"boundingVolume": {"box": [0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2]},
                                   "geometricError": 0.1,
                                   "content": {"url": f"{prefix}tileset_lod1_0.json"}}]}}


def _rs_folder(where, name="tileset_X"):
    """The RealityScan export: X.json beside X/ (Geometry + a lod json)."""
    d = where / name
    (d / "Geometry").mkdir(parents=True)
    (d / "Geometry" / "lod1_0.b3dm").write_bytes(b"b3dm" + b"\0" * 60)
    (d / "Geometry" / "lod0_0.b3dm").write_bytes(b"b3dm" + b"\1" * 40)
    (d / "tileset_lod1_0.json").write_text(json.dumps(
        {"asset": {"version": "1.0"}, "geometricError": 0.1,
         "root": {"boundingVolume": {"box": [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]},
                  "geometricError": 0, "content": {"url": "Geometry/lod0_0.b3dm"}}}))
    (where / f"{name}.json").write_text(json.dumps(_root(f"{name}/")))
    return d


def _digest(path):
    h = hashlib.sha256()
    for p in sorted(pathlib.Path(path).rglob("*")) if os.path.isdir(path) else [pathlib.Path(path)]:
        if p.is_file():
            h.update(str(p.relative_to(path) if os.path.isdir(path) else p.name).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


# ── the forms ────────────────────────────────────────────────────────────────

def test_folder_with_tileset_json(tmp_path):
    d = tmp_path / "T"
    (d / "t").mkdir(parents=True)
    (d / "tileset.json").write_text(json.dumps(_root("")))
    r = ts.recognise(str(d))
    assert r["form"] == "folder" and r["ready"] and r["preparable"]
    assert ts.recognise(str(d / "tileset.json"))["form"] == "folder"


@pytest.mark.parametrize("chosen", ["folder", "json", "parent"])
def test_realityscan_pair_three_ways(tmp_path, chosen):
    parent = tmp_path / "BasilicaTSL_cesium"
    parent.mkdir()
    d = _rs_folder(parent)
    path = {"folder": d, "json": parent / "tileset_X.json", "parent": parent}[chosen]
    r = ts.recognise(str(path))
    assert r["form"] == "pair" and not r["ready"] and r["preparable"]
    assert "RealityScan" in r["says"] and "no tileset.json" in r["says"]
    assert r["root_json"].endswith("tileset_X.json") and r["folder"] == str(d)
    out = ts.package_path(r, ".zip")
    # beside what was chosen, never inside it
    assert os.path.dirname(out) == os.path.dirname(str(path).rstrip(os.sep))
    assert not out.startswith(str(d) + os.sep)


def test_zip_holding_the_pair(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _rs_folder(src)
    z = tmp_path / "Archivio.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for p in sorted(src.rglob("*")):
            zf.write(p, p.relative_to(src).as_posix())
    r = ts.recognise(str(z))
    assert r["form"] == "zip_pair" and r["preparable"] and r["name"] == "tileset_X"


def test_zip_holding_the_folder_alone_finds_its_root_beside(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _rs_folder(src)
    z = tmp_path / "Archivio.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for p in sorted((src / "tileset_X").rglob("*")):
            zf.write(p, p.relative_to(src).as_posix())
    # no root beside: the message says what is inside and what to do
    r = ts.recognise(str(z))
    assert r["form"] == "unknown" and not r["preparable"]
    assert "No tileset.json in Archivio.zip" in r["says"]
    assert "tileset_X/ (1 json, 2 tiles)" in r["says"]
    assert "tileset_X.json beside the zip" in r["says"] and "RealityScan" in r["says"]
    # the root beside the zip: preparable
    (tmp_path / "tileset_X.json").write_text((src / "tileset_X.json").read_text())
    r = ts.recognise(str(z))
    assert r["form"] == "zip_no_root" and r["preparable"]
    assert "without its root" in r["says"]


def test_a_package_is_ready_and_unknowns_say_why(tmp_path):
    z = tmp_path / "p.3tz"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("tileset.json", json.dumps(_root("")))
    r = ts.recognise(str(z))
    assert r["form"] == "package" and r["ready"] and not r["preparable"]
    e = tmp_path / "empty"
    e.mkdir()
    assert "No tileset in the folder empty/" in ts.recognise(str(e))["says"]
    (tmp_path / "n.zip").write_bytes(b"not a zip")
    assert "not a readable archive" in ts.recognise(str(tmp_path / "n.zip"))["says"]


# ── where it falls ───────────────────────────────────────────────────────────

def test_position_basilica_warns():
    p = ts.position(_root("x/"))
    assert p["kind"] == "earth" and p["warn"]
    assert abs(p["lat"]) < 0.001 and abs(p["lon"] - 10.5115) < 0.001 and abs(p["h"] - 3.7) < 0.5
    assert "geocentric" in p["line"] and "RealityScan" in p["line"]


def test_position_true_place_and_local_frame():
    # the Forum, Rome: 41.8925 N 12.4853 E, 40 m — ECEF by the forward formula
    lat, lon, h = map(float, (41.8925, 12.4853, 40.0))
    a, e2 = 6378137.0, 6.69437999014e-3
    import math
    n = a / math.sqrt(1 - e2 * math.sin(math.radians(lat)) ** 2)
    x = (n + h) * math.cos(math.radians(lat)) * math.cos(math.radians(lon))
    y = (n + h) * math.cos(math.radians(lat)) * math.sin(math.radians(lon))
    z = (n * (1 - e2) + h) * math.sin(math.radians(lat))
    t = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]
    p = ts.position(_root("", t))
    assert not p["warn"] and abs(p["lat"] - lat) < 1e-6 and abs(p["h"] - h) < 1e-3
    assert ts.position(_root("", None))["kind"] == "local"
    assert ts.position({"root": {}})["kind"] == "local"


# ── preparing ────────────────────────────────────────────────────────────────

def _check_package(path, name="tileset_X"):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        assert "tileset.json" in names
        assert f"{name}/Geometry/lod1_0.b3dm" in names
        assert f"{name}/tileset_lod1_0.json" in names
        doc = json.loads(z.read("tileset.json"))
        assert doc["root"]["content"]["url"] == f"{name}/Geometry/lod1_0.b3dm"


def test_prepare_zip_from_the_pair_beside_never_over(tmp_path):
    parent = tmp_path / "BasilicaTSL_cesium"
    parent.mkdir()
    d = _rs_folder(parent)
    (parent / "tileset_X.zip").write_bytes(b"somebody's file")
    before = _digest(parent)
    r = ts.recognise(str(d))
    got = ts.prepare(r, writer_3tz=None)
    assert got["format"] == "zip" and got["path"].endswith("tileset_X-2.zip")
    assert (parent / "tileset_X.zip").read_bytes() == b"somebody's file"
    _check_package(got["path"])
    os.remove(got["path"])
    assert _digest(parent) == before                      # the original untouched
    assert not any(p.name.startswith(".em-tileset-") for p in parent.iterdir())


def test_prepare_zip_from_the_zips(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _rs_folder(src)
    zp = tmp_path / "pair.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        for p in sorted(src.rglob("*")):
            zf.write(p, p.relative_to(src).as_posix())
    _check_package(ts.prepare(ts.recognise(str(zp)))["path"])
    alone = tmp_path / "alone"
    alone.mkdir()
    za = alone / "Archivio.zip"
    with zipfile.ZipFile(za, "w") as zf:
        for p in sorted((src / "tileset_X").rglob("*")):
            zf.write(p, p.relative_to(src).as_posix())
    (alone / "tileset_X.json").write_text((src / "tileset_X.json").read_text())
    got = ts.prepare(ts.recognise(str(za)))
    assert os.path.dirname(got["path"]) == str(alone)
    _check_package(got["path"])


def test_prepare_3tz_through_a_folder_writer(tmp_path):
    """The .3tz writer packs FOLDERS (3DSC's write_3tz): the pair is staged
    with hard links beside the output and removed after."""
    parent = tmp_path / "P"
    parent.mkdir()
    d = _rs_folder(parent)
    seen = {}

    def writer(src_dir, out_path):
        seen["files"] = sorted(p.relative_to(src_dir).as_posix()
                               for p in pathlib.Path(src_dir).rglob("*") if p.is_file())
        seen["inside"] = out_path.startswith(src_dir)
        with zipfile.ZipFile(out_path, "w") as z:
            for f in seen["files"]:
                z.write(os.path.join(src_dir, f), f)
        return {"entries": len(seen["files"])}

    got = ts.prepare(ts.recognise(str(d)), writer_3tz=writer)
    assert got["format"] == "3tz" and got["path"] == str(parent / "tileset_X.3tz")
    assert seen["files"][0] == "tileset.json" and not seen["inside"]
    _check_package(got["path"])
    assert not any(p.name.startswith(".em-tileset-") for p in parent.iterdir())
    assert (d / "Geometry" / "lod1_0.b3dm").stat().st_nlink == 1   # the links are gone


@pytest.mark.skipif(not _3DSC.is_file(), reason="no 3D Survey Collection checkout beside")
def test_prepare_3tz_with_3dsc_writer(tmp_path):
    a3 = _load("archive_3tz", _3DSC)
    parent = tmp_path / "P"
    parent.mkdir()
    _rs_folder(parent)
    got = ts.prepare(ts.recognise(str(parent / "tileset_X.json")), writer_3tz=a3.write_3tz)
    _check_package(got["path"])
    v = a3.verify_3tz(got["path"])
    assert v["ok"], v["errors"]
