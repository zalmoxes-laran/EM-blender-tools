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

import pytest

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


# ── D1 (E.D., 4 Oct 2026) · the measures of a version, taken when it is born ──

def test_d1_measures_in_the_form_of_the_formula():
    """Demetrescu et al. 2026, Table 1, Gardens: 864 m², 53 atlases 4096², UV
    0.6 → 1.27 mm per texel side (the table's value)."""
    m = av.version_measures(tris=1_776_384, area_m2=864.0, texture_count=53,
                            texture_side_px=4096, uv_fraction=0.6, lod0_tris=3_552_768)
    assert m["texel_density_dd"] == pytest.approx(1.273, abs=0.001)
    assert m["tris_per_m2"] == pytest.approx(2056.0, abs=0.01)
    assert m["texture_count"] == 53 and m["texture_side_px"] == 4096 and m["uv_ratio"] == 0.6
    assert m["reduction_from_lod0"] == 0.5


def test_d1_what_cannot_be_measured_is_left_out_not_zero():
    m = av.version_measures(tris=1000, area_m2=0.0)
    assert m == {}
    m = av.version_measures(tris=1000, area_m2=10.0)
    assert m == {"tris_per_m2": 100.0}


def test_d1_the_uses_are_the_library_s():
    from s3dgraphy.resources.versions import USES
    assert tuple(k for k, _l, _t in av.USES) == USES


def test_the_master_comes_first_and_lod_steps_both_ways():
    """Q1 · measured on Templu Mare: «master» sorted after lod0, so «LOD ▸» on
    the master stayed put and «◂ LOD» went to the version."""
    levels = ["lod1", "master", "lod0"]
    assert sorted(levels, key=av.level_key) == ["master", "lod0", "lod1"]
    assert av.step_level(levels, "master", +1) == "lod0"
    assert av.step_level(levels, "lod0", -1) == "master"
    assert av.step_level(levels, "lod1", -1) == "lod0"


# ── U1 · one change of level for RM Manager, Anastylosis and the versions ────
#
# Measured on Templu Mare (4 Oct 2026): the tiles show `ME_EST_fr_LOD2` with
# LOD0…LOD2 beside it in `RB/TempluMare_2021.blend`, the RMSF fragments
# `ME_TM038_LOD3` with LOD0…LOD3 in `TM038_semented.blend`. Two codes of their
# own walked them; the versions' one does now.

def test_a_lod_name_is_split_into_base_and_number():
    assert av.split_lod_name("ME_EST_fr_LOD2") == ("ME_EST_fr", 2)
    assert av.split_lod_name("ME_TM038_LOD3") == ("ME_TM038", 3)
    assert av.split_lod_name("TM026_2015") == (None, None)
    assert av.split_lod_name("ME_PODIO@LOD1") == (None, None)
    assert av.split_lod_name(None) == (None, None)


def test_named_levels_step_like_the_versions():
    levels = ["LOD0", "LOD1", "LOD2", "LOD3"]
    assert av.step_level(levels, "LOD3", -1) == "LOD2"
    assert av.step_level(levels, "LOD3", +1) == "LOD3"
    assert av.step_level(levels, "LOD0", -1) == "LOD0"


def test_a_level_asked_and_missing_falls_back_to_the_nearest_heavier():
    assert av.resolve_level(["LOD0", "LOD1", "LOD2"], "LOD2") == ("LOD2", False)
    assert av.resolve_level(["LOD0", "LOD1", "LOD2"], "LOD4") == ("LOD2", True)
    assert av.resolve_level(["LOD2", "LOD3"], "LOD0") == ("LOD2", True)
    assert av.resolve_level(["master", "LOD1"], "master") == ("master", False)
    assert av.resolve_level(["master"], "LOD1") == (None, False)
    assert av.resolve_level([], "LOD1") == (None, False)


def test_the_list_column_reads_the_number_of_a_level():
    assert av.level_number("LOD3") == 3
    assert av.level_number("master") == 0
    assert av.level_number(None) == 0


def test_the_same_sentences_from_every_panel():
    assert av.said_moves([], []) == [("INFO", "already at the end")]
    said = av.said_moves(["ME_TM038_LOD3 → LOD2"], ["no LOD4 for ME_X: LOD2 shown"])
    assert said == [("WARNING", "no LOD4 for ME_X: LOD2 shown"), ("INFO", "ME_TM038_LOD3 → LOD2")]
    many = av.said_moves([f"o{i} → LOD1" for i in range(9)], [])
    assert many[0][1].endswith("(and 3 more)")


def test_U1_prepare_for_a_use_records_what_changed_with_its_numbers():
    """«Prepare for a use…»: the step's technique says what changed (the
    geometry, else the textures, else only the encoding), with its numbers."""
    assert av.resized_side(4096, 2048) == 2048
    assert av.resized_side(1024, 2048) == 1024
    assert av.resized_side(4096, 0) == 4096
    step = av.prepare_step(ratio=0.25, max_side=2048, draco=True, resized=2,
                           size_bytes=123456)
    assert step["technique"] == "decimation"
    assert step["parameters"] == {"ratio": 0.25, "max_texture_px": 2048,
                                  "textures_resized": 2, "draco": True,
                                  "size_bytes": 123456,
                                  "tool": "EM Tools · Prepare for a use"}
    assert av.prepare_step(ratio=1.0, max_side=1024, draco=True, resized=1,
                           size_bytes=1)["technique"] == "texture_reduction"
    assert av.prepare_step(ratio=1.0, max_side=0, draco=True, resized=0,
                           size_bytes=1)["technique"] == "compression"
