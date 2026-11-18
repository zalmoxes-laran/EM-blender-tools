"""MICRO-PL12 (row W9 of the extensions plan, E.D. 18 Nov 2026): the community
packages in EM Tools, measured without Blender — ``community_packages/core.py``
and ``i18n.py`` (no bpy), on em-profiles' examples (invented, D-5) installed in
/tmp machine folders.

The machine folders are the ones EMStudio reads (``~/.s3dgraphy``); here they
are redirected (``S3DGRAPHY_*_DIR``, ``EM_VOCABULARIES_DIR``) and the real ones
are never written.
"""
import importlib.util
import json
import pathlib
import shutil
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
EXAMPLES = _REPO.parent / "em-profiles" / "examples"

pytest.importorskip("s3dgraphy.profiles")
pytest.importorskip("s3dgraphy.extensions")
pytest.importorskip("s3dgraphy.annotation.combiners")


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod          # dataclasses look their module up
    spec.loader.exec_module(mod)
    return mod


C = _load("pl12_core", "community_packages/core.py")
I18N = _load("pl12_i18n", "community_packages/i18n.py")
RV = _load("pl12_readings", "readings_view/core.py")

need_examples = pytest.mark.skipif(not (EXAMPLES / "esempio-statuaria").is_dir(),
                                   reason="em-profiles' examples are not beside EM-blender-tools")

STAT = "https://w3id.org/extendedmatrix/profile/esempio-statuaria"
FASE = f"{STAT}/vocab/fase-superficie/"


@pytest.fixture
def machine(tmp_path, monkeypatch):
    for env, sub in (("S3DGRAPHY_PROFILES_DIR", "profiles"), ("S3DGRAPHY_EXTENSIONS_DIR", "extensions"),
                     ("S3DGRAPHY_PLUGINS_DIR", "plugins"), ("EM_VOCABULARIES_DIR", "vocab")):
        monkeypatch.setenv(env, str(tmp_path / sub))
    from s3dgraphy.authorities import packages as pk
    pk._changed()
    C.forget_cache()
    yield tmp_path
    pk._changed()
    C.forget_cache()


def _copy(tmp_path, name):
    dst = tmp_path / "src" / name
    shutil.copytree(EXAMPLES / name, dst)
    return dst


# ── the sentences ───────────────────────────────────────────────────────────

def test_every_sentence_has_its_italian():
    missing = [m for m, by in I18N.MESSAGES.items() if not by.get("it_IT")]
    assert missing == []


def test_templates_keep_their_placeholders_in_italian():
    import re
    for msgid, by in I18N.MESSAGES.items():
        want = sorted(re.findall(r"\{(\w+)\}", msgid))
        assert sorted(re.findall(r"\{(\w+)\}", by["it_IT"])) == want, msgid


def test_a_composed_sentence_is_recomposed_in_italian():
    it = I18N.catalogue("it_IT")
    text = "This file uses packages not installed here: esempio-statuaria 0.1.0"
    assert I18N.translate(text, it) == "Questo file usa pacchetti non installati qui: esempio-statuaria 0.1.0"
    assert I18N.translate("Remove", it) == "Rimuovi"
    assert I18N.translate("nobody knows me", it) == "nobody knows me"


def test_operator_sentences_are_in_the_catalogue():
    for s in I18N.AUTO:
        assert s in I18N.MESSAGES, s


# ── installing from disk ────────────────────────────────────────────────────

@need_examples
def test_a_mixed_package_installs_its_data_and_leaves_the_code_out(machine):
    src = _copy(machine, "esempio-statuaria-misto")
    pv = C.library()[1].preview(str(src))
    plan = C.plan_install(pv)
    assert plan == {"action": "data", "code_left_out": True}
    lines = [t for t, _i, _l in C.preview_lines(pv, "en")]
    assert any(t.startswith("Data 0.1.0") for t in lines)
    assert any("tier A" in t for t in lines)
    assert any("NOT VERIFIED" in t for t in lines)
    assert any("EM Tools installs the data only" in t for t in lines)
    # every permission with its why (D-14)
    assert any("«" in t and "—" in t for t in lines)
    C.install_data(str(src))
    rows = {r.id: r for r in C.package_rows()}
    row = rows["esempio-statuaria"]
    assert row.data == "installed" and row.code == "not_installed"
    assert "solo i dati" in C.problem_text(row.code_reason, "it")
    # nothing of the code reached the machine
    assert not list((machine / "plugins").rglob("*.py"))


@need_examples
def test_the_confirmation_in_italian(machine):
    src = _copy(machine, "esempio-statuaria-misto")
    pv = C.library()[1].preview(str(src))
    it = I18N.catalogue("it_IT")
    lines = [t for t, _i, _l in C.preview_lines(pv, "it", lambda s: I18N.translate(s, it))]
    assert any(t.startswith("Dati 0.1.0: nessun codice") for t in lines)
    assert any("fascia A" in t for t in lines)
    assert any("NON VERIFICATO" in t for t in lines)


@need_examples
def test_a_plugin_alone_is_refused_and_nothing_is_written(machine):
    src = _copy(machine, "facemesh_fit")
    pv = C.library()[1].preview(str(src))
    assert C.plan_install(pv)["action"] == "refuse"
    with pytest.raises(ValueError):
        C.install_data(str(src))
    assert C.package_rows() == []


@need_examples
def test_remove_leaves_the_vocabularies(machine):
    from s3dgraphy.authorities import packages as pk
    C.install_data(str(_copy(machine, "esempio-statuaria")))
    assert len(C.vocabularies_only_here("esempio-statuaria")) == 3
    C.remove_package("esempio-statuaria")
    assert C.package_rows() == []
    pk._changed()
    assert pk.find_installed(FASE), "D-19: the vocabularies stay"


# ── the overlay of a file ───────────────────────────────────────────────────

@need_examples
def test_the_overlay_is_the_declared_plus_the_installed(machine):
    C.install_data(str(_copy(machine, "esempio-statuaria")))
    ov, missing, _probs, declared = C.active_overlay([])
    assert [p.name for p in ov] == ["esempio-statuaria"] and declared == set()
    ov, missing, _probs, declared = C.active_overlay(
        [{"iri": "https://w3id.org/extendedmatrix/profile/ritratti-romani", "version": "0.2.0"}])
    assert C.missing_line(missing) == "ritratti-romani 0.2.0"
    assert [p.name for p in ov] == ["esempio-statuaria"]


@need_examples
def test_saving_declares_a_package_the_content_uses(machine):
    """The importer puts the active overlay in the container: saving declares
    the package of a prefix the content uses (profiles.declare)."""
    from s3dgraphy.container import Container, save_container_file
    from s3dgraphy.graph import Graph
    from s3dgraphy.nodes.property_node import PropertyNode
    C.install_data(str(_copy(machine, "esempio-statuaria")))
    g = Graph("G1")
    g.add_node(PropertyNode(node_id="p1", name="Fase della superficie", property_type="stat:fase_di_superficie",
                            value="originale"))
    ov = C.active_overlay([])[0]
    cont = Container(graphs={"G1": g}, active_graph_id="G1", profiles=ov)
    out = machine / "x.em.json"
    save_container_file(cont, str(out))
    doc = json.loads(out.read_text())
    assert [p["iri"] for p in doc["header"]["profiles"]] == [STAT]


# ── colour schemes and vocabularies ─────────────────────────────────────────

@need_examples
def test_a_package_scheme_becomes_an_emc_keyed_by_the_terms(machine):
    C.install_data(str(_copy(machine, "esempio-statuaria")))
    ov = C.active_overlay([])[0]
    (s,) = C.package_schemes(ov, "it")
    assert s["property"] == "stat:fase_di_superficie" and s["name"] == "Fasi della superficie"
    emc = s["emc"]
    codes = emc["metadata"]["value_codes"]
    assert set(codes.values()) == {FASE + "originale", FASE + "rilavorazione", FASE + "integrazione"}
    # the labels from the vocabulary installed with the package, linear colours
    for label, colour in emc["color_mapping"].items():
        assert "://" not in label and len(colour) == 4 and all(0 <= c <= 1 for c in colour)
    # file_schemes colours a value by its CODE, whatever its label says
    FS = _load("pl12_fs", "visual_manager/file_schemes.py")
    rows = dict(FS.rows_for(emc, {"testo libero": FASE + "integrazione"}))
    lab = next(k for k, v in codes.items() if v == FASE + "integrazione")
    assert rows["testo libero"] == tuple(emc["color_mapping"][lab])


def test_an_emc_in_em_tools_form_is_taken_as_it_is():
    doc = {"metadata": {"property_name": "material"}, "color_mapping": {"stone": [0.1, 0.2, 0.3, 1.0]}}
    assert C.package_scheme_as_emc(doc, "x", "en") == doc
    assert C.package_scheme_as_emc({"color_mapping": {"a": "not a colour"}}, "p", "en") is None


@need_examples
def test_the_property_is_found_by_type_label_or_id(machine):
    from s3dgraphy.graph import Graph
    from s3dgraphy.nodes.property_node import PropertyNode
    C.install_data(str(_copy(machine, "esempio-statuaria")))
    ov = C.active_overlay([])[0]
    g = Graph("G")
    g.add_node(PropertyNode(node_id="a", name="Fase della superficie", property_type="stat:fase_di_superficie",
                            value="x"))
    g.add_node(PropertyNode(node_id="b", name="Fase della superficie", value="y"))
    g.add_node(PropertyNode(node_id="c", name="stat:fase_di_superficie", value="z"))
    g.add_node(PropertyNode(node_id="d", name="Material", value="w"))
    assert C.property_names(g, "stat:fase_di_superficie", ov) == ["Fase della superficie",
                                                                   "stat:fase_di_superficie"]


@need_examples
def test_the_vocabularies_of_the_packages(machine):
    C.install_data(str(_copy(machine, "esempio-statuaria")))
    ov = C.active_overlay([])[0]
    vs = {v["property"]: v for v in C.package_vocabularies(ov, "it")}
    assert vs["stat:fase_di_superficie"]["installed"] and vs["stat:fase_di_superficie"]["concepts"] == 3
    assert vs["stat:lavorazione"]["label"] == "Lavorazione"


# ── the chain, read (G14) ───────────────────────────────────────────────────

def _graph_with_places(ov):
    from s3dgraphy.annotation.extractors import place_extractor, place_landmark, start_landmark_pose
    from s3dgraphy.graph import Graph
    from s3dgraphy.nodes.extractor_node import ExtractorNode
    from s3dgraphy.nodes.representation_node import RepresentationModelNode
    g = Graph("G")
    g.add_node(RepresentationModelNode("rm1", "Testa_RM"))
    pose = start_landmark_pose(g, ov, "stat:volto", "rm1")
    pts = {"nasion": [0.0, 1.5, 0.1], "gnathion": [0.0, 1.38, 0.11],
           "exocanthion_r": [-0.05, 1.49, 0.09], "exocanthion_l": [0.05, 1.49, 0.09]}
    for pid, p in pts.items():
        place_landmark(g, ov, "stat:volto", pid, "rm1", p, pose_id=pose, lang="it")
    place_extractor(g, ov, "stat:superficie_integrata", "rm1",
                    [[0, 1, 0], [0.1, 1, 0], [0.1, 1.1, 0], [0, 1.1, 0]])
    # EM Tools' own form of a measured point (Proxy Box)
    ex = ExtractorNode("pb1", "D.1.1")
    ex.attributes.update({"x": 1.0, "y": 2.0, "z": 3.0, "point_type": "Quota Min"})
    g.add_node(ex)
    return g, pts


@need_examples
def test_the_two_forms_of_a_measured_point_are_read(machine):
    C.install_data(str(_copy(machine, "esempio-statuaria")))
    ov = C.active_overlay([])[0]
    g, pts = _graph_with_places(ov)
    points = C.measured_points(g, ov, "it")
    chain = [p for p in points if p.source == "chain"]
    assert len(chain) == 4 and all(p.on_id == "rm1" for p in chain)
    nasion = next(p for p in chain if p.landmark.get("point") == "nasion")
    assert nasion.label == "nasion" or nasion.label  # the label the person saw
    # Y-up → Z-up: (x, y, z) → (x, -z, y)
    assert nasion.blender[0] == pytest.approx((0.0, -0.1, 1.5))
    attr = [p for p in points if p.source == "attributes"]
    assert len(attr) == 1 and attr[0].blender[0] == (1.0, 2.0, 3.0) and "Quota Min" in attr[0].label
    assert C.position_of(g, nasion.extractor_id) == (pytest.approx((0.0, -0.1, 1.5)), "chain")
    assert C.position_of(g, "pb1") == ((1.0, 2.0, 3.0), "attributes")


@need_examples
def test_a_surface_is_read_as_a_ring_for_the_areale(machine):
    C.install_data(str(_copy(machine, "esempio-statuaria")))
    ov = C.active_overlay([])[0]
    g, _ = _graph_with_places(ov)
    (s,) = C.surfaces(g, ov, "en")
    assert s.kind == "surface" and len(s.blender) == 4 and s.on_id == "rm1"
    assert s.area == pytest.approx(0.01) and "Infill surface" in s.label
    assert C.ring_problem(s.blender) is None
    assert C.ring_problem([(0, 0, 0), (1, 0, 0), (2, 0, 0)]) == "all the vertices on one line"
    assert C.ring_problem([(0, 0, 0), (0, 0, 0), (1, 0, 0)]) == "fewer than three distinct vertices"


@need_examples
def test_the_measures_of_the_packages_are_computed_once(machine):
    C.install_data(str(_copy(machine, "esempio-statuaria")))
    ov = C.active_overlay([])[0]
    g, pts = _graph_with_places(ov)
    assert C.measure_targets(g) == [("rm1", None)]
    done, waiting = C.compute_measures(g, ov)
    assert (done, waiting) == (3, 0)        # two distances, then the ratio
    n_nodes = len(g.nodes)
    assert C.compute_measures(g, ov) == (3, 0) and len(g.nodes) == n_nodes   # idempotent


# ── the readings show the surface ───────────────────────────────────────────

@need_examples
def test_the_readings_show_and_bring_back_a_surface(machine):
    C.install_data(str(_copy(machine, "esempio-statuaria")))
    ov = C.active_overlay([])[0]
    g, _ = _graph_with_places(ov)
    plan = RV.plan_readings(g)
    kinds = sorted(r.kind for r in plan.shown)
    assert kinds == ["point"] * 4 + ["surface"]
    surf = next(r for r in plan.shown if r.kind == "surface")
    res = RV.apply_back(g, surf.region_id, {"geometry_kind": "surface",
                                            "coords": [[0, 1, 0], [0.2, 1, 0], [0.2, 1.1, 0], [0, 1.1, 0]]})
    assert res["written"] and res["area_after"] == pytest.approx(0.02)
    node = g.find_node_by_id(surf.region_id)
    assert node.data["area"] == pytest.approx(0.02) and node.data["perimeter"] == pytest.approx(0.6)
