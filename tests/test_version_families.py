"""MICRO salva (17 Oct 2026) · the author's levels and the recipe's derived
versions, apart (bpy-free)."""

import os
import pathlib
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))
pytest.importorskip("s3dgraphy.resources.versions")

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.resources.files import add_resource  # noqa: E402
from s3dgraphy.resources.versions import add_version, version_info  # noqa: E402

import version_families as vf  # noqa: E402
import version_recipe  # noqa: E402

RECIPE = {"tool": version_recipe.RECIPE_TOOL}


def _file(name, n):
    return [{"url": f"../RB/{name}", "checksum": "sha256:" + f"{n:064x}"}]


def _survey():
    """The survey of Templu Mare as v3.2 writes it: the author's LOD0-2 (steps
    of Blender), the recipe's lod3 (compression of LOD2) and lod4 (decimation)."""
    g = Graph(graph_id="g")
    m = add_resource(g, name="OB_EST_L (surveyed mesh)", kind="model",
                     files=_file("TempluMare_2021.blend", 1), tier="master").node_id
    lods = []
    for i, tech in enumerate(("OBJ export of the LOD0 mesh, Blender 5.2 (E.D., 30 Sep 2026)",
                              "decimation and texture baking, OBJ export, Blender 2.92 (2021)",
                              "decimation and texture baking, OBJ export, Blender 2.92 (2021)")):
        lods.append(add_version(g, m, level=f"lod{i}", use=["analysis"],
                                files=_file(f"LOD{i}/OB_EST_L_LOD{i}.obj", 10 + i),
                                technique=tech, tool="Blender",
                                parameters={"level": f"lod{i}"})["version_id"])
    add_version(g, m, level="lod3", use=["aton", "heriverse"],
                files=_file("versions/SM_OB_EST_L_LOD1@lod3-aton-heriverse.glb", 20),
                technique="compression", tool="EM Tools",
                parameters=dict(RECIPE, level="lod3", ratio=1))
    add_version(g, m, level="lod4", use=["web"],
                files=_file("versions/SM_OB_EST_L_LOD1@lod4-web.glb", 21),
                technique="decimation", tool="EM Tools",
                parameters=dict(RECIPE, level="lod4", ratio=0.5))
    return g, m


def _reconstruction():
    """A reconstruction of Templu Mare: the .blend object, and the recipe's
    lod0 (the whole model) and lod1 (a decimation) — no level of the author."""
    g = Graph(graph_id="g")
    m = add_resource(g, name="Column_entrance1 (reconstruction)", kind="model",
                     files=_file("GreatTemple_2026.blend", 2), tier="master").node_id
    add_version(g, m, level="lod0", use=["aton", "heriverse"],
                files=_file("versions/Column_entrance1@lod0.glb", 30),
                technique="compression", tool="EM Tools",
                parameters=dict(RECIPE, level="lod0", ratio=1))
    add_version(g, m, level="lod1", use=["web", "realtime"],
                files=_file("versions/Column_entrance1@lod1.glb", 31),
                technique="decimation", tool="EM Tools",
                parameters=dict(RECIPE, level="lod1", ratio=0.5))
    return g, m


def test_the_sign_is_the_recipe_s_tool_not_the_kind_of_step():
    assert vf.is_derived({"dtc_kind": "lod_generation", "parameters": RECIPE})
    assert not vf.is_derived({"dtc_kind": "lod_generation",
                              "parameters": {"level": "lod1"}}), "the author's LOD1"
    assert not vf.is_derived(None) and not vf.is_derived({"parameters": "x"})
    assert version_recipe.step_parameters({}, applied={})["tool"] == version_recipe.RECIPE_TOOL


def test_the_survey_author_levels_and_derived_versions_apart():
    g, m = _survey()
    fam = vf.families(g, m)
    assert [e["level"] for e in fam["author"]] == ["lod0", "lod1", "lod2"]
    assert [e["level"] for e in fam["derived"]] == ["lod3", "lod4"]
    assert fam["whole"] is False
    said = [(k, t) for k, t, _ in vf.lines(g, m)]
    assert said == [
        ("head", "Author's levels"),
        ("author", "LOD0 · analysis"),
        ("author", "LOD1 · analysis"),
        ("author", "LOD2 · analysis"),
        ("head", "Derived versions (the recipe's)"),
        ("derived", "Derived version · aton, heriverse · compression"),
        ("derived", "Derived version · web · decimated to 0.50"),
    ]


def test_a_reconstruction_without_levels_is_whole():
    g, m = _reconstruction()
    fam = vf.families(g, m)
    assert fam["whole"] and not fam["author"] and len(fam["derived"]) == 2
    said = [t for _k, t, _ in vf.lines(g, m)]
    assert said[:2] == ["Author's levels", vf.WHOLE]
    assert "LOD1" not in " ".join(said), "the recipe's lod1 is not a level"
    assert said[-1] == "Derived version · web, realtime · decimated to 0.50"


def test_the_shown_version_is_said_derived_and_nothing_is_rewritten():
    g, m = _reconstruction()
    before = {n.node_id: dict(n.data or {}) for n in g.nodes}
    lod1 = vf.families(g, m)["derived"][-1]["id"]
    assert vf.is_derived_info(g, version_info(g, lod1))
    assert not vf.is_derived_info(g, version_info(g, m)), "the master"
    assert {n.node_id: dict(n.data or {}) for n in g.nodes} == before, "read only"
    gs, ms = _survey()
    lod1s = vf.families(gs, ms)["author"][1]["id"]
    assert not vf.is_derived_info(gs, version_info(gs, lod1s))


_V32 = os.environ.get("EM_V32", "/tmp/salva17/proj/EM/TempluMare_v3.2.em.json")


@pytest.mark.skipif(not os.path.isfile(_V32), reason="the copy of Templu Mare v3.2 is not here")
def test_templu_mare_v32():
    from s3dgraphy.container import load_container_file
    c, _w = load_container_file(_V32)
    g = c.graphs["6af9866e-96a9-5c99-a6b1-78524ae2e2c2"]
    survey = vf.families(g, "templu-mare.rb.EST_L.master")
    assert [e["lod_level"] for e in survey["author"]] == ["lod0", "lod1", "lod2"]
    assert [e["lod_level"] for e in survey["derived"]] == ["lod3", "lod4"]
    recon = vf.families(g, "templu-mare.sb.Column_entrance1.master")
    assert recon["whole"] and [e["lod_level"] for e in recon["derived"]] == ["lod0", "lod1"]
    # every recipe step of the dataset, none of the author's
    steps = [n for n in g.nodes if n.node_type == "dtc_process"
             and (n.data or {}).get("dtc_kind") == "lod_generation"]
    assert sum(vf.is_derived(n.data) for n in steps) == 196 and len(steps) == 230
