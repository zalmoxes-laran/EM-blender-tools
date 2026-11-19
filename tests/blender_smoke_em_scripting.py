"""Headless smoke: ``em`` in Blender (MICRO-PL19, W16).

NOT a pytest test (needs bpy). The machine folders MUST be redirected into
/tmp, or the real ~/.s3dgraphy is written; ``em`` must be in the s3dgraphy
Blender loads (``PYTHONPATH=<s3Dgraphy>/src --python-use-system-env`` while the
bundled wheel is older than dev124)::

    D=/tmp/pl19-smoke; S3DGRAPHY_PROFILES_DIR=$D/profiles S3DGRAPHY_EXTENSIONS_DIR=$D/ext \\
    S3DGRAPHY_PLUGINS_DIR=$D/plugins EM_VOCABULARIES_DIR=$D/vocab S3DGRAPHY_PLUGINS_DATA_DIR=$D/pdata \\
    S3DGRAPHY_CONSOLE_DIR=$D/console PYTHONPATH=../s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python-exit-code 1 --python tests/blender_smoke_em_scripting.py

EM Tools is em's host at registration; a graph made active in EM Setup is
``em.graph``; the selection of a proxy is ``em.app.selection()`` and
``em.app.select`` selects it back; ``em.write`` is one step (the lists follow,
the DTC is there, the Log has it) and «Undo» gives it back; ``view`` and the
camera without a 3D view say «not in blender»; a text run as an EM script keeps
its code; a plugin with ``hosts = blender`` installs with the tick, is drawn in
EM ▸ Plugin with «not verified», its command writes as the plugin, the
Preferences say «loaded in Blender»; turned off it leaves; the events; the
console's namespace; Italian.
"""
import importlib
import os
import sys
import textwrap
import uuid

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


for env in ("S3DGRAPHY_PROFILES_DIR", "S3DGRAPHY_EXTENSIONS_DIR", "S3DGRAPHY_PLUGINS_DIR", "EM_VOCABULARIES_DIR",
            "S3DGRAPHY_PLUGINS_DATA_DIR", "S3DGRAPHY_CONSOLE_DIR"):
    if not os.environ.get(env, "").startswith("/tmp"):
        print(f"[SMOKE] FAIL: {env} must point into /tmp (the real machine folders are not written)")
        sys.exit(1)
TMP = os.path.dirname(os.environ["S3DGRAPHY_PLUGINS_DIR"])

pkg = next((n.rsplit(".", 1)[0] for n in list(sys.modules)
            if n.startswith("bl_ext.") and n.endswith(".graph_updaters")), None)
if not check("addon loaded", pkg is not None and hasattr(bpy.ops, "emscript")
             and hasattr(bpy.ops.emscript, "undo")):
    sys.exit(1)
emc = importlib.import_module(pkg + ".em_scripting.core")
emb = importlib.import_module(pkg + ".em_scripting.blender")
ops = importlib.import_module(pkg + ".em_scripting.operators")
pui = importlib.import_module(pkg + ".community_packages.ui")
pcore = importlib.import_module(pkg + ".community_packages.core")
helpers = importlib.import_module(pkg + ".operators.addon_prefix_helpers")

from s3dgraphy import em  # noqa: E402

if not check("em is here", emc.available(), "(PYTHONPATH with s3Dgraphy/src?)"):
    sys.exit(1)
check("EM Tools is em's host", em.host.current() is emb.HOST and em.host.current().name == "blender",
      repr(em.host.current()))


class Rec:
    def __init__(self, calls): self.calls = calls
    def _c(self, *a, **k): return Rec(self.calls)
    column = row = box = split = _c
    alert = False
    enabled = True
    def label(self, **k): self.calls.append(k.get("text", ""))
    def prop(self, data, name, **k): self.calls.append(f"prop:{name}")
    def menu(self, *a, **k): self.calls.append(f"menu:{a[0] if a else ''}")
    def operator(self, idname, **k):
        self.calls.append(f"op:{idname}:{k.get('text', '')}")
        return type("OpProps", (), {})()
    def separator(self, **k): pass


# ── a graph made active in EM Setup ─────────────────────────────────────────
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402

scene = bpy.context.scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
g = Graph(graph_id="smoke_pl19")
for i in (1, 2, 3):
    g.add_node(StratigraphicUnit(f"us{i}", f"USM0{i}", description="" if i == 2 else "described"))
g.add_edge("e12", "us1", "us2", "is_after")
multi_graph_manager.graphs["smoke_pl19"] = g
em_tools = scene.em_tools
em_tools.graphml_files.clear()
em_tools.graphml_files.add().name = "smoke_pl19"
em_tools.active_file_index = 0
# the author is the Preferences' declared iD (no room here)
emb.author = lambda: "0000-0002-1825-0097"          # noqa: E731 — no preferences in -b
emb.HOST._author = emb.author

check("em.graph is the active graph", em.graph.node("USM02").id == "us2")

# proxies, named as EM Tools names them
for i in (1, 2):
    name = helpers.node_name_to_proxy_name(f"USM0{i}", context=bpy.context, graph=g)
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
bpy.context.view_layer.update()

# ── em.app: the selection ───────────────────────────────────────────────────
em.app.select(["us1"])
check("em.app.select selects the proxy", [o.name for o in bpy.data.objects if o.select_get()]
      == [helpers.node_name_to_proxy_name("USM01", context=bpy.context, graph=g)])
check("em.app.selection() reads it back", em.app.selection() == ["us1"], str(em.app.selection()))

seen = []
em.on("selection-changed", lambda p: seen.append(p["ids"]))
em.app.select(["us2"])
emb._on_depsgraph(scene)
check("selection-changed told", seen and seen[-1] == ["us2"], str(seen))

# the startup file has a 3D view even in -b: the camera goes and comes back in the scene's frame
cam = {"pos": [1.0, 2.0, 5.0], "target": [0.0, 1.0, 0.0]}
em.app.space.set_camera(cam)
back = em.app.space.camera()
check("the camera, set and read back (EMStudio's {pos, target})",
      all(abs(a - b) < 1e-4 for k in ("pos", "target") for a, b in zip(back[k], cam[k])), str(back))
for feature, call in (("view", lambda: em.app.view("graph")),
                      ("space.pick", lambda: em.app.space.pick("a point"))):
    try:
        call()
        check(f"em.app.{feature} says it does not exist here", False)
    except em.NotAvailable as exc:
        check(f"em.app.{feature} says it does not exist here", "blender" in exc.messages["en"], str(exc))

# ── em.write: one step, the lists follow, the DTC, the Log; Undo ────────────
changed = []
em.on("graph-changed", lambda p: changed.append(p["label"]))
with em.write("Described in Blender") as tx:
    tx.update("us2", "description", "now described")
    tx.add_node("US", "USM09")
check("the write is in the graph", g.find_node_by_id("us2").description == "now described"
      and g.find_node_by_name("USM09") is not None)
units = [u.name for u in em_tools.stratigraphy.units]
check("the lists follow the graph", "USM09" in units, str(units))
step = emb.HOST.steps[-1]
dtc = g.find_node_by_id(step.dtc)
check("one step with its DTC", len(emb.HOST.steps) == 1 and dtc is not None
      and dtc.data["parameters"]["host"] == "blender")
check("graph-changed told", changed == ["Described in Blender"], str(changed))
lines = ops.log_lines(emb.HOST)
check("the Log has the act", lines and "Described in Blender" in lines[0][0], str(lines[:1]))

calls = []
ops.EMSCRIPT_MT_plugins.draw(type("M", (), {"layout": Rec(calls)})(), bpy.context)
check("EM ▸ Plugin offers the undo", any("Undo «Described in Blender»" in c for c in calls), str(calls))
r = bpy.ops.emscript.undo()
check("Undo", r == {"FINISHED"} and not (g.find_node_by_id("us2").description or "")
      and g.find_node_by_name("USM09") is None and g.find_node_by_id(step.dtc) is None, str(r))
check("the lists follow the undo", "USM09" not in [u.name for u in em_tools.stratigraphy.units])

# ── a text run as an EM script ──────────────────────────────────────────────
code = 'with em.write("From the Text Editor") as tx:\n    tx.update("us3", "description", "scripted")\n'
out = ops.run_script(code, "smoke.py")
dtc = g.find_node_by_id(emb.HOST.steps[-1].dtc)
check("a script writes, its code in the DTC", out["ok"] and out["writes"] == 1
      and dtc.data["parameters"].get("code") == code, str(out))
bad = ops.run_script('with em.write("x") as tx:\n    tx.add_edge("us1", "is_after", "nobody")\n', "bad.py")
check("a failing script is said", not bad["ok"] and bad["error"], str(bad))
ns = ops.prepare_console({})
check("the console's namespace has em", ns.get("em") is em and "bpy" in ns)

# ── a plugin for Blender, installed with the tick ───────────────────────────
module = f"plug19_{uuid.uuid4().hex[:8]}"
pid = module.replace("_", "-")
folder = os.path.join(TMP, "src", f"{pid}-0.1.0")
os.makedirs(os.path.join(folder, module))
with open(os.path.join(folder, module, "__init__.py"), "w", encoding="utf-8") as f:
    f.write(textwrap.dedent('''
        from s3dgraphy import em


        def mark(slots):
            with em.write("Marked by the plugin") as tx:
                tx.update(slots["unit"], "description", "marked in Blender")


        def setup(ctx):
            ctx.command("mark", mark)
            ctx.command("export", lambda s: ctx.file("units.txt", "\\n".join(
                sorted(n.name for n in em.graph.nodes(type="US"))), "text/plain"))


        plugin = type("Plugin", (), {"setup": staticmethod(setup)})
    '''))
with open(os.path.join(folder, "LICENSE"), "w") as f:
    f.write("EUPL-1.2 (smoke)\n")
with open(os.path.join(folder, "em-extension.toml"), "w", encoding="utf-8") as f:
    f.write(f'''schema_version = "1.0.0"
id = "{pid}"
version = "0.1.0"
name = "A plugin for Blender (SMOKE)"
tagline = "A plugin of the smoke"
maintainer = "Smoke"
license = ["SPDX:EUPL-1.2"]
em_api_min = "1.0"
type = "plugin"
[code]
entry = "{module}:plugin"
hosts = ["blender"]
  [code.permissions]
  files = "Writes the file you choose"
  [code.descriptor]
  host = "app-side"
  transport = ["direct"]
  capabilities = ["read-graph", "write-graph"]
  provenance = "derivation"
  [[code.commands]]
  id = "mark"
  label = {{ it = "Segna l'unità", en = "Mark the unit" }}
  writes = true
  slots = [{{ name = "unit", kind = "id" }}]
  in = ["context.node@1"]
  when = "selection:US"
  [[code.commands]]
  id = "export"
  label = "Units as text"
  writes = false
  in = ["menu.file.export@1"]
''')

try:
    r = bpy.ops.empkg.confirm_install('EXEC_DEFAULT', source=folder)
except RuntimeError as exc:
    r = str(exc)
check("without the tick a plugin is refused", "tick" in str(r), str(r))
r = bpy.ops.empkg.confirm_install('EXEC_DEFAULT', source=folder, with_code=True)
check("with the tick it goes in", r == {"FINISHED"}, str(r))
p = em.plugins.get(pid)
check("loaded for Blender", p is not None and p.state == "loaded", str(p and p.problems))

em.app.select(["us2"])
calls = []
ops.EMSCRIPT_MT_plugins.draw(type("M", (), {"layout": Rec(calls)})(), bpy.context)
check("EM ▸ Plugin draws it, not verified",
      any("A plugin for Blender (SMOKE) 0.1.0 · not verified" == c for c in calls)
      and any(c.startswith("op:emscript.run_plugin_command:Mark the unit") for c in calls), str(calls))
r = bpy.ops.emscript.run_plugin_command('EXEC_DEFAULT', plugin=pid, command="mark")
step = emb.HOST.steps[-1]
check("its command writes as the plugin", r == {"FINISHED"}
      and g.find_node_by_id("us2").description == "marked in Blender"
      and step.plugin and step.plugin["id"] == pid and step.plugin["verified"] is False, str(r))
dtc = g.find_node_by_id(step.dtc)
check("the plugin in the DTC", dtc.data["parameters"].get("plugin") == pid
      and dtc.data["parameters"].get("command") == "mark")
out_file = os.path.join(TMP, "units.txt")
ops._pending_file[(pid, "export")] = {"name": "units.txt", "mime": "text/plain", "text": "USM01\nUSM02"}
r = bpy.ops.emscript.run_plugin_command('EXEC_DEFAULT', plugin=pid, command="export", saving=True,
                                        filepath=out_file)
check("an exporter's file saved where the person said", r == {"FINISHED"} and os.path.isfile(out_file))

calls = []
pui.draw_preferences(Rec(calls), bpy.context)
check("the Preferences: loaded in Blender", any("code: loaded in Blender, not verified" in c for c in calls),
      str([c for c in calls if "code" in c]))
r = bpy.ops.empkg.set_code_active(package_id=pid, active=False)
check("turned off, it leaves Blender", r == {"FINISHED"} and em.plugins.get(pid) is None)
r = bpy.ops.empkg.set_code_active(package_id=pid, active=True)
check("on again, it is back", em.plugins.get(pid) is not None and em.plugins.get(pid).state == "loaded")

# ── document events ─────────────────────────────────────────────────────────
saved = []
em.on("document-saved", lambda p: saved.append(p["path"]))
emb.document_marked("/tmp/pl19-smoke/x.em.json", True)
check("document-saved told", saved == ["/tmp/pl19-smoke/x.em.json"], str(saved))

# ── Italian ─────────────────────────────────────────────────────────────────
i18n = importlib.import_module(pkg + ".em_scripting.i18n")
prefs = bpy.context.preferences.view
prefs.language = 'it_IT'
prefs.use_translate_interface = True
check("Italian: Apri console EM", i18n.tr("Open EM console") == "Apri console EM", i18n.tr("Open EM console"))
check("Italian: the plugin's label", any(c.label == "Segna l'unità" for s in emc.menu_sections("it")
                                         for c in s.commands))
prefs.language = 'en_US'

em.plugins.reset()
print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
