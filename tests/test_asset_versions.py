"""A1–A3 · an asset and its versions in the scene — the decisions, without Blender.

ONE object per asset; a library .blend per asset with the meshes of all its
versions; «LOD ▸» swaps the mesh; the cache is checked mesh by mesh against the
digests the graph cites. The Blender side is measured headless in
`tests/blender_smoke_asset_versions.py` (T-A2, T-A3).
"""

import importlib.util
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load(name):
    pkg = types.ModuleType("_av_pkg")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_av_pkg"] = pkg
    spec = importlib.util.spec_from_file_location(
        f"_av_pkg.{name}", _REPO / "sync_manager" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


av = _load("asset_versions")
sp = _load("scene_package")

S = {k: "sha256:" + c * 64 for k, c in (("0", "0"), ("1", "1"), ("2", "2"),
                                         ("2b", "b"))}
VERSIONS = [
    {"id": "podio", "level": "LOD0", "master": True, "checksum": S["0"],
     "residency": "resident"},
    {"id": "v1", "level": "LOD1", "master": False, "checksum": S["1"],
     "residency": "resident"},
    {"id": "v2", "level": "LOD2", "master": False, "checksum": S["2"],
     "residency": "resident"},
]


def test_an_empty_library_fetches_every_version():
    plan = av.plan_library(VERSIONS, {})
    assert [(r["level"], r["why"]) for r in plan["fetch"]] == \
        [("LOD0", "missing"), ("LOD1", "missing"), ("LOD2", "missing")]


def test_only_the_mesh_whose_digest_changed_is_fetched():
    plan = av.plan_library(
        [*VERSIONS[:2], {**VERSIONS[2], "checksum": S["2b"]}],
        {"LOD0": S["0"], "LOD1": S["1"], "LOD2": S["2"]})
    assert [r["level"] for r in plan["here"]] == ["LOD0", "LOD1"]
    assert [(r["level"], r["why"], r["held"]) for r in plan["fetch"]] == \
        [("LOD2", "changed", S["2"])]


def test_a_digest_is_compared_with_or_without_its_prefix():
    plan = av.plan_library(VERSIONS[:1], {"LOD0": "0" * 64})
    assert [r["level"] for r in plan["here"]] == ["LOD0"]


def test_a_master_without_bytes_stays_local_and_a_reference_is_external():
    rows = [{"id": "m", "level": "LOD0", "master": True, "checksum": ""},
            {"id": "v", "level": "LOD1", "checksum": S["1"], "residency": "reference"}]
    plan = av.plan_library(rows, {})
    assert [r["id"] for r in plan["local"]] == ["m"]
    assert [r["id"] for r in plan["external"]] == ["v"]
    assert plan["fetch"] == []


def test_lod_steps_in_natural_order_and_stops_at_the_ends():
    levels = ["LOD10", "LOD2", "LOD0", "LOD1"]
    assert av.step_level(levels, "LOD0", +1) == "LOD1"
    assert av.step_level(levels, "LOD2", +1) == "LOD10"
    assert av.step_level(levels, "LOD10", +1) == "LOD10"
    assert av.step_level(levels, "LOD0", -1) == "LOD0"
    assert av.step_level(levels, None, +1) == "LOD0"
    assert av.step_level([], "LOD0", +1) is None


def test_the_next_level_proposed_and_the_names_in_the_library():
    assert av.next_level(["LOD0", "LOD1"]) == "LOD2"
    assert av.next_level([]) == "LOD1"
    assert av.mesh_name("OB_PODIO", "LOD1") == "OB_PODIO@LOD1"
    assert av.level_of_mesh_name("OB_PODIO@LOD1") == "LOD1"
    assert av.level_of_mesh_name("OB_PODIO") is None


def test_one_library_per_asset_under_the_room():
    assert av.library_relpath("podio", "scavo 2026") == "em_cache/scavo_2026/podio.blend"
    assert av.library_relpath("a/b", None) == "em_cache/local/a_b.blend"


def test_the_assets_with_versions_are_read_off_the_summary():
    rows = [{"node_id": "rm", "asset_id": "podio", "level": "LOD0"},
            {"node_id": "rm", "asset_id": "podio", "level": "LOD1"},
            {"node_id": "rm2"}, {"node_id": "rm3", "asset_id": "tempio"}]
    assert av.versioned_assets(rows) == ["podio", "tempio"]


def test_the_sentences_say_what_was_downloaded():
    lines = av.sentences({"assets": 1, "here": 2, "missing": 0, "changed": 1,
                          "fetched": 1, "not_fetched": 0})
    assert lines[0].startswith("1 asset(s) with versions: 2 mesh(es)")
    assert lines[1] == "1 mesh(es) downloaded (0 missing, 1 changed)"


def test_the_package_is_named_by_its_digest_and_never_the_file_in_use():
    assert sp.package_name("/x/GreatTemple.blend", "ab" * 32) == \
        "GreatTemple-package-abababababab.blend"
    script = sp.pack_script("/tmp/out.blend")
    assert "pack_libraries" in script and "copy=True" in script
