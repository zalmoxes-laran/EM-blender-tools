"""MICRO tre pannelli (13 Oct 2026), measured without bpy.

E.D. in the room `tavolo-2026-10-12`, editor2: «Open in EMStudio» twice, the
identity three times, two alignments, the counters and «Check files» beside a
sync that checks the same, «Replace with the scene's object (US 3)» in the card
of US 2, v1 and v2 of US 2 with the same bytes, «by…22-2221» for Editor Due.
Room, Files, Project storage: each thing said once.

* the head of Files counts as the one resolver counts («8 files · 2 only on
  the node»);
* two versions with the same bytes are one version (`v1/1`, no label);
* «Replace» is not offered for an object that is not this resource's (US 3 ↔
  US 2), and its operator checks it too;
* who did a thing is said by name, never an ORCID;
* the room is one state, its name whole, who you are once.
"""

import importlib.util
import pathlib
import re
import sys
import types

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir():
    sys.path.insert(0, str(_S3D))

pytest.importorskip("s3dgraphy.geometry.proxy")

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.author_node import AuthorNode  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402
from s3dgraphy.resources.locate import summary  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_sync(name):
    pkg = types.ModuleType("_tp")
    pkg.__path__ = [str(_REPO / "sync_manager")]
    sys.modules["_tp"] = pkg
    return _load(f"_tp.{name}", f"sync_manager/{name}.py")


PC = _load("_tp_proxy_chain", "proxy_chain.py")
GOV = _load("_tp_resource_governance", "resource_governance.py")
PROV = _load("_tp_provenance_card", "provenance_card.py")
FL = _load_sync("files_list")
WHERE = _load_sync("where")

ROOM = "tavolo-2026-10-12"
ORCID = "0000-0002-1825-2221"
_CODE = re.compile(r"(?i)[0-9a-f]{12,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
                   r"[0-9a-f]{12}|\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")


def _digest(two):
    return "sha256:" + two * 32


def _unit(g, uid, name, digest):
    g.add_node(StratigraphicUnit(uid, name=name))
    rid = PC.ensure_unit_proxy(g, uid, name)["resource_id"]
    g.find_node_by_id(rid).data.update(
        {"url": GOV.store_url("http://localhost:8000", ROOM, digest), "checksum": digest,
         "residency": "resident", "media_type": "model/gltf-binary",
         "created_by": ORCID, "created_at": "2026-10-13T08:51:00Z"})
    return rid


def _revise(g, rid, digest, at):
    rr = GOV._rr()
    spec = {"path": "x.glb", "url": GOV.store_url("http://localhost:8000", ROOM, digest),
            "checksum": digest, "size_bytes": 10, "media_type": "model/gltf-binary"}
    new = rr.revise_files(g, rid, [spec], force=True)["new_resource_id"]
    g.find_node_by_id(new).data.update({"checksum": digest, "residency": "resident",
                                        "created_by": ORCID, "created_at": at})
    rr.move_citations(g, rid, new, [c["edge_id"] for c in GOV.citing(g, rid)])
    return new


def _results(g):
    return [{"id": n.node_id, "state": "both", "name": n.name, "positions": []}
            for n in g.nodes if getattr(n, "node_type", "") in ("resource", "resource_file")]


# ── B · Files ───────────────────────────────────────────────────────────────

def test_the_head_counts_as_the_one_resolver_counts():
    results = ([{"id": f"r{i}", "state": "both"} for i in range(6)]
               + [{"id": "a", "state": "on_node"}, {"id": "b", "state": "on_node"}])
    c = summary(results)
    assert sum(c.values()) == len(results)
    assert FL.summary_line(c) == "8 files · 2 only on the node"
    assert FL.summary_line({**c, "missing": 1}) == "9 files · 2 only on the node · 1 missing"
    assert FL.summary_line({"on_disk": 3}, in_room=True) == "3 files · 3 only here"
    assert FL.summary_line({"on_disk": 3}) == "3 files"
    assert FL.summary_line({}) == "No files in this study"


def test_two_versions_with_the_same_bytes_are_one():
    """v1 and v2 of US 2 were the two doubled revisions of the morning,
    alive again after an Undo: one row, no «v2/2»."""
    g = Graph(ROOM)
    v1 = _unit(g, "US2", "US 2", _digest("6c"))
    v2 = _revise(g, v1, _digest("6c"), "2026-10-13T09:20:00Z")
    assert GOV.chain_of(g, v1) == [v1, v2]
    assert GOV.version_count(g, v2) == (1, 1)
    groups = GOV.distinct_versions(GOV.versions(g, v2))
    assert len(groups) == 1 and groups[0]["id"] == v1          # the oldest is shown
    assert groups[0]["in_use"] and [v["id"] for v in groups[0]["same"]] == [v2]
    row = [r for r in FL.build_rows(g, _results(g)) if r["file"] == "US 2 — proxy"]
    assert len(row) == 1 and row[0]["versions"] == "" and row[0]["revs"] == 1
    # a third version with other bytes: two
    v3 = _revise(g, v2, _digest("e5"), "2026-10-13T09:24:00Z")
    assert GOV.version_count(g, v3) == (2, 2)
    row = [r for r in FL.build_rows(g, _results(g)) if r["file"] == "US 2 — proxy"]
    assert row[0]["versions"] == "v2/2"


def test_parts_are_not_rows_and_rows_have_a_kind():
    g = Graph(ROOM)
    _unit(g, "US1", "US 1", _digest("11"))
    rows = FL.build_rows(g, _results(g))
    assert [r["file"] for r in rows] == ["US 1 — proxy"]
    assert rows[0]["what"] == "proxy" and rows[0]["tag"] == ""
    assert not any("Unnamed part" in r["file"] for r in rows)


def test_replace_is_not_offered_for_another_resources_object():
    """13 Oct 2026: «Replace with the scene's object (US 3)» in the card of
    US 2 would have sent US 3's mesh as a version of US 2."""
    g = Graph(ROOM)
    us2 = _unit(g, "US2", "US 2", _digest("22"))
    us3 = _unit(g, "US3", "US 3", _digest("33"))
    obj_us3 = {"em_resource_id": us3, "em_rm_node_id": "US3"}
    obj_us2 = {"em_resource_id": us2, "em_rm_node_id": "US2"}
    assert not GOV.bound_to(g, us2, obj_us3)
    assert GOV.bound_to(g, us3, obj_us3)
    assert GOV.bound_to(g, us2, obj_us2)
    # bound by its unit only (the resource id lost, or an old `<US>.model`)
    assert GOV.bound_to(g, us2, {"em_resource_id": "US2.model", "em_rm_node_id": "US2"})
    assert not GOV.bound_to(g, us2, {"em_rm_node_id": "US3"})
    assert not GOV.bound_to(g, us2, {})
    # a later version of US 2 in use: the object of the older one is NOT the
    # object of this resource any more (MICRO una verità: Replace would send
    # superseded geometry as new); the object with the bytes in use is
    v2 = _revise(g, us2, _digest("2b"), "2026-10-13T09:30:00Z")
    assert not GOV.bound_to(g, v2, obj_us2) and not GOV.bound_to(g, v2, obj_us3)
    assert GOV.bound_to(g, v2, {**obj_us2, "em_asset_sha256": _digest("2b")})
    assert GOV.bound_to(g, v2, {"em_resource_id": v2, "em_rm_node_id": "US2"})
    src = (_REPO / "sync_manager" / "files_list.py").read_text()
    assert src.count("bound_object(context") >= 3       # poll, execute, card


def test_who_did_it_is_said_by_name():
    names = FL.people([{"author": ORCID, "display": "Editor Due", "role": "editor"},
                       {"author": "0000-0001-0000-0001", "display": "0000-0001-0000-0001"}])
    assert names == {ORCID: "Editor Due"}
    assert FL.who_is(ORCID, names) == "Editor Due"
    assert FL.who_is(ORCID, {}) == "someone"                  # never the ORCID
    assert FL.who_is("editor2", {}) == "editor2"              # a username is a name
    g = Graph(ROOM)
    a = AuthorNode("a1", name="Emanuel", surname="Demetrescu", orcid=ORCID)
    g.add_node(a)
    assert FL.who_is(ORCID, {}, g) == "Emanuel Demetrescu"
    # the versions and the withdrawn rows, said with these names
    us2 = _unit(g, "US2", "US 2", _digest("22"))
    v = GOV.distinct_versions(GOV.versions(g, us2))[0]
    line = FL.version_line({**v, "by": FL.who_is(v["by"], names, g)}, today="2026-10-13")
    assert "Editor Due" in line and not _CODE.search(line)
    rows = FL.withdrawn_rows(None, [{"id": "x", "name": "US 3 — proxy", "by": ORCID,
                                     "at": "2026-10-13T09:19:21Z"}], names)
    assert rows[0]["state"] == "withdrawn" and rows[0]["where"].startswith("by Editor Due")
    assert not _CODE.search(rows[0]["where"])


def test_withdrawn_rows_only_under_their_filter():
    assert FL.shown("all", "all", "both", "proxy")
    assert not FL.shown("all", "all", "withdrawn", "")
    assert FL.shown("withdrawn", "all", "withdrawn", "")
    assert not FL.shown("withdrawn", "all", "both", "proxy")
    assert FL.shown("here", "all", "on_disk", "rm") and FL.shown("here", "all", "both", "rm")
    assert not FL.shown("here", "all", "on_node", "rm")
    assert FL.shown("missing", "proxy", "empty_copy", "proxy")
    assert not FL.shown("all", "document", "both", "proxy")


def test_where_it_comes_from_in_plain_sentences():
    g = Graph(ROOM)
    us2 = _unit(g, "US2", "US 2", _digest("22"))
    c = PROV.card(g, us2)
    assert PROV.story(c) == ["No record of how it was made"]
    made = {"resource": "r", "steps": [{"tool": "Blender", "who": ORCID,
                                        "at": "2026-10-13T08:51:00Z", "when": "2026-10-13",
                                        "process": "", "technique": "",
                                        "inputs": [{"name": "US 2 · dopo A", "state": ""}],
                                        "more": 0}], "used_by": 0}
    said = PROV.story(made, lambda by: FL.who_is(by, {ORCID: "Editor Due"}),
                      lambda at: FL.when(at, today="2026-10-13"))
    assert said[0].startswith("Made in Blender by Editor Due, ")
    assert said[1] == "From US 2 · dopo A"
    assert not any(_CODE.search(x) for x in said)


def test_the_bucket_says_what_it_asks_on_a_closed_head():
    assert FL.bucket_todo(False, {}) == "Bucket not checked"
    assert FL.bucket_todo(False, {}, has_files=False) == ""
    assert FL.bucket_todo(True, {"a": {"state": "aligned"}}) == ""
    assert FL.bucket_todo(True, {"a": {"state": "differ"}, "b": {"state": "aligned"}}) == \
        "Bucket: 1 differ"


# ── A · Room ────────────────────────────────────────────────────────────────

def _room(**kw):
    s = {"place": "room", "room_title": "Tavolo · prova multiutente 12 ottobre",
         "room_id": ROOM, "node": "https://em.localhost:8443/em", "members": 2,
         "author": "Editor Due", "role": "editor", "sent": 4, "answered": 4,
         "signin_line": "signed in to https://em.localhost:8443/em as editor2"}
    s.update(kw)
    return WHERE.zones(s)


def test_the_room_says_each_thing_once():
    z = _room()
    assert z["place"][1] == "▣ Tavolo · prova multiutente 12 ottobre · 2 present"
    assert z["who"][1] == "Editor Due · editor · em.localhost:8443"
    assert z["state"]["text"] == "● Aligned"
    assert z["message"]["text"] == ""                       # no «signed in to … as»
    assert z["place_detail"][1] == "" and z["log"][1] == ""
    said = [z["place"][1], z["who"][1], z["state"]["text"]]
    assert sum("em.localhost" in x for x in said) == 1
    assert not any(_CODE.search(x) for x in said)
    # an ORCID is not a name
    assert "0000" not in _room(author=ORCID)["who"][1]


def test_the_room_is_one_state():
    assert _room(waiting=3)["state"]["text"] == "● Sending 3…"
    off = _room(offline=True, waiting=5)["state"]
    assert off["text"] == "● Offline — 5 waiting" and off["op"] == "em.room_reconnect"
    tally = {"here": 4, "missing": 0, "changed": 2, "external": 0, "only_here": 0}
    assert _room(tally=tally)["state"]["text"] == "● 2 changes here, not sent"
    # a revision made here and not sent is said, never «● Aligned»
    assert _room(tally={**tally, "changed": 0}, here_only=1)["state"]["text"] == \
        "● 1 change here, not sent"
    dl = _room(tally={**tally, "changed": 0, "missing": 3}, offer_download=True)["state"]
    assert dl["text"] == "● 3 to download" and dl["op"] == "em.scene_check"
    assert _room(tally={**tally, "changed": 0})["state"]["text"] == "● Aligned"


def test_the_rooms_name_wraps_whole():
    lines = WHERE.wrap("▣ Tavolo · prova multiutente 12 ottobre · 2 present", 22)
    assert " ".join(lines) == "▣ Tavolo · prova multiutente 12 ottobre · 2 present"
    assert all(len(x) <= 22 for x in lines) and not any("…" in x for x in lines)
    assert WHERE.host_port("https://em.localhost:8443/em") == "em.localhost:8443"


def test_a_name_from_the_token():
    import base64
    import json
    body = base64.urlsafe_b64encode(json.dumps(
        {"name": "Editor Due", "preferred_username": "editor2", "orcid": ORCID}).encode()
    ).decode().rstrip("=")
    assert WHERE.name_in(f"h.{body}.s") == "Editor Due"
    assert WHERE.name_in("opaque") == ""


# ── the sources: what went, where it went ───────────────────────────────────

def test_open_in_emstudio_is_drawn_once_and_check_files_is_automatic():
    import glob
    drawn = []
    for path in glob.glob(str(_REPO / "**" / "*.py"), recursive=True):
        if "/_dead_code/" in path or "/tests/" in path or "/build/" in path:
            continue
        text = pathlib.Path(path).read_text(errors="replace")
        drawn += [path for _ in re.finditer(r'text="Open in EMStudio"', text)]
    assert [pathlib.Path(p).name for p in drawn] == ["panel.py"], drawn
    fs = (_REPO / "sync_manager" / "file_states.py").read_text()
    assert 'text="Check files"' not in fs and "Keep the" not in fs
    assert "check_soon" in (_REPO / "sync_manager" / "operators.py").read_text()
    assert "load_post" in fs
