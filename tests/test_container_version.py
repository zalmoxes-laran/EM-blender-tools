"""MICRO-VERSIONE-CONTENITORE (E.D., 30 Oct 2026) · a version of a whole RM
container written by «Prepare for a use».

Measured on E.D.'s ``TempluMare_v6_optimized.em.json``: «Reconstruction II AC
lod1 for Mobile webXR» had ``data.represents: container`` and
``data.container: rmgroup_Reconstruction_II_AC`` but NO edge to the container,
and an absolute ``url`` (``/Users/…/SB/versions/…``) where the other versions
are relative to the em.json (``../RB/versions/…``): EMStudio did not find it.

Here a real s3Dgraphy graph of that shape: the container hats its version
(``has_linked_resource``, connections 1.6.41), the url becomes relative, both
when the version is registered and when an old file is read; the level of the
dialog and of the file are one function of the choices."""

import importlib.util
import json
import os
import pathlib
import sys
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))
pytest.importorskip("s3dgraphy.nodes.group_node")

from s3dgraphy.exporter.emjson_exporter import build_emjson  # noqa: E402
from s3dgraphy.importer.emjson_importer import import_emjson  # noqa: E402


def _load(pkgname, folder, name):
    if pkgname not in sys.modules:
        pkg = types.ModuleType(pkgname)
        pkg.__path__ = [str(folder)]
        sys.modules[pkgname] = pkg
    spec = importlib.util.spec_from_file_location(f"{pkgname}.{name}", folder / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pd = _load("_cv_pkg", _REPO / "sync_manager", "prepare_diagnosis")

GID = "rmgroup_Reconstruction_II_AC"
RID = "fea517cc-f737-5387-8d6e-334a322c369c"


def _project(tmp_path, *, edge=False, url=None):
    """The project's tree (EM/, SB/versions/) and an em.json of the measured shape."""
    (tmp_path / "EM").mkdir()
    (tmp_path / "SB" / "versions").mkdir(parents=True)
    glb = tmp_path / "SB" / "versions" / "Reconstruction_II_AC@lod1-mobile.glb"
    glb.write_bytes(b"glTF")
    nodes = [
        {"id": GID, "name": "Reconstruction II AC", "node_type": "RepresentationModelNodeGroup"},
        {"id": "Column_light1_model", "name": "Column_light1", "node_type": "representation_model"},
        {"id": RID, "name": "Reconstruction II AC lod1 for Mobile webXR", "node_type": "resource",
         "data": {"url": url if url is not None else str(glb), "url_type": "3d_model",
                  "tier": "distribution", "represents": "container", "container": GID,
                  "level": "lod1", "profile": "mobile_webxr", "purpose": "mobile",
                  "use": ["mobile_ar"], "size_bytes": 2535856, "primitives": {"triangles": 595058}}},
        {"id": "other", "name": "a surveyed mesh lod3", "node_type": "resource",
         "data": {"url": "/elsewhere/SM_OB_EST_L@lod3.glb", "url_type": "3d_model"}},
    ]
    edges = [{"edge_type": "is_in_representation_model_group", "id": "m_in_g",
              "source": "Column_light1_model", "target": GID}]
    if edge:
        edges.append({"edge_type": "has_linked_resource", "id": f"{GID}_has_linked_resource_{RID}",
                      "source": GID, "target": RID})
    doc = build_emjson(import_emjson_doc({"nodes": nodes, "edges": edges}))
    p = tmp_path / "EM" / "TempluMare_v6_optimized.em.json"
    p.write_text(json.dumps(doc))
    return p, glb


def import_emjson_doc(g):
    """an em.json of these nodes and edges, through s3Dgraphy's own writer"""
    from s3dgraphy.graph import Graph
    from s3dgraphy.importer.emjson_importer import parse_emjson
    shell = build_emjson(Graph(graph_id="temple", name="Temple"))
    shell["graph"].update(nodes=g["nodes"], edges=g["edges"])
    graph, _w = parse_emjson(shell)
    return graph


def _hats(graph):
    return [(e.edge_source, e.edge_target) for e in graph.edges if e.edge_type == "has_linked_resource"]


def test_PRIMA_the_measured_shape_has_no_edge_and_an_absolute_url(tmp_path):
    p, glb = _project(tmp_path)
    g, _w = import_emjson(str(p))
    assert _hats(g) == []
    assert g.find_node_by_id(RID).data["url"] == str(glb)


def test_the_datamodel_lets_a_container_hat_a_resource():
    cfg = json.loads((_CHECKOUT / "s3dgraphy" / "JSON_config" / "s3Dgraphy_connections_datamodel.json").read_text())
    allowed = cfg["edge_types"]["has_linked_resource"]["allowed_connections"]
    assert "RepresentationModelNodeGroup" in allowed["source"] and "ResourceNode" in allowed["target"]


def test_read_mends_the_edge_and_the_url_in_memory(tmp_path):
    p, _glb = _project(tmp_path)
    g, _w = import_emjson(str(p))
    r = pd.repair_container_versions(g, str(p.parent), str(tmp_path))
    assert r == {"linked": [RID], "relative": [RID]}
    assert _hats(g) == [(GID, RID)]
    assert g.find_node_by_id(RID).data["url"] == "../SB/versions/Reconstruction_II_AC@lod1-mobile.glb"
    # a url outside the project, and a resource «Prepare for a use» did not write, stay
    assert g.find_node_by_id("other").data["url"] == "/elsewhere/SM_OB_EST_L@lod3.glb"
    # …the file is not touched until it is saved
    assert str(tmp_path) in p.read_text()
    # saved, the edge and the relative url are in the em.json
    doc = build_emjson(g)
    edges = {(e["source"], e["target"], e["edge_type"]) for e in doc["graph"]["edges"]}
    assert (GID, RID, "has_linked_resource") in edges
    node = next(n for n in doc["graph"]["nodes"] if n["id"] == RID)
    assert node["data"]["url"] == "../SB/versions/Reconstruction_II_AC@lod1-mobile.glb"


def test_read_twice_changes_nothing_more(tmp_path):
    p, _glb = _project(tmp_path, edge=True, url="../SB/versions/Reconstruction_II_AC@lod1-mobile.glb")
    g, _w = import_emjson(str(p))
    assert pd.repair_container_versions(g, str(p.parent), str(tmp_path)) == {"linked": [], "relative": []}
    assert _hats(g) == [(GID, RID)]


def test_a_url_outside_the_project_stays_absolute(tmp_path):
    p, _glb = _project(tmp_path, url="/Volumes/other/Reconstruction_II_AC@lod1-mobile.glb")
    g, _w = import_emjson(str(p))
    r = pd.repair_container_versions(g, str(p.parent), str(tmp_path))
    assert r["relative"] == [] and r["linked"] == [RID]


def test_no_container_node_no_edge(tmp_path):
    p, _glb = _project(tmp_path)
    g, _w = import_emjson(str(p))
    g.remove_node(GID)
    assert pd.link_to_container(g, RID, GID) is False
    # and not to a node that is not a container
    assert pd.link_to_container(g, RID, "Column_light1_model") is False


def test_relative_locator_is_the_registration_rule(tmp_path):
    emdir = tmp_path / "EM"
    f = tmp_path / "SB" / "versions" / "x@lod0-mobile.glb"
    assert pd.relative_locator(str(f), str(emdir)) == "../SB/versions/x@lod0-mobile.glb"
    assert pd.relative_locator(str(f), "") == str(f)                       # no em.json: as it is
    assert pd.relative_locator("../SB/x.glb", str(emdir)) == "../SB/x.glb"  # already relative
    assert pd.relative_locator(str(f), str(emdir), root=str(emdir)) == str(f)  # outside the root


def test_opening_the_file_mends_it(tmp_path, monkeypatch):
    """The door EM Tools opens an em.json by (``emjson_support``): the mended
    graph and a line that says it."""
    pkg = types.ModuleType("_cv_root")
    pkg.__path__ = [str(_REPO)]
    sys.modules["_cv_root"] = pkg
    sm = types.ModuleType("_cv_root.sync_manager")
    sm.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_cv_root.sync_manager"] = sm
    sys.modules["_cv_root.sync_manager.prepare_diagnosis"] = pd
    es = _load("_cv_root", _REPO, "emjson_support")
    p, _glb = _project(tmp_path)
    from s3dgraphy.multigraph.multigraph import multi_graph_manager
    before = dict(multi_graph_manager.graphs)
    try:
        container, warnings = es.import_container_from_emjson(str(p), replace=True)
        g = container.graphs["temple"]
        assert _hats(g) == [(GID, RID)]
        assert g.find_node_by_id(RID).data["url"] == "../SB/versions/Reconstruction_II_AC@lod1-mobile.glb"
        assert any("container version(s) linked" in w for w in warnings)
    finally:
        multi_graph_manager.graphs.clear()
        multi_graph_manager.graphs.update(before)


def test_the_level_is_the_choices_one():
    assert pd.level_of({"decimated": {"geo": 12000}}) == "lod1"
    assert pd.level_of({"decimated": {}}) == "lod0"
    assert pd.level_of({}) == "lod0"
