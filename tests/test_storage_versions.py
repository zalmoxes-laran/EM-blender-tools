"""MICRO lo storage governa le versioni (13 Oct 2026), measured without bpy.

Measured in the room `tavolo-2026-10-12`: E.D. changed the proxy of US2 and
«Sync the scene…» sent it; the scene got the OLD one back as well. Here, on a
graph built as the room was:

* the migration closes `<US>.model` (and a room migrated before is repaired):
  after migration + change + sync, `materialise` brings nothing;
* the revision moves the shape's citation, under an edge id of its own, so the
  room sees it;
* a second identical sync writes nothing;
* «Withdraw» tombstones the resource, its revisions and its edges;
* «Use this version» makes the chosen bytes current and moves the citation.
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

from s3dgraphy import api  # noqa: E402
from s3dgraphy.exporter.emjson_exporter import build_emjson  # noqa: E402
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
    pkg = types.ModuleType("_sv")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_sv"] = pkg
    return _load(f"_sv.{name}", f"sync_manager/{name}.py")


PC = _load("_sv_proxy_chain", "proxy_chain.py")
GOV = _load("_sv_resource_governance", "resource_governance.py")
SYNC = _load_sync("scene_sync")
MAT = _load_sync("materialise")

OLD = "sha256:" + "e3" * 32           # the proxy as it was published
NEW = "sha256:" + "6c" * 32           # the proxy E.D. changed


def _url(d):
    return f"https://em.localhost:8443/v1/rooms/tavolo/assets/{d}"


def _spec(d, name="US 2 · dopo A.glb"):
    return {"path": name, "url": _url(d), "checksum": d, "size_bytes": 1234,
            "media_type": "model/gltf-binary"}


def _room():
    """US1, US2 with the `<US>.model` an EMtools 1.6.0-dev.14 published."""
    g = Graph("tavolo-2026-10-12")
    for uid in ("US1", "US2"):
        g.add_node(StratigraphicUnit(uid, name=uid))
    promote_resource(g, "US2.model", url=_url(OLD), sha256=OLD,
                     media_type="model/gltf-binary", link_to="US2",
                     name="US2 (glTF)", residency="resident")
    promote_resource(g, "US1.model", url=_url("sha256:" + "11" * 32),
                     sha256="sha256:" + "11" * 32, media_type="model/gltf-binary",
                     link_to="US1", name="US1 (glTF)", residency="resident")
    return g


def _room_as_measured():
    """The room on 13 Oct 2026, 10:50: migrated by dev48 (the `<US>.model`
    left alive), then one sync of the changed proxy that made TWO revisions of
    the same bytes and left the shape citing the old resource."""
    g = _room()
    for uid in ("US1", "US2"):
        chain = PC.ensure_unit_proxy(g, uid, uid)
        new, old = g.find_node_by_id(chain["resource_id"]), g.find_node_by_id(f"{uid}.model")
        new.data.update({k: old.data[k] for k in ("url", "checksum", "residency", "media_type")
                         if k in old.data})
        for e in list(g.edges):
            if e.edge_type == "dtc_had_output" and e.edge_target == old.node_id:
                g.add_edge(f"gen-{uid}", e.edge_source, new.node_id, "dtc_had_output")
            if e.edge_type == "has_linked_resource" and e.edge_source == uid:
                g.remove_edge(e.edge_id)
    # what dev49's `_revise` did: the object's resource, then the chain's
    # (by then the same resource's revision), `force` — two of the same bytes
    rr = GOV._rr()
    _s, canonical = PC.glb_proxy(g, "US2")
    first = rr.revise_files(g, canonical.node_id, [_spec(NEW)], force=True)["new_resource_id"]
    second = rr.revise_files(g, first, [_spec(NEW)], force=True)["new_resource_id"]
    for rid in (first, second):
        g.find_node_by_id(rid).data.update({"checksum": NEW, "url": _url(NEW),
                                            "residency": "resident"})
    return g, canonical.node_id, first, second


def _cites(g, shape_id):
    return [e.edge_target for e in g.edges
            if e.edge_source == shape_id and e.edge_type == "has_linked_resource"]


class _Obj(dict):
    def __init__(self, name, digest, rid=""):
        super().__init__(em_asset_sha256=digest, em_resource_id=rid)
        self.name = name


def _nothing_fetched(graph, scene):
    def fetch(checksum):
        raise AssertionError(f"materialise fetched {checksum}")
    return MAT.materialise(graph, fetch=fetch, importer=lambda p: [], objects=scene)


# ── 1 · the migration closes the old form ───────────────────────────────────

def test_the_migration_takes_the_old_model_out_of_the_live_graph():
    g = _room()
    report = PC.migrate_unit_models(g)
    assert {c["unit_id"] for c in report["closed"]} == {"US1", "US2"}
    assert g.find_node_by_id("US2.model") is None
    assert g.find_node_by_id("US1.model") is None
    shape, res = PC.glb_proxy(g, "US2")
    assert GOV.digest_of(g, res.node_id) == GOV.bare_digest(OLD)
    # the genesis is on the canonical resource
    assert any(e.edge_type == "dtc_had_output" and e.edge_target == res.node_id
               for e in g.edges)
    assert PC.migrate_unit_models(g)["migrated"] == []


def test_after_migration_change_and_sync_materialise_brings_nothing():
    g = _room()
    PC.migrate_unit_models(g)
    shape, res = PC.glb_proxy(g, "US2")
    out = GOV.revise_and_cite(g, res.node_id, _spec(NEW))
    assert out["created"] and _cites(g, shape.node_id) == [out["resource_id"]]
    # the scene holds the changed proxy and US1's: nothing is owed to it
    scene = [_Obj("US 2 · dopo A", NEW, out["resource_id"]),
             _Obj("US1", "sha256:" + "11" * 32)]
    report = _nothing_fetched(g, scene)
    assert report["materialised"] == [] and report["failed"] == []
    assert sorted(r["checksum"] for r in report["reused"]) == sorted(
        ["sha256:" + "11" * 32, NEW])


def test_a_room_migrated_before_is_repaired_at_the_next_sync():
    g, canonical, first, second = _room_as_measured()
    shape, _r = PC.glb_proxy(g, "US2")
    assert _cites(g, shape.node_id) == [canonical]              # as measured
    before = build_emjson(g)["graph"]

    closed = GOV.close_legacy_models(g)
    forwarded = GOV.forward_proxy_citations(g)

    assert sorted(c["unit_id"] for c in closed["closed"]) == ["US1", "US2"]
    assert g.find_node_by_id("US2.model") is None and g.find_node_by_id("US1.model") is None
    assert _cites(g, shape.node_id) == [second]                 # the current revision
    assert forwarded == [{"shape": shape.node_id, "old": canonical, "new": second}]

    ops = SYNC.section_delta_ops(before, build_emjson(g)["graph"])
    removed_nodes = {o["id"] for o in ops if o["op"] == "remove_node"}
    assert {"US1.model", "US2.model"} <= removed_nodes
    gone = [o for o in ops if o["op"] == "remove_edge"
            and o["source"] == shape.node_id and o["target"] == canonical]
    came = [o for o in ops if o["op"] == "add_edge"
            and o["source"] == shape.node_id and o["target"] == second]
    assert len(gone) == 1 and len(came) == 1
    assert gone[0]["id"] != came[0]["id"], "the moved edge kept the id the room already has"

    # …and once repaired, a second pass changes nothing
    again = build_emjson(g)["graph"]
    assert GOV.close_legacy_models(g)["closed"] == [] and GOV.forward_proxy_citations(g) == []
    assert SYNC.section_delta_ops(again, build_emjson(g)["graph"]) == []

    # the scene of the measure: the changed proxy and the old one materialised again
    scene = [_Obj("US 2 · dopo A", NEW, first), _Obj("US 2 · dopo A.001", OLD, "US2.model")]
    assert _nothing_fetched(g, scene)["materialised"] == []
    removed = {i for c in closed["closed"] for i in c["removed"]}
    assert GOV.object_status(g, "US2.model", OLD, removed=removed) == GOV.STATUS_WITHDRAWN
    # bound to the first of two revisions with the same bytes: current, not superseded
    assert GOV.object_status(g, first, NEW) == GOV.STATUS_CURRENT
    assert GOV.object_status(g, canonical, OLD) == GOV.STATUS_SUPERSEDED
    # a resource of another graph is not «withdrawn» just because it is not here
    assert GOV.object_status(g, "elsewhere", OLD, removed=removed) == GOV.STATUS_CURRENT


def test_an_old_model_still_cited_by_a_document_is_left_and_said():
    g, *_ = _room_as_measured()
    g.add_edge("doc-cites", "US1", "US2.model", "has_data_provenance")
    report = GOV.close_legacy_models(g, ["US2"])
    assert report["closed"] == [] and "still cited" in report["warnings"][0]
    assert g.find_node_by_id("US2.model") is not None


# ── 2 · 3 · the revision moves the citation, once ───────────────────────────

def test_the_revision_moves_the_shape_citation_under_a_new_edge_id():
    g = _room()
    PC.migrate_unit_models(g)
    shape, res = PC.glb_proxy(g, "US2")
    before = build_emjson(g)["graph"]
    out = GOV.revise_and_cite(g, res.node_id, _spec(NEW))
    assert _cites(g, shape.node_id) == [out["resource_id"]]
    assert api.revisions_of(g, out["resource_id"]) == [res.node_id, out["resource_id"]]
    ops = SYNC.section_delta_ops(before, build_emjson(g)["graph"])
    assert any(o["op"] == "remove_edge" and o["target"] == res.node_id
               and o["edge_type"] == "has_linked_resource" for o in ops)
    assert any(o["op"] == "add_edge" and o["target"] == out["resource_id"]
               and o["edge_type"] == "has_linked_resource" for o in ops)
    # the genesis stays on the old bytes
    assert any(e.edge_type == "dtc_had_output" and e.edge_target == res.node_id
               for e in g.edges)


def test_a_second_identical_sync_writes_nothing():
    g = _room()
    PC.migrate_unit_models(g)
    _shape, res = PC.glb_proxy(g, "US2")
    first = GOV.revise_and_cite(g, res.node_id, _spec(NEW))
    before = build_emjson(g)["graph"]
    # from the resource the object was bound to, or from the new one
    for rid in (res.node_id, first["resource_id"]):
        again = GOV.revise_and_cite(g, rid, _spec(NEW))
        assert again == {"resource_id": first["resource_id"], "revision_of": None,
                         "created": False, "moved": 0}
    assert SYNC.section_delta_ops(before, build_emjson(g)["graph"]) == []


def test_an_object_bound_to_an_old_revision_revises_the_current_one():
    g = _room()
    PC.migrate_unit_models(g)
    _shape, res = PC.glb_proxy(g, "US2")
    mid = GOV.revise_and_cite(g, res.node_id, _spec(NEW))["resource_id"]
    third = "sha256:" + "7a" * 32
    out = GOV.revise_and_cite(g, res.node_id, _spec(third))
    assert out["revision_of"] == mid
    assert api.revisions_of(g, out["resource_id"]) == [res.node_id, mid, out["resource_id"]]


# ── 4 · the Storage panel's gestures ────────────────────────────────────────

def test_withdraw_tombstones_the_resource_its_revisions_and_its_edges():
    g, canonical, first, second = _room_as_measured()
    GOV.close_legacy_models(g)
    GOV.forward_proxy_citations(g)
    shape, _r = PC.glb_proxy(g, "US2")
    plan = GOV.withdraw_plan(g, first)
    assert plan["members"] == [canonical, first, second]
    assert [c["source"] for c in plan["citing"]] == [shape.node_id]
    before = build_emjson(g)["graph"]
    GOV.withdraw(g, first)
    for nid in plan["members"] + plan["files"]:
        assert g.find_node_by_id(nid) is None
    ops = SYNC.section_delta_ops(before, build_emjson(g)["graph"])
    assert {o["id"] for o in ops if o["op"] == "remove_node"} == \
        set(plan["members"]) | set(plan["files"])
    assert any(o["op"] == "remove_edge" and o["source"] == shape.node_id for o in ops)
    assert any(o["op"] == "remove_edge" and o["edge_type"] == "was_revision_of" for o in ops)
    assert not any(o["op"].startswith("add") for o in ops)
    # remove_node after the edges it held
    kinds = [o["op"] for o in ops]
    assert kinds.index("remove_node") > max(i for i, k in enumerate(kinds) if k == "remove_edge")


def test_use_this_version_makes_the_old_bytes_current_and_moves_the_edge():
    g = _room()
    PC.migrate_unit_models(g)
    shape, res = PC.glb_proxy(g, "US2")
    newer = GOV.revise_and_cite(g, res.node_id, _spec(NEW))["resource_id"]
    before = build_emjson(g)["graph"]
    out = GOV.use_version(g, res.node_id)
    assert out["created"] and out["revision_of"] == newer
    head = out["resource_id"]
    assert api.current_revision(g, res.node_id) == head
    assert GOV.digest_of(g, head) == GOV.bare_digest(OLD)
    assert g.find_node_by_id(head).data.get("residency") == "resident"
    assert _cites(g, shape.node_id) == [head]
    ops = SYNC.section_delta_ops(before, build_emjson(g)["graph"])
    assert any(o["op"] == "add_edge" and o["source"] == shape.node_id
               and o["target"] == head for o in ops)
    # the current one: nothing to do
    assert GOV.use_version(g, head)["created"] is False


def test_the_rows_of_one_resource_are_grouped_by_revision():
    g, canonical, first, second = _room_as_measured()
    info = GOV.revision_info(g, [first])
    assert info[canonical]["head"] == second and info[second]["index"] == 2
    assert info[first]["chain"] == [canonical, first, second]
