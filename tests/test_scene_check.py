"""S1 · the scene as a cache of the graph — the decision, without Blender.

`classify_scene` takes what `geometry_summary` says the graph cites and what the
scene holds, and answers in five groups. The Blender reading, the marking and
the download sit around it (`check_scene`) and are measured headless in
`tests/blender_smoke_bring_and_check.py`.
"""

import importlib.util
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load():
    pkg = types.ModuleType("_s1_pkg")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_s1_pkg"] = pkg
    spec = importlib.util.spec_from_file_location(
        "_s1_pkg.scene_check", _REPO / "sync_manager" / "scene_check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sc = _load()

A = "sha256:" + "a" * 64
B = "sha256:" + "b" * 64
C = "sha256:" + "c" * 64
B_OLD = "sha256:" + "d" * 64

SUMMARY = {
    "resident": [
        {"node_id": "rm1", "resource_id": "rm1.model", "checksum": A, "name": "RM 1"},
        {"node_id": "rm2", "resource_id": "rm2.model", "checksum": B, "name": "RM 2"},
        {"node_id": "rm3", "resource_id": "rm3.model", "checksum": C, "name": "RM 3"},
    ],
    "elsewhere": [{"resource_id": "nas", "name": "on the NAS", "url": "smb://nas/x"}],
}

OBJECTS = [
    {"name": "RM1_obj", "type": "MESH", "digest": A, "resource_id": "rm1.model",
     "linked": True},
    {"name": "RM2_old", "type": "MESH", "digest": B_OLD, "resource_id": "rm2.model",
     "linked": True},
    {"name": "Decoration", "type": "MESH", "digest": "", "resource_id": "",
     "linked": False},
    {"name": "Camera", "type": "CAMERA", "digest": "", "resource_id": "",
     "linked": False},
    {"name": "US101", "type": "MESH", "digest": "", "resource_id": "",
     "linked": True},
]


def test_the_five_groups():
    r = sc.classify_scene(SUMMARY, OBJECTS)
    assert [x["node_id"] for x in r["here"]] == ["rm1"]
    assert [x["node_id"] for x in r["changed"]] == ["rm2"]
    assert r["changed"][0]["objects"] == ["RM2_old"]
    assert [x["node_id"] for x in r["missing"]] == ["rm3"]
    assert len(r["external"]) == 1
    # a decoration is only here; a camera is not content; a proxy is linked
    assert r["only_here"] == ["Decoration"]


def test_a_deleted_model_is_missing_again():
    r = sc.classify_scene(SUMMARY, [o for o in OBJECTS if o["name"] != "RM1_obj"])
    assert "rm1" in [x["node_id"] for x in r["missing"]]


def test_the_digest_is_compared_however_it_is_spelled():
    objects = [{"name": "x", "type": "MESH", "digest": "a" * 64,
                "resource_id": "", "linked": True}]
    assert [x["node_id"] for x in sc.classify_scene(SUMMARY, objects)["here"]] == ["rm1"]


def test_one_sentence_per_group():
    r = sc.classify_scene(SUMMARY, OBJECTS)
    lines = sc.sentences(r)
    assert len(lines) == 5
    assert lines[-1].startswith("1 object(s) only here")
    r["downloaded"], r["not_downloaded"], r["why_not"] = 1, 0, ""
    assert sc.sentences(r)[1] == "1 missing: 1 downloaded"


def test_the_first_sentence_says_what_it_measures_and_the_rms_are_counted_apart():
    """Q9 · Templu Mare: «0 model(s) of the graph are in the scene» with 99 RMs
    in the list — it counted only the models with a file in the graph."""
    r = sc.classify_scene(SUMMARY, OBJECTS)
    assert "with a file in the graph" in sc.sentences(r)[0]
    r["rm"] = {"in_scene": 99, "in_graph": 0, "bound": 0}
    lines = sc.sentences(r)
    assert lines[1] == ("RMs: 99 in the scene, 0 in the graph (99 not in it — a "
                        "GraphML carries no models)")
    r["rm"] = {"in_scene": 3, "in_graph": 3, "bound": 3}
    assert sc.sentences(r)[1] == "RMs: 3 in the scene, 3 in the graph"
