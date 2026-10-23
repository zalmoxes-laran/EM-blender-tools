"""Headless smoke · the georeferencing is written into the graph at every save
(MICRO georef al salvataggio, 24 Oct 2026), on a COPY of the GT16 (never the
OneDrive originals).

    EM_GEOREF_DIR=/tmp/emt-georef-save \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/emt-georef-save/SB/GreatTemple_2026_v2.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_georef_on_save.py

``$EM_GEOREF_DIR/EM/TempluMare_v4.em.json`` is the GT16 as corrected on 23 Oct
(EPSG:3844 · 327372.56 · 448682.65 · 0).

(1) opened in an empty scene, the azimuth edited, «Save em.json» → the file's
node says it, the shift exact, the node in «Graph paradata» once; reopened in an
empty scene: the same values. (2) the scene emptied → a save leaves the node as
it is. (3) a scene never aligned to the graph: «Save em.json» refuses, Keep
saves without writing it, Push writes the scene, Pull takes the graph; «Save
As…» refuses the same way. (4) the panel says what the next save does. (5) the
Heriverse package stops on the same discrepancy.
"""
import importlib
import json
import os
import sys
import types

import bpy

FAILURES = []
DIR = os.environ.get("EM_GEOREF_DIR", "/tmp/emt-georef-save")
EMJSON = os.path.join(DIR, "EM", "TempluMare_v4.em.json")
SAVEAS = os.path.join(DIR, "EM", "TempluMare_v4_saveas.em.json")
GT16 = ("3844", 327372.56, 448682.65, 0.0)
OLD = ("31700", 327300.0, 448370.0, 500.0)


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


names = [n for n in sys.modules if n.endswith(".georef_manager.graph_sync")
         and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".georef_manager.graph_sync", 1)[0]
print("[SMOKE] package:", PKG)
gs = importlib.import_module(PKG + ".georef_manager.graph_sync")
panel_mod = importlib.import_module(PKG + ".georef_manager.panel")


class StubLayout:
    """Records what a draw asks for (no region in -b)."""

    def __init__(self, calls):
        self.calls = calls
        self.alert = False
        self.enabled = True
        self.scale_y = 1.0

    def _child(self, *a, **k):
        return StubLayout(self.calls)

    box = row = column = split = _child

    def panel(self, *a, **k):
        return StubLayout(self.calls), None

    def prop(self, data, name, **k):
        self.calls.append(("prop", name))

    def prop_enum(self, data, name, value, **k):
        self.calls.append(("prop_enum", value))

    def prop_search(self, *a, **k):
        self.calls.append(("prop_search", a[1] if len(a) > 1 else ""))

    def label(self, **k):
        self.calls.append(("label", k.get("text", "")))

    def operator(self, idname, **k):
        self.calls.append(("operator", idname, k.get("text", "")))
        return types.SimpleNamespace()

    def separator(self, *a, **k):
        pass


def panel_lines():
    calls = []
    panel_mod.EM_PT_georef.draw(types.SimpleNamespace(layout=StubLayout(calls)),
                                bpy.context)
    return [c[1] for c in calls if c[0] == "label"]


def scene_tuple():
    g = bpy.context.scene.em_georef
    x, y, z = gs.exact_shift(g)
    return (g.epsg, x, y, z)


def file_geo(path=EMJSON):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    for gid, gd in doc["graphs"].items():
        if gid == "shelf":
            continue
        geo = [n for n in gd["nodes"] if n.get("node_type") == "geo_position"]
        if geo:
            edges = [e["id"] for e in gd["edges"]
                     if e.get("edge_type") == "is_in_paradata_nodegroup"
                     and e.get("source") == geo[0]["id"]]
            data = {k: v for k, v in geo[0]["data"].items() if k != "field_clocks"}
            return data, edges
    return None, []


def empty_scene(clear_rows=True):
    g = bpy.context.scene.em_georef
    g.epsg = ""
    gs.set_shift(g, 0.0, 0.0, 0.0)
    g.rotation = 0.0
    g.graph_note = ""
    if clear_rows:
        bpy.context.scene.em_tools.graphml_files.clear()
        bpy.context.scene.em_tools.active_file_index = -1
        g.reference_graph = ""


def load():
    return getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)


scene = bpy.context.scene
g = scene.em_georef
print("[SMOKE] the blend at opening:", scene_tuple(),
      [(r.name, r.graphml_path) for r in scene.em_tools.graphml_files])
before_file, before_edges = file_geo()
print("[SMOKE] the file before:", before_file, before_edges)

# ── (1) save → reopen ────────────────────────────────────────────────────────
empty_scene()
g.graph_agreed = ""
check("em.json loaded", load() == {"FINISHED"})
check("adopted on opening", scene_tuple() == GT16, str(scene_tuple()))
gid = gs.scene_graph_id(scene)
check("the opening is remembered as an agreement",
      gid in json.loads(g.graph_agreed or "{}"), g.graph_agreed[:120])
g.rotation = 12.5                                   # an edit in the panel
lines = panel_lines()
check("the panel says the next save writes it",
      any(l.startswith("The scene changed since it agreed") for l in lines),
      str([l for l in lines if "save" in l]))
r = bpy.ops.export.em_save()
data, edges = file_geo()
check("Save em.json", r == {"FINISHED"}, str(r))
check("the file says the azimuth", data.get("rotation") == 12.5, str(data))
check("the shift exact in the file (448682.65, not 448682.65625)",
      (data.get("epsg"), data.get("shift_x"), data.get("shift_y"), data.get("shift_z"))
      == (3844, 327372.56, 448682.65, 0), str(data))
check("the node in Graph paradata once", len(edges) == 1, str(edges))
empty_scene()
check("reloaded", load() == {"FINISHED"})
check("reopened: the same values", scene_tuple() == GT16 and g.rotation == 12.5,
      f"{scene_tuple()} rot {g.rotation}")

# ── (2) an empty scene leaves the node as it is ─────────────────────────────
saved_data, _ = file_geo()
empty_scene(clear_rows=False)
r = bpy.ops.export.em_save()
data, edges = file_geo()
check("an empty scene saves", r == {"FINISHED"}, str(r))
check("and the node is unchanged", data == saved_data, f"{data} vs {saved_data}")

# ── (3) a scene never aligned to the graph ──────────────────────────────────
empty_scene()
g.graph_agreed = ""                       # a .blend that never met this graph
g.epsg = OLD[0]
gs.set_shift(g, *OLD[1:])
check("reloaded over the other values", load() == {"FINISHED"})
check("nothing overwritten on opening", scene_tuple() == OLD, str(scene_tuple()))
lines = panel_lines()
check("the panel says a save asks first",
      any(l.startswith("Never aligned to these values") for l in lines),
      str([l for l in lines if "save" in l]))
mtime = os.path.getmtime(EMJSON)
with open(EMJSON, "rb") as f:
    blob = f.read()
r = bpy.ops.export.em_save()
with open(EMJSON, "rb") as f:
    same_bytes = f.read() == blob
check("Save without a choice: refused", r == {"CANCELLED"}, str(r))
check("the file is not written", same_bytes and os.path.getmtime(EMJSON) == mtime)
check("the scene untouched", scene_tuple() == OLD)
r = bpy.ops.export.em_saveas(filepath=SAVEAS)
check("Save As without a choice: refused", r == {"CANCELLED"}
      and not os.path.exists(SAVEAS), str(r))

r = bpy.ops.export.em_save(georef="KEEP")
data, _ = file_geo()
check("Keep: saved", r == {"FINISHED"}, str(r))
check("Keep: the node keeps the graph's values", data.get("epsg") == 3844
      and data.get("shift_z") == 0, str(data))
check("Keep: the scene keeps its own", scene_tuple() == OLD)
check("Keep: the next save still asks", bpy.ops.export.em_save() == {"CANCELLED"})

r = bpy.ops.export.em_save(georef="PULL")
data, _ = file_geo()
check("Pull: saved", r == {"FINISHED"}, str(r))
check("Pull: the scene takes the graph's", scene_tuple()[:4] == GT16, str(scene_tuple()))
check("Pull: the node unchanged", data.get("epsg") == 3844 and data.get("shift_y") == 448682.65)

g.graph_agreed = ""
g.epsg = OLD[0]
gs.set_shift(g, *OLD[1:])
r = bpy.ops.export.em_saveas(filepath=SAVEAS, georef="PUSH")
data, edges = file_geo(SAVEAS)
check("Save As with Push: saved", r == {"FINISHED"} and os.path.exists(SAVEAS), str(r))
check("Push: the file says the scene's", (data.get("epsg"), data.get("shift_x"),
      data.get("shift_y"), data.get("shift_z")) == (31700, 327300.0, 448370.0, 500.0),
      str(data))
check("Push: once in Graph paradata", len(edges) == 1, str(edges))
check("after Push no question", bpy.ops.export.em_save() == {"FINISHED"})

# ── (5) the Heriverse package stops on the same discrepancy ─────────────────
g.graph_agreed = ""
g.epsg = GT16[0]
gs.set_shift(g, *GT16[1:])
try:
    r = bpy.ops.em.deck_heriverse_write_disk(folder=os.path.join(DIR, "pkg_out"))
    print("[SMOKE] package with a discrepancy:", r)
    check("the package does not go out on a discrepancy", r == {"CANCELLED"}, str(r))
except Exception as exc:  # noqa: BLE001 — an operator error reports
    print("[SMOKE] package:", exc)
    check("the package does not go out on a discrepancy",
          "differ" in str(exc) or "publishable" in str(exc) or "version" in str(exc),
          str(exc)[:300])

print(f"[SMOKE] DONE: {len(FAILURES)} failure(s)", FAILURES)
