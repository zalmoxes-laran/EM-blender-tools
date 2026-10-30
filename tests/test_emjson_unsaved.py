"""MICRO salva (17 Oct 2026) · a save that is found: the unsaved mark on the
em.json and the safety copy before an overwrite (bpy-free half; the Blender
half is tests/blender_smoke_save_emjson.py)."""

import datetime
import importlib.util
import pathlib
import re
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_CHECKOUT = _REPO.parent / "s3Dgraphy" / "src"
if _CHECKOUT.is_dir():
    sys.path.insert(0, str(_CHECKOUT))
pytest.importorskip("s3dgraphy.container")

from s3dgraphy.container import Container, save_container_file  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402

import emjson_state as st  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_emtools_graph_origins_salva", _REPO / "graph_origins.py")
go = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = go
_spec.loader.exec_module(go)


@pytest.fixture(autouse=True)
def _session():
    st.reset_session()
    go.forget_all()
    yield
    st.reset_session()


def _graph(gid, *units):
    g = Graph(graph_id=gid)
    for name in units:
        g.add_node(StratigraphicUnit(node_id=f"{gid}-{name}", name=name))
    return g


SURVEY = ("Survey2015", "", "", ("ME_EST_L_LOD2", "ME_PODIO_LOD2"))
RECON = ("Reconstruction II AC", "", "", ("Column_entrance1",))


# ── the fingerprint ─────────────────────────────────────────────────────────

def test_the_fingerprint_is_the_graph_as_written_and_it_moves_with_it():
    g = _graph("g", "US1", "US2")
    a = st.graph_digest(g)
    assert a == st.graph_digest(g), "the same graph, the same fingerprint"
    g.find_node_by_id("g-US1").description = "changed"
    b = st.graph_digest(g)
    assert b != a, "an attribute changed"
    g.add_node(StratigraphicUnit(node_id="g-US3", name="US3"))
    assert st.graph_digest(g) != b, "a node added"


def test_a_file_never_loaded_nor_saved_here_says_nothing():
    assert st.unsaved("/nowhere/x.em.json", {"g": _graph("g", "US1")}) == []


def test_after_a_load_the_mark_is_off_until_the_graph_moves(tmp_path):
    path = str(tmp_path / "x.em.json")
    g = _graph("g", "US1")
    st.mark_saved(path, {"g": g}, (), saved=False)
    assert st.unsaved(path, {"g": g}) == []
    g.add_node(StratigraphicUnit(node_id="g-US2", name="US2"))
    assert st.unsaved(path, {"g": g}) == ["the graph changed"]
    st.mark_saved(path, {"g": g}, ())
    assert st.unsaved(path, {"g": g}) == [], "saved: the mark is off"


def test_containers_not_in_the_file_are_unsaved_after_a_load():
    """Templu Mare v3.2: the .blend has Survey2015 and the reconstruction,
    the file has no group — the mark is on as soon as the file is opened."""
    g = _graph("g", "US1")
    st.mark_saved("/p/x.em.json", {"g": g}, (SURVEY, RECON), saved=False)
    said = st.unsaved("/p/x.em.json", {"g": g}, (SURVEY, RECON))
    assert said == ["2 RM container(s) not yet in the em.json "
                    "(Reconstruction II AC, Survey2015)"]
    # the save projects them: each container gets its group
    projected = (SURVEY[:2] + ("rmgroup_Survey2015", SURVEY[3]),
                 RECON[:2] + ("rmgroup_Reconstruction_II_AC", RECON[3]))
    st.mark_saved("/p/x.em.json", {"g": g}, projected)
    assert st.unsaved("/p/x.em.json", {"g": g}, projected) == []


def test_a_container_the_save_left_out_is_accepted_then():
    """A container that concerns none of the file's graphs stays without a
    group after a save: it is not «unsaved» forever."""
    g = _graph("g", "US1")
    st.mark_saved("/p/x.em.json", {"g": g}, (SURVEY,))
    assert st.unsaved("/p/x.em.json", {"g": g}, (SURVEY,)) == []


def test_a_container_changed_after_the_save_is_unsaved():
    g = _graph("g", "US1")
    projected = SURVEY[:2] + ("rmgroup_Survey2015", SURVEY[3])
    st.mark_saved("/p/x.em.json", {"g": g}, (projected,))
    one_more = projected[:3] + (projected[3] + ("ME_PRATO_LOD2",),)
    assert st.unsaved("/p/x.em.json", {"g": g}, (one_more,)) == ["RM containers changed"]


# ── the safety copy ─────────────────────────────────────────────────────────

def test_the_safety_copy_once_per_session_beside_the_file(tmp_path):
    f = tmp_path / "x.em.json"
    assert st.safety_copy(str(f)) is None, "no file yet: nothing to keep"
    f.write_text("one")
    when = datetime.datetime(2026, 10, 17, 15, 30, 5)
    copy = st.safety_copy(str(f), when)
    assert copy == str(f) + ".bak-20261017-153005"
    assert pathlib.Path(copy).read_text() == "one"
    f.write_text("two")
    assert st.safety_copy(str(f), when) is None, "one per session"
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "x.em.json", "x.em.json.bak-20261017-153005"]


def test_the_safety_copy_never_overwrites_another(tmp_path):
    f = tmp_path / "x.em.json"
    f.write_text("now")
    when = datetime.datetime(2026, 10, 17, 15, 30, 5)
    (tmp_path / "x.em.json.bak-20261017-153005").write_text("older")
    copy = st.safety_copy(str(f), when)
    assert copy.endswith(".bak-20261017-153005-2")
    assert (tmp_path / "x.em.json.bak-20261017-153005").read_text() == "older"


def test_save_file_keeps_the_previous_file_on_the_first_overwrite(tmp_path):
    f = tmp_path / "A.em.json"
    save_container_file(Container(graphs={"g": _graph("g", "US1")},
                                  active_graph_id="g"), str(f))
    before = f.read_bytes()
    live = {"g": _graph("g", "US1", "US2")}
    r1 = go.save_file(str(f), ["g"], live.get)
    assert r1.backup and pathlib.Path(r1.backup).read_bytes() == before
    assert "the previous file kept as A.em.json.bak-" in r1.sentence()
    r2 = go.save_file(str(f), ["g"], live.get)
    assert r2.backup == "" and "kept as" not in r2.sentence()
    assert len(list(tmp_path.glob("A.em.json.bak-*"))) == 1


def test_a_new_file_has_no_safety_copy(tmp_path):
    r = go.save_file(str(tmp_path / "new.em.json"), ["g"],
                     {"g": _graph("g", "US1")}.get)
    assert r.backup == "" and not list(tmp_path.glob("*.bak-*"))


# ── where the save is (the Blender side, read as source) ────────────────────

def _src(*parts):
    return (_REPO.joinpath(*parts)).read_text()


def test_the_save_has_words_beside_the_file_name():
    tree = _src("em_setup", "graph_tree.py")
    body = tree[tree.index("def draw_save_row("):tree.index("def room_alignment(")]
    # MICRO-EMTOOLS-PANNELLO (30 Oct 2026) · the words are the tooltips of
    # two icons ON the file's row, beside its name (Save lit when unsaved)
    assert '"export.em_save", text="", icon="FILE_TICK"' in body
    assert '"export.em_saveas", text="", icon="FILE_NEW"' in body
    assert "save.alert = bool(unsaved)" in body
    loop = tree[tree.index("def draw_graph_tree("):tree.index("def _unsaved_reasons(")]
    assert 'f"● {origin.label}" if unsaved' in loop, "the mark on the file's name"
    assert loop.index('text=f"● {origin.label}" if unsaved') < \
        loop.index("draw_save_row(right, origin, unsaved)"), "beside the name"
    assert '"Unsaved: "' not in loop, "the why is the name's tooltip"


def test_file_export_has_extended_matrix():
    src = _src("export_operators", "exporter_emjson.py")
    assert 'text="Extended Matrix (.em.json)"' in src
    assert "TOPBAR_MT_file_export.append(menu_func_export)" in src
    assert "TOPBAR_MT_file_export.remove(menu_func_export)" in src
    assert re.search(r'bl_idname = "export.em_save"\n    bl_label = "Save em.json"', src)


def test_saving_the_blend_only_warns():
    src = _src("em_setup", "unsaved.py")
    assert "bpy.app.handlers.save_post.append(on_blend_saved)" in src
    assert "status_text_set(line)" in src
    assert "Save em.json" in src
    assert "em_save(" not in src and "save_file(" not in src, "never a save"


def test_load_and_save_mark_the_file():
    assert "_mark_loaded(context, target_origin.path, saved=False)" in _src(
        "import_operators", "importer_emjson.py")
    assert "mark(context, origin.path)" in _src("em_setup", "graph_tree.py")
    assert "mark(context, out)" in _src("export_operators", "exporter_emjson.py")
