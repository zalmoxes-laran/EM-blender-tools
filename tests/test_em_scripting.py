"""MICRO-PL19 (row W16 of the extensions plan, E.D. 18 Nov 2026): ``em`` in
Blender, measured without Blender — ``em_scripting/core.py`` and ``i18n.py``
(no bpy) on plain s3Dgraphy graphs, the machine folders in tmp.

What is defended:

* EM Tools' host: ``em.write`` on the active graph is ONE step — the seam, the
  author of the session (never an argument), a ``dtc_process`` node naming the
  console, the script (with its code, D-8) or the plugin (unverified), a line
  in the Log, ``graph-changed``, the add-on told (``after_apply``);
* «Undo»: the inverse act through the seam gives back the graph as it was —
  fields, added nodes, removed nodes WITH their relations;
* ``em.app`` in Blender: ``view`` and ``pick`` do not exist and say so in EN
  and IT; the camera as EMStudio's ``{pos, target}`` in the scene's frame;
* the plugins: one with ``hosts = blender`` is loaded for Blender and drawn in
  EM ▸ Plugin with its mark, ``when`` held against the selection; its command
  writes AS THE PLUGIN; one for EMStudio only is not here;
* what goes to a room: every operation of an act is one the library sends;
* the Preferences: a code for Blender can go in with the tick (trust), and be
  turned off and on.
"""
import importlib.util
import json
import os
import pathlib
import sys
import textwrap
import uuid

import pytest

pytest.importorskip("s3dgraphy.em.plugins")

from s3dgraphy import em  # noqa: E402
from s3dgraphy.em import plugins as PL  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402

_REPO = pathlib.Path(__file__).resolve().parent.parent
ORCID = "0000-0002-1825-0097"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, _REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


C = _load("pl19_core", "em_scripting/core.py")
I18N = _load("pl19_i18n", "em_scripting/i18n.py")
PK = _load("pl19_packages", "community_packages/core.py")


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    for env, sub in (("S3DGRAPHY_PROFILES_DIR", "profiles"), ("S3DGRAPHY_EXTENSIONS_DIR", "extensions"),
                     ("S3DGRAPHY_PLUGINS_DIR", "plugins"), ("EM_VOCABULARIES_DIR", "vocab"),
                     ("S3DGRAPHY_PLUGINS_DATA_DIR", "plugins-data"), ("S3DGRAPHY_CONSOLE_DIR", "console")):
        monkeypatch.setenv(env, str(tmp_path / sub))
    monkeypatch.delenv("S3DGRAPHY_PLUGINS_DEV_DIR", raising=False)
    from s3dgraphy.authorities import packages as pk
    pk._changed()
    em.host.uninstall()
    em.events.clear()
    PL.reset()
    yield
    PL.reset()
    em.host.uninstall()
    em.events.clear()


def _graph():
    g = Graph(graph_id="g19")
    g.add_node(StratigraphicUnit("US1", "US1", description="described"))
    g.add_node(StratigraphicUnit("US2", "US2"))
    g.add_node(StratigraphicUnit("US3", "US3"))
    g.add_edge("e1", "US1", "US2", "is_after")
    return g


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, step, delta, result):
        self.calls.append((step, delta, result))


def host(g=None, *, author=ORCID, app=None):
    g = g if g is not None else _graph()
    rec = Recorder()
    h = C.BlenderHost(graph=lambda: g, author=lambda: author, language=lambda: "en",
                      app=app, after_apply=rec, addon_version="1.6.0-test")
    em.host.install(h)
    h.rec = rec
    h.g = g
    return h


def dtc_nodes(g):
    return [n for n in g.nodes if getattr(n, "node_type", "") == "dtc_process"]


def params_of(node):
    return (getattr(node, "data", None) or {}).get("parameters") or {}


# ── the sentences ───────────────────────────────────────────────────────────

def test_every_sentence_has_its_italian_and_keeps_its_placeholders():
    import re
    for msgid, by in I18N.MESSAGES.items():
        assert by.get("it_IT"), msgid
        assert sorted(re.findall(r"\{(\w+)\}", by["it_IT"])) == sorted(re.findall(r"\{(\w+)\}", msgid)), msgid
    for s in I18N.AUTO:
        assert s in I18N.MESSAGES, s
    it = I18N.catalogue("it_IT")
    assert I18N.translate("Undo «Marked»", it) == "Annulla «Marked»"
    assert I18N.translate("Open EM console", it) == "Apri console EM"


def test_the_new_package_sentences_have_their_italian():
    pk_i18n = _load("pl19_pk_i18n", "community_packages/i18n.py")
    missing = [m for m, by in pk_i18n.MESSAGES.items() if not by.get("it_IT")]
    assert missing == []
    it = pk_i18n.catalogue("it_IT")
    assert pk_i18n.translate("code: loaded in Blender, not verified", it) == "codice: caricato in Blender, non verificato"


# ── the host ────────────────────────────────────────────────────────────────

def test_em_write_is_one_step_of_the_blender_host():
    h = host()
    seen = []
    em.on("graph-changed", lambda p: seen.append(p))
    assert em.host.current() is h and em.host.current().app is h.app
    with em.write("Described from Blender") as tx:
        tx.update("US2", "description", "now described")
        tx.add_node("US", "US9")
        tx.add_edge("US9", "is_after", "US3")
    assert h.g.find_node_by_id("US2").description == "now described"
    assert h.g.find_node_by_name("US9") is not None
    # one step, one DTC, one line, the add-on told once, one event
    assert len(h.steps) == 1 and len(h.rec.calls) == 1 and len(seen) == 1
    step = h.steps[0]
    assert step.label == "Described from Blender" and step.caller == C.CONSOLE_CALLER
    assert step.author == ORCID
    [dtc] = dtc_nodes(h.g)
    assert dtc.node_id == step.dtc
    p = params_of(dtc)
    assert p["host"] == "blender" and p["source"] == "Python console"
    assert "US2" in p["touched"]
    # the stamps are the session's author's
    assert "0000-0002-1825-0097" in str(h.g.find_node_by_name("US9").data.get("created_by", ""))


def test_the_author_is_the_sessions_and_without_it_nothing_is_written():
    h = host(author=None)
    before = C.snapshot(h.g)
    with pytest.raises(em.Refused) as err:
        with em.write("No author") as tx:
            tx.update("US1", "description", "x")
    assert "verificata" in err.value.messages["it"]
    assert C.snapshot(h.g) == before and h.steps == []


def test_no_active_graph_is_said_in_both_languages():
    h = C.BlenderHost(graph=lambda: None, author=lambda: ORCID)
    res = h.apply(__import__("s3dgraphy.contract", fromlist=["Delta"]).Delta(author=ORCID),
                  descriptor=C.console_caller(), capability="write-graph", label="x")
    assert not res.ok and "EM Setup" in res.data["messages"]["en"] and "EM Setup" in res.data["messages"]["it"]


def test_undo_gives_the_graph_back():
    h = host()
    start = C.snapshot(h.g)
    with em.write("Many things") as tx:
        tx.update("US1", "description", "changed")
        tx.clear("US1", "description")
        tx.update("US3", "name", "US3bis")
        tx.add_node("US", "US10")
        tx.add_edge("US10", "is_after", "US2")
        tx.remove_edge("US1", "is_after", "US2")
    assert C.snapshot(h.g) != start
    step, res = h.undo()
    assert res.ok and step.undone
    nodes, edges = C.snapshot(h.g)
    assert edges == start[1]
    # the DTC of the act goes with it (it was added by the act)
    assert nodes == start[0]
    assert h.last_undoable() is None
    assert len(h.rec.calls) == 2 and h.rec.calls[1][0].label == "undo: Many things"


def test_undo_of_a_removal_brings_the_node_back_with_its_relations():
    h = host()
    start = C.snapshot(h.g)
    with em.write("Remove US1") as tx:
        tx.remove("US1")
    assert h.g.find_node_by_id("US1") is None
    assert not any(e.edge_source == "US1" for e in h.g.edges)
    h.undo()
    assert h.g.find_node_by_id("US1") is not None
    nodes, edges = C.snapshot(h.g)
    assert edges == start[1]
    # the seam gives a text node born again the study's language (``und`` here):
    # the one difference from the node as it was (said in the report)
    assert nodes["US1"]["data"].pop("lang") == "und"
    assert nodes == start[0]


def test_a_script_leaves_its_code_in_the_dtc(tmp_path):
    h = host()
    code = 'with em.write("From a text") as tx:\n    tx.update("US2", "description", "scripted")\n'
    ns = {"em": em}
    with h.running(code):
        exec(compile(code, "t.py", "exec"), ns)
    assert h.caller().name == C.CONSOLE_CALLER          # back to the console afterwards
    [dtc] = dtc_nodes(h.g)
    p = params_of(dtc)
    assert p["code"] == code and p["source"] == "Text Editor" and p["code_bytes"] == len(code)
    assert h.steps[-1].caller == C.SCRIPT_CALLER
    big = "# " + "x" * 5000 + "\n" + code.replace("scripted", "scripted again")
    with h.running(big):
        exec(compile(big, "big.py", "exec"), ns)
    p = params_of(next(n for n in dtc_nodes(h.g) if n.node_id == h.steps[-1].dtc))
    assert "code" not in p and p["code_sha256"] and os.path.isfile(p["code_ref"])


def test_a_proof_is_said_and_applied_nowhere():
    h = host()
    before = C.snapshot(h.g)
    res = em.write("Only a proof", dry_run=True)
    with res as tx:
        tx.update("US1", "description", "proved")
    assert C.snapshot(h.g) == before and h.steps == []
    assert h.proofs and h.proofs[-1]["label"] == "Only a proof"


def test_em_help_names_the_blender_host():
    host()
    assert "host: blender" in em.help("en")


# ── em.app ──────────────────────────────────────────────────────────────────

def test_view_and_pick_do_not_exist_in_blender_and_say_so():
    from s3dgraphy.em.host import NoApp
    host(app=NoApp("blender"))
    with pytest.raises(em.NotAvailable) as err:
        em.app.view("graph")
    assert "blender" in err.value.messages["en"] and "blender" in err.value.messages["it"]


def test_the_camera_is_emstudios_in_the_scenes_frame():
    # a view looking down Blender's −Y at a pivot 2 m above the origin, 5 m away
    cam = C.camera_state((0, 0, 2), (0, 1, 0), 5.0)
    # Blender (x, y, z) → scene (x, z, −y): the eye at Blender (0, −5, 2) → (0, 2, 5)
    assert cam == {"pos": [0.0, 2.0, 5.0], "target": [0.0, 2.0, -0.0]}
    target, forward, dist = C.view_of(cam)
    assert [round(v, 6) for v in target] == [0.0, 0.0, 2.0]
    assert [round(v, 6) for v in forward] == [0.0, 1.0, 0.0] and dist == pytest.approx(5.0)
    with pytest.raises(ValueError):
        C.view_of({"pos": [1, 1, 1], "target": [1, 1, 1]})
    with pytest.raises(ValueError):
        C.view_of({"target": [0, 0, 0]})


def test_slots_are_filled_from_what_blender_knows():
    slots = [{"name": "a", "kind": "id"}, {"name": "b", "kind": "id"}, {"name": "all", "kind": "ids"},
             {"name": "f", "kind": "path"}, {"name": "n", "kind": "number"}]
    assert C.fill_slots(slots, ["US1", "US2", "US3"], "/tmp/x") == {
        "a": "US1", "b": "US2", "all": ["US1", "US2", "US3"], "f": "/tmp/x"}
    assert C.fill_slots(slots, [], None) == {}
    assert C.wants_path(slots) and not C.wants_path(slots[:1])


# ── what goes to a room ─────────────────────────────────────────────────────

def test_every_operation_of_an_act_is_one_the_library_sends():
    from s3dgraphy import crdt
    h = host()
    with em.write("For the room") as tx:
        tx.update("US2", "description", "roomy")
        tx.add_node("US", "US11")
        tx.add_edge("US11", "is_after", "US3")
        tx.remove_edge("US1", "is_after", "US2")
    delta = h.rec.calls[0][1]
    ops = C.wire_ops(delta)
    kinds = sorted(o["op"] for o in ops)
    assert kinds.count("add_node") == 2              # the unit and the act's DTC
    assert {"add_edge", "update_field", "remove_edge"} <= set(kinds)
    for o in ops:
        assert crdt.ops_for_local_change(o)          # raises if the library would not send it
    assert C.structural(delta)


# ── the plugins ─────────────────────────────────────────────────────────────

COMMANDS = '''
  [[code.commands]]
  id = "mark"
  label = { it = "Segna l'unità", en = "Mark the unit" }
  writes = true
  slots = [{ name = "unit", kind = "id" }]
  in = ["context.node@1", "menu.tools@1"]
  when = "selection:US"
  [[code.commands]]
  id = "count"
  label = "Count"
  writes = false
  in = ["menu.tools@1"]
  [[code.commands]]
  id = "export"
  label = "Units as text"
  writes = false
  in = ["menu.file.export@1"]
'''

MODULE = '''
from s3dgraphy import em


def mark(slots):
    with em.write("Marked in Blender") as tx:
        tx.update(slots["unit"], "description", "marked by the plugin")
    return slots["unit"]


def setup(ctx):
    ctx.command("mark", mark)
    ctx.command("count", lambda s: len(list(em.graph.nodes(type="US"))))
    ctx.command("export", lambda s: ctx.file("units.txt", "US1", "text/plain"))


plugin = type("Plugin", (), {"setup": staticmethod(setup)})
'''


def write_plugin(tmp_path, *, hosts='["blender", "emstudio"]', caps='["read-graph", "write-graph"]'):
    module = f"plug19_{uuid.uuid4().hex[:8]}"
    pid = module.replace("_", "-")
    folder = tmp_path / "src" / f"{pid}-0.1.0"
    (folder / module).mkdir(parents=True)
    (folder / module / "__init__.py").write_text(textwrap.dedent(MODULE), encoding="utf-8")
    (folder / "LICENSE").write_text("EUPL-1.2 (test)\n", encoding="utf-8")
    (folder / "em-extension.toml").write_text(f'''schema_version = "1.0.0"
id = "{pid}"
version = "0.1.0"
name = "A plugin for Blender (TEST)"
tagline = "A plugin of the tests"
maintainer = "Tests"
license = ["SPDX:EUPL-1.2"]
em_api_min = "1.0"
type = "plugin"
[code]
entry = "{module}:plugin"
hosts = {hosts}
  [code.permissions]
  files = "Reads the file it is given"
  [code.descriptor]
  host = "app-side"
  transport = ["direct"]
  capabilities = {caps}
  provenance = "derivation"
{COMMANDS}''', encoding="utf-8")
    return pid, module, folder


def _forget(module):
    sys.modules.pop(module, None)
    PL._imported.pop(module, None)


def test_a_plugin_for_blender_installs_with_the_tick_and_runs_here(tmp_path):
    pid, module, folder = write_plugin(tmp_path)
    try:
        pv = PK.library()[1].preview(str(folder))
        assert PK.code_for_blender(pv)
        # without the tick a plugin with no data is refused, with the tick it goes in
        assert PK.plan_install(pv) == {"action": "refuse", "why": "plugin_needs_trust", "code_for_blender": True}
        assert PK.plan_install(pv, with_code=True)["action"] == "all"
        lines = [t for t, _i, _l in PK.preview_lines(pv, "en")]
        assert any("Install the code too" in t for t in lines)
        PK.install_with_code(str(folder))
        assert pid in PK.active_code_ids()

        h = host()
        got = PL.sync(C.HOST)
        assert [p.id for p in got] == [pid] and got[0].state == "loaded"
        # the menu: the mark, ``when`` against the selection
        [sec] = C.menu_sections("it", document=True, types=["US"])
        assert sec.badge == "not verified" and sec.name == "A plugin for Blender (TEST)"
        by = {c.id: c for c in sec.commands}
        assert by["mark"].label == "Segna l'unità" and by["mark"].enabled and by["mark"].writes
        assert by["export"].exporter and not by["count"].writes
        [sec] = C.menu_sections("en", document=True, types=["representation_model"])
        assert not {c.id: c for c in sec.commands}["mark"].enabled
        # the command writes AS THE PLUGIN, one step with the plugin in its DTC
        res = PL.invoke(pid, "mark", C.fill_slots([{"name": "unit", "kind": "id"}], ["US2"]),
                        author=h.author())
        assert res.ok, res.message
        assert h.g.find_node_by_id("US2").description == "marked by the plugin"
        step = h.steps[-1]
        assert step.plugin == {"id": pid, "version": "0.1.0", "source": "disk", "verified": False}
        p = params_of(next(n for n in dtc_nodes(h.g) if n.node_id == step.dtc))
        assert p["plugin"] == pid and p["command"] == "mark" and p["verified"] is False
        assert "plugin" in step.caller or pid in step.caller
        # «Undo» works on a plugin's act too
        h.undo()
        assert h.g.find_node_by_id("US2").description in (None, "")
        # turned off: gone from Blender; on again: back
        PK.set_code_active(pid, False)
        assert PL.sync(C.HOST) == [] and C.menu_sections() == []
        PK.set_code_active(pid, True)
        assert [p.id for p in PL.sync(C.HOST)] == [pid]
    finally:
        PL.reset()
        _forget(module)


def test_a_plugin_for_emstudio_only_is_not_in_blender(tmp_path):
    pid, module, folder = write_plugin(tmp_path, hosts='["emstudio"]')
    try:
        pv = PK.library()[1].preview(str(folder))
        assert not PK.code_for_blender(pv)
        assert PK.plan_install(pv, with_code=True) == {"action": "refuse", "why": "plugin_only",
                                                        "code_for_blender": False}
        lines = [t for t, _i, _l in PK.preview_lines(pv, "en")]
        assert any("does not run in Blender" in t for t in lines)
        PK.library()[1].install(str(folder), trust=True)        # as EMStudio would
        host()
        assert PL.sync(C.HOST) == [] and C.menu_sections() == []
    finally:
        PL.reset()
        _forget(module)


def test_a_plugin_without_write_graph_cannot_write_from_blender(tmp_path):
    pid, module, folder = write_plugin(tmp_path, caps='["read-graph"]')
    try:
        PK.install_with_code(str(folder))
        h = host()
        PL.sync(C.HOST)
        before = C.snapshot(h.g)
        res = PL.invoke(pid, "mark", {"unit": "US2"}, author=h.author())
        assert not res.ok
        assert C.snapshot(h.g) == before and h.steps == []
    finally:
        PL.reset()
        _forget(module)


def test_no_em_in_an_older_s3dgraphy_is_said(monkeypatch):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **kw):
        if name == "s3dgraphy" and a and a[2] and "em" in a[2]:
            raise ImportError("no em")
        return real(name, *a, **kw)
    monkeypatch.setattr(builtins, "__import__", fake)
    assert C.em_module() is None and not C.available() and C.menu_sections() == []
