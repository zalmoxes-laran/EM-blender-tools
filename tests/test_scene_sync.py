"""P2 · «Sync the scene…»: which models are offered, and what reaches the room.

The pure half of `sync_manager/scene_sync.py`; the Blender half is measured by
`tests/blender_smoke_sync_scene.py` on a copy of Templu Mare and the dev node.
"""
import importlib.util
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parent.parent


def _load():
    pkg = types.ModuleType("_p2pkg")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_p2pkg"] = pkg
    spec = importlib.util.spec_from_file_location("_p2pkg.scene_sync",
                                                  _REPO / "sync_manager" / "scene_sync.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ss = _load()


def _m(name, **kw):
    base = {"object": name, "target": name + "-id", "kind": "proxy", "digest": "sha256:a",
            "published": True, "fingerprint": "F", "recorded": "F",
            "linked_library": False, "only_here": False}
    base.update(kw)
    return base


def test_a_mesh_that_moved_from_its_bytes_is_changed_and_one_never_published_is_new():
    g = ss.classify_models([
        _m("same"),
        _m("edited", fingerprint="G"),
        _m("fresh", digest="", published=False),
        _m("unknown", recorded=""),
    ])
    assert [m["object"] for m in g["changed"]] == ["edited"]
    assert g["changed"][0]["state"] == ss.STATE_CHANGED
    assert [m["object"] for m in g["new"]] == ["fresh"]
    # published before the fingerprint existed: a baseline, not a guess
    assert [m["object"] for m in g["baseline"]] == ["unknown"]


def test_only_here_and_a_linked_library_never_go_up():
    g = ss.classify_models([_m("deco", only_here=True, fingerprint="X"),
                            _m("rb", linked_library=True, digest="", published=False)])
    assert not g["changed"] and not g["new"]
    assert {m["object"] for m in g["skipped"]} == {"deco", "rb"}


def test_the_size_is_an_estimate_said_as_one():
    assert ss.estimated_size(1000, 2000) == 32 * 1000 + 12 * 2000 + 2048
    assert ss.human_size(512) == "512 B"
    assert ss.human_size(2048) == "2.0 kB"


def test_the_delta_is_the_ops_of_what_changed_and_nothing_else():
    before = {"nodes": [{"id": "R", "type": "resource", "name": "R",
                         "data": {"url": "u1", "checksum": "c1"}},
                        {"id": "U", "type": "US", "name": "U"}],
              "edges": [{"id": "U~R", "source": "U", "target": "R",
                         "edge_type": "has_representation_model"}]}
    after = {"nodes": [{"id": "R", "type": "resource", "name": "R",
                        "data": {"url": "u1", "checksum": "c1"}},
                       {"id": "R2", "type": "resource", "name": "R",
                        "data": {"url": "u2", "checksum": "c2"}},
                       {"id": "U", "type": "US", "name": "U", "description": "d"}],
             "edges": [{"id": "U~R2", "source": "U", "target": "R2",
                        "edge_type": "has_representation_model"},
                       {"id": "R2~revision~>R", "source": "R2", "target": "R",
                        "edge_type": "was_revision_of"}]}
    ops = ss.section_delta_ops(before, after)
    kinds = [(o["op"], o.get("id") or o.get("node_id"), o.get("field")) for o in ops]
    assert ("add_node", "R2", None) in kinds
    assert ("update_field", "U", "description") in kinds
    assert ("add_edge", "U~R2", None) in kinds and ("add_edge", "R2~revision~>R", None) in kinds
    assert ("remove_edge", "U~R", None) in kinds
    assert not any(k[1] == "R" for k in kinds)          # the old one, as it was
    assert len(ops) == 5


def test_a_field_that_went_is_an_emptying():
    ops = ss.section_delta_ops({"nodes": [{"id": "U", "description": "x", "data": {"k": 1}}]},
                               {"nodes": [{"id": "U", "data": {}}]})
    assert {(o["field"], o.get("remove")) for o in ops} == {("description", True),
                                                           ("data.k", True)}
