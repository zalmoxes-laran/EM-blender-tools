"""R2 · a file row says the file and its document, the sign beside each model,
the count of the Files section said as a filter; I1 · the room, the role, the
sync and «only here» with the signs of s3Dgraphy's one list — without Blender.

The drawing itself is photographed in `tests/blender_shots_r2_i1.py`.
"""
import importlib.util
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parent.parent
_S3D = _REPO.parent / "s3Dgraphy" / "src"
if _S3D.is_dir() and str(_S3D) not in sys.path:
    sys.path.insert(0, str(_S3D))


def _package(name, path):
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(path)]
    sys.modules[name] = pkg
    return pkg


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, _REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# the addon as a package without its __init__ (which needs bpy)
_package("_r2pkg", _REPO)
_package("_r2pkg.sync_manager", _REPO / "sync_manager")
_package("_r2pkg.sync_bridge", _REPO / "sync_bridge")
ss = _load("_r2pkg.state_symbols", "state_symbols.py")
fs = _load("_r2pkg.sync_manager.file_states", "sync_manager/file_states.py")
sc = _load("_r2pkg.sync_manager.scene_check", "sync_manager/scene_check.py")
rs = _load("_r2pkg.sync_manager.room_session", "sync_manager/room_session.py")

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.document_node import DocumentNode  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402
from s3dgraphy.nodes.resource_file_node import ResourceFileNode  # noqa: E402
from s3dgraphy.nodes.resource_node import ResourceNode  # noqa: E402


# ── I1 · room, role, sync ───────────────────────────────────────────────────

def test_the_room_the_role_and_the_sync_take_the_states_of_the_list():
    assert ss.room_state(False) == "room.outside"
    assert ss.room_state(True, True) == "room.inside"
    assert ss.room_state(True, False) == "room.read_only"
    assert [ss.role_state(r) for r in ("owner", "editor", "viewer")] == \
        ["role.owner", "role.editor", "role.viewer"]
    # a role the list does not have keeps its word and gets no sign
    assert ss.role_state("admin") is None and ss.role_state(None) is None
    assert ss.sync_state(0, 0, 0) == "sync.aligned"
    assert ss.sync_state(3, 3, 0) == "sync.aligned"
    assert ss.sync_state(3, 1, 0) == "sync.pending"
    assert ss.sync_state(3, 3, 1) == "sync.conflict"


def test_the_sync_panel_lines_carry_the_glyph_and_the_icon_of_the_list():
    owner = ss.room_signs({"joined": True, "room_id": "r1", "members": 2,
                           "role": "owner", "can_write": True,
                           "sent": 4, "answered": 4, "refused": 0})
    assert owner[0] == ("COMMUNITY", "▣ In r1 · 2 present")
    assert owner[1] == ("SOLO_ON", "★ Role: owner")
    assert owner[2][0] == "CHECKMARK" and owner[2][1].startswith("✓ Aligned")

    viewer = ss.room_signs({"joined": True, "room_id": "r1", "members": 1,
                            "role": "viewer", "can_write": False,
                            "sent": 1, "answered": 1, "refused": 1})
    assert viewer[0] == ("LOCKED", "⊘ In r1 · 1 present · read only")
    assert viewer[1] == ("HIDE_OFF", "◎ Role: viewer")
    assert viewer[2][0] == "ERROR" and viewer[2][1].startswith("≠ In conflict: 1 edit")

    pending = ss.room_signs({"joined": True, "room_id": "r1", "role": "editor",
                             "sent": 3, "answered": 1, "refused": 0})
    assert pending[1] == ("GREASEPENCIL", "✎ Role: editor")
    assert pending[2] == ("TIME", "⋯ Pending: 2 edit(s) sent, not yet confirmed")

    admin = ss.room_signs({"joined": True, "room_id": "r1", "role": "admin"})
    assert admin[1] == ("BLANK1", "Role: admin")

    assert ss.room_signs({"joined": False}) == \
        [("FILE_BLEND", "□ No room: the graph is a file on this computer")]


def test_only_here_is_drawn_with_its_sign():
    assert sc.only_here_line([]) is None
    icon, text = sc.only_here_line(["Decoration"])
    assert icon == "PINNED" and text == "◆ Only here: Decoration"
    assert sc.only_here_line([f"o{i}" for i in range(8)])[1].endswith("… +2")


class _Client:
    connected = True

    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)
        return True


def _frame(kind, payload):
    from _r2pkg.sync_bridge.wire import envelope
    return envelope(kind, payload, source="em-server")


def test_the_session_counts_the_edits_by_the_rooms_answers():
    s = rs.RoomSession()
    s.client = _Client()
    for i in range(3):
        assert s.send_op({"op": "update_field", "node_id": f"n{i}",
                          "field": "description", "value": "x"})
    assert (s.sent_ops, s.answered_ops, s.refused_ops) == (3, 0, 0)
    assert ss.sync_state(s.sent_ops, s.answered_ops, s.refused_ops) == "sync.pending"
    s._absorb(_frame("op_result", {"applied": True, "reason": "", "op": {}}))
    # stale: another hand was later — the state already knew, not a conflict
    s._absorb(_frame("op_result", {"applied": False, "reason": "stale", "op": {}}))
    assert ss.sync_state(s.sent_ops, s.answered_ops, s.refused_ops) == "sync.pending"
    s._absorb(_frame("op_result", {"applied": True, "reason": "", "op": {}}))
    assert ss.sync_state(s.sent_ops, s.answered_ops, s.refused_ops) == "sync.aligned"
    # a refusal that is news, and a write the role may not do
    s.send_op({"op": "update_field", "node_id": "n9", "field": "name", "value": "y"})
    s._absorb(_frame("op_result", {"applied": False, "reason": "resurrected", "op": {}}))
    s.send_op({"op": "update_field", "node_id": "n9", "field": "name", "value": "z"})
    s._absorb(_frame("denied", {"verb": "op", "reason": "this room is read-only for your role"}))
    assert (s.sent_ops, s.answered_ops, s.refused_ops) == (5, 5, 2)
    assert ss.sync_state(s.sent_ops, s.answered_ops, s.refused_ops) == "sync.conflict"
    # a denied snapshot request is not one of our edits
    s._absorb(_frame("denied", {"verb": "request_snapshot", "reason": "read-only"}))
    assert s.answered_ops == 5
    s.client = None
    s.leave()
    assert (s.sent_ops, s.answered_ops, s.refused_ops) == (0, 0, 0)


# ── R2 · what a file row says, the sign beside a model, the count ───────────

def _san_pietro_like():
    """The shape the GraphML importer gives: every link is «Link to D.xx»."""
    g = Graph("sp")
    d32 = DocumentNode("d32", "D.32", "")
    d02 = DocumentNode("d02", "D.02", "La chiesa di San Pietro in un'incisione di E. Dodwell (1834)")
    d40 = DocumentNode("d40", "D.40", "Rilievo 1931")
    for n in (d32, d02, d40):
        g.add_node(n)
    g.add_node(ResourceNode("l32", "Link to D.32", url="/DosCo/D.32.jpg"))
    g.add_node(ResourceNode("l02", "Link to D.02", url="//DosCo/D.02.png"))
    g.add_node(ResourceNode("set40", "Link to D.40", url=""))
    g.add_node(ResourceFileNode("f1", "Link to D.40", url="https://h/x/tav1%20b.tif?v=2"))
    g.add_node(ResourceNode("lost", "Link to D.99", url=""))
    g.add_edge("e1", "d32", "l32", "has_linked_resource")
    g.add_edge("e2", "d02", "l02", "has_linked_resource")
    g.add_edge("e3", "d40", "set40", "has_linked_resource")
    g.add_edge("e4", "set40", "f1", "has_file")
    return g


def test_last_segment_of_any_address():
    assert fs.last_segment("/DosCo/D.32.jpg") == "D.32.jpg"
    assert fs.last_segment("C:\\x\\D.32.jpg") == "D.32.jpg"
    assert fs.last_segment("https://h/x/P01%5Bext%5D.jpeg?v=2") == "P01[ext].jpeg"
    assert fs.last_segment("photos/") == "photos"
    assert fs.last_segment("") == ""


def test_a_file_row_says_the_file_and_its_document_not_link_to():
    g = _san_pietro_like()
    assert fs.describe(g, "l32") == {"file": "D.32.jpg", "doc": "D.32", "doc_id": "d32"}
    assert fs.describe(g, "l02")["doc"] == \
        "D.02 · La chiesa di San Pietro in un'incisione di E. Dodwell (1834)"
    # one file of a set: its document through the set
    assert fs.describe(g, "f1") == {"file": "tav1 b.tif", "doc": "D.40 · Rilievo 1931",
                                    "doc_id": "d40"}
    # where the resolver found it wins over where the graph says it is
    assert fs.describe(g, "l32", {"path": "/x/EM/DosCo/D.32.jpg"})["file"] == "D.32.jpg"
    # a store-backed file: its store address ends in the digest, the path it
    # came from is kept as a second address — that one names the file
    g.add_node(ResourceNode("up", "LINK.DOC.US1.001",
                            url="http://n/v1/rooms/r/asset/sha256:" + "f" * 64))
    g.find_node_by_id("up").data["addresses"] = [
        {"locator": "http://n/v1/rooms/r/asset/sha256:" + "f" * 64},
        {"locator": "DosCo/D.01.jpg"}]
    assert fs.describe(g, "up")["file"] == "D.01.jpg"
    # with no address at all the node's name stays (nothing to invent)
    assert fs.describe(g, "lost") == {"file": "Link to D.99", "doc": "", "doc_id": None}


def test_the_sign_of_a_model_is_where_its_file_can_best_be_had():
    g = Graph("m")
    g.add_node(RepresentationModelNode("M_model", "Model for M"))
    g.add_node(RepresentationModelNode("N_model", "Model for N"))
    g.add_node(RepresentationModelNode("E_model", "Model with no file"))
    for rid in ("m_blend", "m_glb", "n_glb"):
        g.add_node(ResourceNode(rid, rid, url=f"{rid}.glb"))
    g.add_edge("a", "M_model", "m_blend", "has_linked_resource")
    g.add_edge("b", "M_model", "m_glb", "has_linked_resource")
    g.add_edge("c", "N_model", "n_glb", "has_linked_resource")
    results = [{"id": "m_blend", "state": "missing", "sha256": ""},
               {"id": "m_glb", "state": "on_node", "sha256": "sha256:" + "a" * 64},
               {"id": "n_glb", "state": "missing", "sha256": ""}]
    assert fs.model_states(g, results) == {"M_model": "on_node", "N_model": "missing"}
    assert fs.best_state(["missing", "on_disk", "on_node"]) == "on_disk"
    assert fs.best_state([]) is None

    saved = dict(fs.ULTIMI)
    try:
        fs.ULTIMI.update({"results": results, "models": fs.model_states(g, results)})
        assert fs.model_state("M_model") == "on_node"
        assert fs.model_state("E_model") is None          # no file: no sign
        # an object bound to a resource by its digest (promote / materialise)
        assert fs.model_state("", {"em_asset_sha256": "a" * 64}) == "on_node"
        assert fs.model_state("", {"em_resource_id": "n_glb"}) == "missing"
        assert fs.model_state("", {}) is None
    finally:
        fs.ULTIMI.clear()
        fs.ULTIMI.update(saved)


def test_the_count_of_the_files_is_said_as_filters_with_sign_count_and_word():
    chips = fs.filter_chips({"on_disk": 3, "on_node": 0, "missing": 5})
    assert chips == [("on_disk", "DISK_DRIVE", "● 3 on the disk"),
                     ("missing", "CANCEL", "✕ 5 missing")]
