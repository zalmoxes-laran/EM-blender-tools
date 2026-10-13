"""MICRO lo storage parla come una persona (13 Oct 2026), measured without bpy.

E.D. in the room `tavolo-2026-10-12`: «codici UUID ovunque… se voglio tornare
a una versione precedente di un proxy mi ritrovo che si crea un'ulteriore
versione futura». On a graph built as the relay measured it (the chain of US2,
four revisions from two round trips, one checksum without `sha256:`, three
hosts in the urls):

* «Use v1» moves the citation and creates no node; a sync after it writes
  nothing; a changed object makes one revision, and bytes a version already
  has move the pointer back to it;
* no path rewrites the `checksum`/`url` of a resource that has its bytes (the
  09:20:17 UTC case), and the digest is always written `sha256:<hex>`;
* the store urls take one base; the rows speak in names, one row per resource;
* a withdrawal the room keeps in tombstone says who and when, and «Undo» brings
  it back.
"""

import copy
import importlib.util
import os
import pathlib
import re
import sys
import time
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir():
    sys.path.insert(0, str(_S3D))

pytest.importorskip("s3dgraphy.geometry.proxy")

from s3dgraphy import crdt  # noqa: E402
from s3dgraphy.exporter.emjson_exporter import build_emjson  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402
from s3dgraphy.publication import promote_resource  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_sync(name):
    pkg = types.ModuleType("_sr")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_sr"] = pkg
    return _load(f"_sr.{name}", f"sync_manager/{name}.py")


PC = _load("_sr_proxy_chain", "proxy_chain.py")
GOV = _load("_sr_resource_governance", "resource_governance.py")
SYNC = _load_sync("scene_sync")
MAT = _load_sync("materialise")
FL = _load_sync("files_list")

F4E4 = "sha256:" + "f4e4" * 16           # the proxy of US2 as published
E522 = "sha256:" + "e522" * 16           # the proxy E.D. changed
ROOM = "tavolo-2026-10-12"
HOSTS = ("http://localhost:8000", "https://em.localhost:8443/em",
         "http://MacBook-Pro-di-Emanuel.local:8000")


def _url(d, host=HOSTS[0]):
    return GOV.store_url(host, ROOM, d)


def _spec(d, host=HOSTS[0]):
    return {"path": "US 2 · dopo A.glb", "url": _url(d, host), "checksum": d,
            "size_bytes": 1234, "media_type": "model/gltf-binary"}


def _cites(g, shape_id):
    return [e.edge_target for e in g.edges
            if e.edge_source == shape_id and e.edge_type == "has_linked_resource"]


def _measured():
    """US2's chain as the relay measured it at 09:24:05 UTC: 8e3135e7 (f4e4)
    ← 54f88874 (e5228d, no prefix) ← ab58afab (f4e4) ← 4cf0c371 (e5228d,
    cited by the shape) — two round trips, four revisions."""
    g = Graph(ROOM)
    g.add_node(StratigraphicUnit("US2", name="US 2 · dopo A"))
    chain = PC.ensure_unit_proxy(g, "US2", "US 2 · dopo A")
    first = chain["resource_id"]
    g.find_node_by_id(first).data.update(
        {"url": _url(F4E4), "checksum": F4E4, "residency": "resident",
         "media_type": "model/gltf-binary"})
    rr = GOV._rr()
    ids, prev = [first], first
    for d, host in ((E522, HOSTS[1]), (F4E4, HOSTS[2]), (E522, HOSTS[1])):
        new = rr.revise_files(g, prev, [_spec(d, host)], force=True)["new_resource_id"]
        g.find_node_by_id(new).data.update({"url": _url(d, host), "checksum": d,
                                            "residency": "resident"})
        rr.move_citations(g, prev, new, [c["edge_id"] for c in GOV.citing(g, prev)])
        ids.append(new)
        prev = new
    g.find_node_by_id(ids[1]).data["checksum"] = GOV.bare_digest(E522)   # as measured
    shape, _res = PC.glb_proxy(g, "US2")
    return g, shape.node_id, ids


def _bytes_facts(g):
    return {n.node_id: (GOV.bare_digest(n.data.get("checksum")), n.data.get("url"))
            for n in g.nodes if getattr(n, "node_type", "") == "resource"
            and isinstance(getattr(n, "data", None), dict) and n.data.get("checksum")}


# ── «Use» is a pointer ──────────────────────────────────────────────────────

def test_the_measured_chain_is_four_revisions_and_cites_the_last():
    g, shape, ids = _measured()
    assert GOV.chain_of(g, ids[0]) == ids
    assert _cites(g, shape) == [ids[3]] and GOV.in_use(g, ids[0]) == ids[3]


def test_use_v1_moves_the_edge_and_creates_no_node():
    g, shape, ids = _measured()
    nodes = sorted(n.node_id for n in g.nodes)
    before = build_emjson(g)["graph"]
    out = GOV.use_version(g, ids[0])
    assert out["created"] is False and out["from"] == ids[3] and out["moved"] == 1
    assert sorted(n.node_id for n in g.nodes) == nodes
    assert _cites(g, shape) == [ids[0]]
    ops = SYNC.section_delta_ops(before, build_emjson(g)["graph"])
    assert {o["op"] for o in ops} == {"add_edge", "remove_edge"}
    # the later versions are history: v1 in use, «a later version exists»
    lines = [(v["n"], v["in_use"], v["later"]) for v in GOV.versions(g, ids[0])]
    assert lines == [(1, True, False), (2, False, True), (3, False, True), (4, False, True)]


def test_a_sync_after_use_writes_nothing():
    g, shape, ids = _measured()
    GOV.use_version(g, ids[0])
    before = build_emjson(g)["graph"]
    # the scene's object now holds v1's bytes: sent again, it is the same
    out = GOV.revise_and_cite(g, ids[3], _spec(F4E4))
    assert out["created"] is False and out["resource_id"] == ids[0] and out["moved"] == 0
    assert SYNC.section_delta_ops(before, build_emjson(g)["graph"]) == []
    # …and the scene is owed v1, not the newest
    owed = MAT.superseded_out(g, {"resident": [{"resource_id": i} for i in ids]})
    assert [r["resource_id"] for r in owed["resident"]] == [ids[0]]


def test_a_changed_object_makes_one_revision_and_old_bytes_reuse_a_version():
    g, shape, ids = _measured()
    GOV.use_version(g, ids[0])
    changed = "sha256:" + "7a" * 32
    out = GOV.revise_and_cite(g, ids[0], _spec(changed))
    assert out["created"] and out["revision_of"] == ids[3]       # from the newest: no fork
    assert GOV.chain_of(g, ids[0]) == ids + [out["resource_id"]]
    assert _cites(g, shape) == [out["resource_id"]]
    # back to bytes a version already has: the pointer goes there, no node
    nodes = len(g.nodes)
    back = GOV.revise_and_cite(g, out["resource_id"], _spec(E522))
    assert back["created"] is False and back["reused"] == ids[3]
    assert len(g.nodes) == nodes and _cites(g, shape) == [ids[3]]


def test_an_object_shows_superseded_only_against_the_version_in_use():
    g, shape, ids = _measured()
    GOV.use_version(g, ids[0])
    assert GOV.object_status(g, ids[3], E522) == GOV.STATUS_SUPERSEDED
    assert GOV.object_status(g, ids[2], F4E4) == GOV.STATUS_CURRENT     # same bytes as v1
    assert GOV.object_status(g, ids[0], F4E4) == GOV.STATUS_CURRENT


# ── a resource is never rewritten ───────────────────────────────────────────

def test_no_path_rewrites_the_bytes_of_an_existing_resource():
    g, shape, ids = _measured()
    facts = _bytes_facts(g)
    GOV.use_version(g, ids[1])
    GOV.revise_and_cite(g, ids[0], _spec("sha256:" + "7a" * 32))
    GOV.revise_and_cite(g, ids[0], _spec(F4E4))
    GOV.write_bytes(g, ids[0], _spec("sha256:" + "8b" * 32))
    now = _bytes_facts(g)
    for rid, (digest, url) in facts.items():
        assert now[rid] == (digest, url), f"{rid}: its bytes were rewritten"


def test_the_0920_case_is_a_revision_not_an_overwrite():
    """09:20:17 UTC: the proxy of US2 sent as «new» rewrote checksum and url of
    the resource the room had. `promote_resource` does rewrite; `write_bytes`,
    the road every publish now takes, does not."""
    g, shape, ids = _measured()
    head = ids[3]
    probe = copy.deepcopy(g)
    promote_resource(probe, head, url=_url(F4E4, HOSTS[2]), sha256=F4E4,
                     residency="resident")
    assert GOV.digest_of(probe, head) != GOV.digest_of(g, head)          # the hazard
    out = GOV.write_bytes(g, head, _spec(F4E4, HOSTS[2]))
    assert out["action"] == "pointer" and out["resource_id"] == ids[2]
    assert GOV.digest_of(g, head) == GOV.bare_digest(E522)
    assert g.find_node_by_id(head).data["url"] == _url(E522, HOSTS[1])
    # a resource without bytes yet is born by its writer
    g.add_node(StratigraphicUnit("US5", name="US 5"))
    born = PC.ensure_unit_proxy(g, "US5", "US 5")["resource_id"]
    assert GOV.write_bytes(g, born, _spec(F4E4))["action"] == "write"


def test_the_digest_is_always_written_with_its_prefix():
    g, shape, ids = _measured()
    out = GOV.revise_and_cite(g, ids[3], {**_spec("9c" * 32), "checksum": "9c" * 32})
    assert g.find_node_by_id(out["resource_id"]).data["checksum"] == "sha256:" + "9c" * 32
    assert GOV.normalise_formats(g) == [ids[1]]                          # 54f88874
    assert g.find_node_by_id(ids[1]).data["checksum"] == E522
    assert all(str(n.data.get("checksum")).startswith("sha256:") for n in g.nodes
               if getattr(n, "node_type", "") == "resource" and n.data.get("checksum"))


# ── one base for the store urls ─────────────────────────────────────────────

def test_the_store_urls_take_one_base():
    g, shape, ids = _measured()
    # declared by the node: it wins
    assert GOV.room_base(g, ROOM, declared="https://scavo.example.org/em/") == \
        "https://scavo.example.org/em"
    # not declared: the base the room already uses most (two of four here)
    base = GOV.room_base(g, ROOM, connected=HOSTS[0])
    assert base == HOSTS[1]
    changed = GOV.normalise_formats(g, ROOM, base)
    assert {ids[0], ids[1], ids[2]} <= set(changed)
    assert all(g.find_node_by_id(i).node_type == "resource_file"     # its parts, too
               for i in set(changed) - {ids[0], ids[1], ids[2]})
    urls = {g.find_node_by_id(i).data["url"] for i in ids}
    assert {GOV.parse_store_url(u)["base"] for u in urls} == {HOSTS[1]}
    # the same bytes as the checksum, always
    for i in ids:
        d = g.find_node_by_id(i).data
        assert GOV.parse_store_url(d["url"])["digest"] == GOV.bare_digest(d["checksum"])
    assert GOV.normalise_formats(g, ROOM, base) == []                    # idempotent


def test_a_url_naming_other_bytes_is_not_touched():
    g, shape, ids = _measured()
    node = g.find_node_by_id(ids[0])
    node.data["url"] = _url("sha256:" + "00" * 32, HOSTS[2])
    GOV.normalise_formats(g, ROOM, HOSTS[1])
    assert node.data["url"] == _url("sha256:" + "00" * 32, HOSTS[2])


# ── names, never codes ──────────────────────────────────────────────────────

_HEX_OR_UUID = re.compile(r"(?i)[0-9a-f]{12,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                          r"[0-9a-f]{4}-[0-9a-f]{12}")


def _results(g):
    return [{"id": n.node_id, "state": "on_node", "node_type": n.node_type,
             "name": n.name} for n in g.nodes
            if getattr(n, "node_type", "") in ("resource", "resource_file")]


def test_a_resource_is_named_by_what_cites_it():
    g, shape, ids = _measured()
    assert GOV.display_name(g, ids[0]) == "US 2 · dopo A — proxy"
    g.add_node(RepresentationModelNode("rm1", name="Epoch 1"))
    promote_resource(g, "rm1.model", url=_url("sha256:" + "ab" * 32),
                     sha256="sha256:" + "ab" * 32, link_to="rm1", name="rm1 (glTF)",
                     residency="resident")
    assert GOV.display_name(g, "rm1.model") == "Epoch 1 — RM"
    # nothing cites it, and its name is a code: never the code
    promote_resource(g, "d0c5e1a2-0f3b-4c1e-9a7d-5b8e6f1a2c3d", url=_url("sha256:" + "cd" * 32),
                     sha256="sha256:" + "cd" * 32, name="e5228d048e2b2871f47961f0e",
                     media_type="model/gltf-binary")
    said = GOV.display_name(g, "d0c5e1a2-0f3b-4c1e-9a7d-5b8e6f1a2c3d")
    assert said == "Unnamed 3D model" and not _HEX_OR_UUID.search(said)


def test_one_row_per_resource_with_its_version_and_no_codes():
    g, shape, ids = _measured()
    g.add_node(StratigraphicUnit("US1", name="US 1"))
    one = PC.ensure_unit_proxy(g, "US1", "US 1")["resource_id"]
    g.find_node_by_id(one).data.update({"url": _url("sha256:" + "11" * 32),
                                        "checksum": "sha256:" + "11" * 32,
                                        "residency": "resident"})
    rows = FL.build_rows(g, _results(g))
    for r in rows:
        assert not _HEX_OR_UUID.search(r["file"]), r["file"]
    us2 = [r for r in rows if r["file"] == "US 2 · dopo A — proxy"]
    # MICRO tre pannelli · four versions, two bytes (f4e4, e522): two versions
    assert len(us2) == 1 and us2[0]["versions"] == "v2/2" and us2[0]["id"] == ids[3]
    assert [r["file"] for r in rows if r["file"] == "US 1 — proxy"] == ["US 1 — proxy"]
    assert not any(r["kind"] == "file" for r in rows)       # one file each: not rows
    GOV.use_version(g, ids[0])
    us2 = [r for r in FL.build_rows(g, _results(g)) if r["file"] == "US 2 · dopo A — proxy"]
    assert us2[0]["versions"] == "v1/2" and us2[0]["later"] == "1"


def test_a_version_is_one_short_line():
    os.environ["TZ"] = "Europe/Rome"
    time.tzset()
    v = {"n": 2, "at": "2026-10-13T09:24:05Z", "by": "Editor Due", "in_use": True}
    assert FL.version_line(v, today="2026-10-13") == "v2 · 11:24 · Editor Due · in use"
    assert FL.when("2026-10-12T09:24:05Z", today="2026-10-13") == "12 Oct 11:24"
    assert FL.people([{"user": "editor2", "name": "Editor Due"}]) == {"editor2": "Editor Due"}


# ── withdraw, and undo while the room remembers ─────────────────────────────

def _stamp(ops, ts, author="editor2"):
    return [{**o, "ts": ts, "author": author} for o in ops]


def test_a_withdrawal_in_tombstone_says_who_and_when_and_undo_brings_it_back():
    g, shape, ids = _measured()
    room = copy.deepcopy(build_emjson(g)["graph"])
    before = build_emjson(g)["graph"]
    GOV.withdraw(g, ids[0])
    ops = SYNC.section_delta_ops(before, build_emjson(g)["graph"])
    for op in _stamp(ops, "2026-10-13T09:19:21.000Z"):
        assert crdt.apply_op_to_section(room, op).applied, op
    records = GOV.withdrawn_in_section(room)
    assert len(records) == 1
    rec = records[0]
    assert rec["id"] == ids[3] and sorted(rec["members"]) == sorted(ids)
    assert rec["by"] == "editor2" and rec["at"].startswith("2026-10-13T09:19:21")
    assert rec["cited_by"] == [shape]
    assert FL.withdrawn_name(g, rec) == "US 2 · dopo A — proxy"

    for op in _stamp(GOV.undo_ops(rec, at="2026-10-13T09:30:00Z"), "2026-10-13T09:30:00.000Z",
                     author="editor1"):
        crdt.apply_op_to_section(room, op)
    alive = {n["id"] for n in crdt.live_nodes(room)}
    assert set(ids) <= alive
    live = {(e["source"], e["edge_type"], e["target"]) for e in crdt.live_edges(room)}
    assert (shape, "has_linked_resource", ids[3]) in live
    assert GOV.withdrawn_in_section(room) == []


def test_the_old_form_closed_by_the_migration_is_not_offered_back():
    g = Graph(ROOM)
    g.add_node(StratigraphicUnit("US2", name="US 2"))
    promote_resource(g, "US2.model", url=_url(F4E4), sha256=F4E4, link_to="US2",
                     residency="resident")
    room = copy.deepcopy(build_emjson(g)["graph"])
    before = build_emjson(g)["graph"]
    PC.migrate_unit_models(g)
    for op in _stamp(SYNC.section_delta_ops(before, build_emjson(g)["graph"]),
                     "2026-10-13T09:00:00.000Z"):
        crdt.apply_op_to_section(room, op)
    assert GOV.withdrawn_in_section(room) == []
