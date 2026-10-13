"""MICRO il proxy arriva come proprietà (13 Oct 2026), measured without bpy.

Measured in the room `tavolo-2026-10-12`: the proxy of US3 published from
Blender arrived as ``US3 ─has_linked_resource→ 'US3.model'``, a convention only
EMtools knew, and EMStudio's Space counted «0 of 31 units alive». The promotion
now writes the canonical chain (`test_room_promote.py`); here:

* a room an older EMtools filled is MIGRATED — the ``<US>.model`` becomes the
  chain's ``proxy_model`` resource with the same bytes, the genesis names it,
  the unit stops citing the old one — once, with stable ids;
* the migration reaches the room as operations (`scene_sync.section_delta_ops`);
* `residence.is_proxy_resource` reads the canonical chain, and still the old.
"""

import importlib.util
import pathlib
import sys
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir():
    sys.path.insert(0, str(_S3D))

pytest.importorskip("s3dgraphy.geometry.proxy")

from s3dgraphy.exporter.emjson_exporter import build_emjson  # noqa: E402
from s3dgraphy.geometry.proxy import proxy_resource_id  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402
from s3dgraphy.publication import promote_resource  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_sync(name):
    pkg = types.ModuleType("_pp")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_pp"] = pkg
    return _load(f"_pp.{name}", f"sync_manager/{name}.py")


PC = _load("_pp_proxy_chain", "proxy_chain.py")
RES = _load_sync("residence")
SYNC = _load_sync("scene_sync")

DIGEST = "sha256:" + "3c" * 32
URL = f"https://em.localhost:8443/v1/rooms/tavolo/assets/{DIGEST}"


def _room_as_measured():
    """US3 with the `US3.model` an EMtools 1.6.0-dev.14 published: resident,
    3d_model, distribution, its dtc_process — and no proxy chain."""
    g = Graph("tavolo-2026-10-12")
    g.add_node(StratigraphicUnit("US3", name="US3"))
    g.add_node(StratigraphicUnit("US4", name="US4"))
    promote_resource(g, "US3.model", url=URL, sha256=DIGEST,
                     media_type="model/gltf-binary", link_to="US3",
                     name="US3 (glTF)", residency="resident")
    return g


def _triples(g):
    return {(e.edge_source, e.edge_type, e.edge_target) for e in g.edges}


def _chain(g, unit_id):
    props = [e.edge_target for e in g.edges
             if e.edge_source == unit_id and e.edge_type == "has_property"]
    shapes = [e.edge_target for e in g.edges
              if e.edge_source in props and e.edge_type == "has_semantic_shape"]
    res = [e.edge_target for e in g.edges
           if e.edge_source in shapes and e.edge_type == "has_linked_resource"]
    return props, shapes, res


def test_the_measured_room_has_the_old_form():
    g = _room_as_measured()
    assert [u for u, _n, _r in PC.legacy_unit_models(g)] == ["US3"]
    assert _chain(g, "US3") == ([], [], [])


def test_the_old_model_becomes_the_canonical_chain():
    g = _room_as_measured()
    report = PC.migrate_unit_models(g)
    props, shapes, res = _chain(g, "US3")
    assert len(props) == len(shapes) == len(res) == 1
    assert res[0] == proxy_resource_id(shapes[0])
    assert report["migrated"] == [{"unit_id": "US3", "old": "US3.model", "new": res[0]}]
    new = g.find_node_by_id(res[0])
    assert new.data["url"] == URL and new.data["checksum"] == DIGEST
    assert new.data["residency"] == "resident"
    assert new.data["url_type"] == "proxy_model"
    assert g.find_node_by_id(props[0]).property_type == "geometry"
    # the unit no longer cites the old resource, and the old one is out of
    # the live graph (13 Oct 2026: left alive, it came back into the scene)
    assert ("US3", "has_linked_resource", "US3.model") not in _triples(g)
    assert g.find_node_by_id("US3.model") is None
    assert report["closed"][0]["removed"] == ["US3.model"]
    # the genesis names the new one
    assert any(e.edge_type == "dtc_had_output" and e.edge_target == res[0]
               for e in g.edges)
    # a unit without the old form is not touched
    assert _chain(g, "US4") == ([], [], [])


def test_the_migration_runs_once_and_its_ids_are_stable():
    a, b = _room_as_measured(), _room_as_measured()
    PC.migrate_unit_models(a)
    PC.migrate_unit_models(b)
    assert sorted(_triples(a)) == sorted(_triples(b))
    before = sorted(_triples(a))
    again = PC.migrate_unit_models(a)
    assert again["migrated"] == [] and sorted(_triples(a)) == before
    assert PC.legacy_unit_models(a) == []


def test_a_revised_old_model_is_migrated_too():
    """«Sync the scene…» revised `US3.model` into a derived id and moved the
    unit's citation to it: the revision is the one the chain takes."""
    g = _room_as_measured()
    other = "sha256:" + "4d" * 32
    promote_resource(g, "US3.model.r2", url=URL.replace(DIGEST, other), sha256=other,
                     media_type="model/gltf-binary", residency="resident")
    g.add_edge("rev", "US3.model.r2", "US3.model", "was_revision_of")
    old = next(e for e in g.edges if e.edge_type == "has_linked_resource")
    g.remove_edge(old.edge_id)
    g.add_edge("cite", "US3", "US3.model.r2", "has_linked_resource")
    report = PC.migrate_unit_models(g)
    assert [m["old"] for m in report["migrated"]] == ["US3.model.r2"]
    _p, _s, res = _chain(g, "US3")
    assert g.find_node_by_id(res[0]).data["checksum"] == other


def test_a_chain_with_other_bytes_is_not_overwritten():
    g = _room_as_measured()
    chain = PC.ensure_unit_proxy(g, "US3", "US3")
    other = "sha256:" + "5e" * 32
    promote_resource(g, chain["resource_id"], url="https://x/" + other, sha256=other,
                     media_type="model/gltf-binary")
    report = PC.migrate_unit_models(g)
    assert report["migrated"] == [] and report["warnings"]
    assert ("US3", "has_linked_resource", "US3.model") in _triples(g)
    assert g.find_node_by_id(chain["resource_id"]).data["checksum"] == other


def test_the_migration_reaches_the_room_as_operations():
    g = _room_as_measured()
    before = build_emjson(g)["graph"]
    PC.migrate_unit_models(g)
    ops = SYNC.section_delta_ops(before, build_emjson(g)["graph"])
    kinds = [o["op"] for o in ops]
    assert kinds.count("add_node") == 3                 # property, shape, resource
    added = {o["edge_type"] for o in ops if o["op"] == "add_edge"}
    assert {"has_property", "has_semantic_shape", "has_linked_resource",
            "dtc_had_output"} <= added
    removed = [o for o in ops if o["op"] == "remove_edge"]
    assert {(o["edge_type"], o["target"]) for o in removed} == \
        {("has_linked_resource", "US3.model"), ("dtc_had_output", "US3.model")}
    # the old form closed: a tombstone, after its edges
    assert [o["id"] for o in ops if o["op"] == "remove_node"] == ["US3.model"]
    assert kinds[-1] == "remove_node"


def test_is_proxy_resource_reads_the_canonical_chain_and_the_old_form():
    g = _room_as_measured()
    assert RES.is_proxy_resource(g, "US3.model")            # the old form, still read
    PC.migrate_unit_models(g)
    _p, _s, res = _chain(g, "US3")
    assert RES.is_proxy_resource(g, res[0])
    assert RES.origin_of_resource(g, res[0])[0] == RES.ORIGIN_PROXY
    plain = Graph("plain")
    promote_resource(plain, "RM1.model", url=URL, sha256=DIGEST,
                     media_type="model/gltf-binary")
    assert not RES.is_proxy_resource(plain, "RM1.model")


def _room_session():
    root = types.ModuleType("_pp_root")
    root.__path__ = [str(_REPO)]
    sys.modules["_pp_root"] = root
    inner = types.ModuleType("_pp_root.sync_manager")
    inner.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_pp_root.sync_manager"] = inner
    return _load("_pp_root.sync_manager.room_session", "sync_manager/room_session.py")


def test_the_adopted_document_is_a_view_without_the_tombstones():
    """Measured at the second entry (13 Oct 2026): the migration's three
    `US ─has_linked_resource→ <US>.model`, tombstoned in the room, were alive
    again in Blender — the importer does not read tombstones."""
    RS = _room_session()
    stamp = {"ts": "2026-10-13T07:40:00.000Z", "by": "0000-0003-2222-2221"}
    doc = {"graphs": {"tavolo": {"graph_id": "tavolo", "nodes": [
        {"id": "US3", "node_type": "US", "name": "US3", "data": {}},
        {"id": "US3.model", "node_type": "resource", "name": "US3 (glTF)", "data": {}},
        {"id": "gone", "node_type": "US", "name": "gone", "data": {"removed": stamp}},
    ], "edges": [
        {"id": "e1", "source": "US3", "target": "US3.model",
         "edge_type": "has_linked_resource", "attributes": {"removed": stamp}},
        {"id": "e2", "source": "gone", "target": "US3", "edge_type": "is_after"},
        {"id": "e3", "source": "US3", "target": "US3.model", "edge_type": "has_data_provenance"},
    ]}}}
    view = RS.live_view(doc)["graphs"]["tavolo"]
    assert [n["id"] for n in view["nodes"]] == ["US3", "US3.model"]
    assert [e["id"] for e in view["edges"]] == ["e3"]
    # the document itself is not touched: the merge needs its tombstones
    assert len(doc["graphs"]["tavolo"]["edges"]) == 3
