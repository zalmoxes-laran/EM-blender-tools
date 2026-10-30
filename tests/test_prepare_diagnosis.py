"""MICRO-PREPARA-DIAGNOSI (E.D., 30 Oct 2026) · the pure parts of «Prepare for
a use: diagnosis…» (``sync_manager/prepare_diagnosis.py``): the similarity that
lets a copy become an instance, the level, the canonical name in versions/, the
warning of a removal. The diagnosis itself is s3Dgraphy's
(``tests/test_use_profiles.py`` there); here it is read through the module the
operator uses, on a fake versions/ folder."""

import importlib.util
import json
import math
import os
import pathlib
import sys
import types

import numpy as np
import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load(name):
    pkg = types.ModuleType("_pd_pkg")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_pd_pkg"] = pkg
    spec = importlib.util.spec_from_file_location(
        f"_pd_pkg.{name}", _REPO / "sync_manager" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pd = _load("prepare_diagnosis")
UP = pytest.importorskip("s3dgraphy.resources.use_profiles")


def _column(n=400, seed=3):
    rng = np.random.default_rng(seed)
    return rng.normal(size=(n, 3)) * [0.4, 0.4, 4.0]


def _place(a, angle, scale, t, mirror=False):
    c, s = math.cos(angle), math.sin(angle)
    r = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    if mirror:
        r = r @ np.diag([1, 1, -1])
    return (a @ (r * scale).T) + np.asarray(t)


def test_a_copy_moved_turned_and_scaled_is_an_instance():
    a = _column()
    b = _place(a, 0.7, 0.857, (12.0, -3.0, 0.5))
    m, res = pd.similarity(a, b)
    assert m is not None and res < 1e-9
    m = np.array(m)
    got = (np.hstack([a, np.ones((len(a), 1))]) @ m.T)[:, :3]
    assert np.abs(got - b).max() < 1e-9


def test_a_stretched_copy_or_another_shape_stays_a_copy():
    a = _column()
    m, why = pd.similarity(a, a * [1.0, 1.0, 1.2])
    assert m is None and "stretched" in why
    b = _place(a, 0.3, 1.0, (0, 0, 0))
    b[10] += 0.5
    m, why = pd.similarity(a, b)
    assert m is None and "shape" in why
    m, why = pd.similarity(a, a[:-1])
    assert m is None


def test_a_mirrored_copy_is_still_a_similarity():
    a = _column()
    m, _ = pd.similarity(a, _place(a, 1.1, 1.0, (1, 2, 3), mirror=True))
    assert m is not None and np.linalg.det(np.array(m)[:3, :3]) < 0


def test_level_and_target_name():
    assert pd.level_for(["instances", "texture_side"]) == "lod0"
    assert pd.level_for(["decimate"]) == "lod1"
    web = UP.profile("web")
    assert pd.target_name("/p/SB/versions", "Colonnato", "lod1", web) \
        == "/p/SB/versions/Colonnato@lod1-web.glb"
    her = UP.profile("heriverse")
    assert pd.target_name("/p/SB/versions", "Colonnato", "lod0", her) \
        == "/p/SB/versions/Colonnato@lod0-aton-heriverse/Colonnato.gltf"
    assert pd.target_name("/p/v", "Colonnato", "lod0", her, "glb").endswith(
        "Colonnato@lod0-aton-heriverse.glb")


def test_target_files_never_overwritten_silently(tmp_path):
    entry = str(tmp_path / "M@lod0-web.glb")
    assert pd.target_files(entry) == []
    open(entry, "wb").write(b"glTF")
    open(entry + ".stamp.json", "w").write("{}")
    assert pd.target_files(entry) == [entry, entry + ".stamp.json"]
    g = tmp_path / "M@lod0-aton-heriverse"
    g.mkdir()
    (g / "M.gltf").write_text("{}")
    assert pd.target_files(str(g / "M.gltf")) == [str(g)]


def test_effect_and_removal_lines():
    assert pd.effect_line({"triangles": 0, "triangles_stored": -586_000, "draw_calls": -11,
                           "download_bytes": -23 * 1048576, "gpu_bytes": 0}) \
        == "-586,000 tris stored · -23.0 MB download · -11 draw calls"
    assert pd.effect_line({}) == "—"
    lines = pd.file_rows_lines([{"name": "M@lod0-web.glb", "files": ["a", "b"],
                                 "bytes": 2 * 1048576}], {"M@lod0-web.glb": ["M lod0 for Web"]})
    assert lines == ["M@lod0-web.glb: 2 file(s), 2.0 MB", "   graph: M lod0 for Web"]


def test_the_module_reads_s3dgraphys_table():
    assert pd.use_profiles() is UP
    assert {p["id"] for p in UP.profiles()} >= {"web", "realtime", "heriverse", "mobile_ar",
                                                "archive"}
