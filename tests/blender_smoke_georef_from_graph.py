"""Headless smoke · the Georeferencing panel reads the graph (MICRO georiferimento
dal grafo, 23 Oct 2026), on a COPY of the GT16 (never the OneDrive originals).

    EM_GEOREF_DIR=/tmp/emt-georef \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/emt-georef/SB/GreatTemple_2026_v2.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_georef_from_graph.py

``$EM_GEOREF_DIR/EM/TempluMare_v4.em.json`` is the GT16 as corrected on 23 Oct
(EPSG:3844 · 327372.56 · 448682.65 · 0); ``TempluMare_v4_31700.em.json`` (made
by this smoke if missing) is the same graph declaring the deprecated 31700.

(1) the blend opens with an empty panel; the em.json is loaded: the scene takes
the graph's values, BlenderGIS and 3DSC receive them, no object moves, the
panel says it; (2) a scene with other values: nothing overwritten, the panel
lists scene vs graph, «Pull from graph» makes them agree; (3) «Push to GeoNode»
links the node to «Graph paradata», once, and «Save em.json» writes the edge;
(4) shift Z: the models carry their heights, Z 0 adds nothing; (5) the 31700
graph: the proposal, «Convert to EPSG:3844», its undo (when present).
"""
import importlib
import json
import os
import shutil
import sys
import types

import bpy

FAILURES = []
DIR = os.environ.get("EM_GEOREF_DIR", "/tmp/emt-georef")
EMJSON = os.path.join(DIR, "EM", "TempluMare_v4.em.json")
EMJSON_31700 = os.path.join(DIR, "EM", "TempluMare_v4_31700.em.json")
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
bgis = importlib.import_module(PKG + ".georef_manager.bgis_adapter")
dsc = importlib.import_module(PKG + ".georef_manager.dsc_adapter")


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

    def prop_search(self, *a, **k):
        self.calls.append(("prop_search", a[1] if len(a) > 1 else ""))

    def label(self, **k):
        self.calls.append(("label", k.get("text", "")))

    def operator(self, idname, **k):
        self.calls.append(("operator", idname, k.get("text", "")))
        return types.SimpleNamespace()

    def separator(self, *a, **k):
        pass


def draw_panel():
    calls = []
    panel_mod.EM_PT_georef.draw(types.SimpleNamespace(layout=StubLayout(calls)),
                                bpy.context)
    return calls


def labels(calls):
    return [c[1] for c in calls if c[0] == "label"]


def ops(calls):
    return [c[1] for c in calls if c[0] == "operator"]


def scene_tuple():
    """The scene's values with the EXACT shift (the fields are float32)."""
    g = bpy.context.scene.em_georef
    x, y, z = gs.exact_shift(g)
    return (g.epsg, round(x, 3), round(y, 3), round(z, 3))


def world_z_range(objs):
    lo, hi = float("inf"), float("-inf")
    for o in objs:
        for c in o.bound_box:
            z = (o.matrix_world @ __import__("mathutils").Vector(c)).z
            lo, hi = min(lo, z), max(hi, z)
    return lo, hi


scene = bpy.context.scene
g = scene.em_georef

# ── (0) the blend as it opens ─────────────────────────────────────────────────
print("[SMOKE] at opening:", scene_tuple(), "rows:",
      [(r.name, r.graphml_path) for r in scene.em_tools.graphml_files])
meshes = [o for o in scene.objects if o.type == "MESH"]
before = {o.name: tuple(o.matrix_world.translation) for o in meshes}
zr = world_z_range(meshes[:400])
print(f"[SMOKE] meshes: {len(meshes)}; world Z of the first 400: {zr[0]:.2f} … {zr[1]:.2f}")
print("[SMOKE] BGIS available:", bgis.is_available(), "3DSC available:", dsc.is_available())
print("[SMOKE] BGIS before:", bgis.read_state(scene), "3DSC before:", dsc.read_state(scene))

# the opening state, emptied as the MICRO measured it (EPSG empty, shift 0)
g.epsg = ""
g.shift_x = g.shift_y = g.shift_z = 0.0
g.rotation = 0.0
g.graph_note = ""
# the copy's rows, not OneDrive's: the scene's graph rows are cleared so the
# em.json loaded here is the first (the reference) graph
scene.em_tools.graphml_files.clear()
scene.em_tools.active_file_index = -1
g.reference_graph = ""

# ── (1) loading the em.json: the scene takes the graph's values ──────────────
r = getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)
check("em.json loaded", r == {"FINISHED"}, str(r))
check("the scene took the graph's georeferencing", scene_tuple() == GT16, str(scene_tuple()))
print("[SMOKE] fields (float32):", g.shift_x, g.shift_y, "exact:", g.shift_exact)
check("the panel line says it", g.graph_note.startswith("Georeferencing read from graph"),
      repr(g.graph_note))
if bgis.is_available():
    st = bgis.read_state(scene)
    check("BlenderGIS received EPSG and shift", st and st["epsg"] == "3844"
          and abs(st["shift_x"] - GT16[1]) < 1e-3 and abs(st["shift_y"] - GT16[2]) < 1e-3, str(st))
if dsc.is_available():
    st = dsc.read_state(scene)
    # 3DSC keeps the shift in 32-bit floats (its own FloatProperty)
    check("3DSC received EPSG and shift (Z 0, at 32-bit)", st and st["epsg"] == "3844"
          and gs._f32(st["shift_x"]) == gs._f32(GT16[1]) and st["shift_z"] == 0.0, str(st))
moved = [n for n, t in before.items()
         if n in scene.objects and tuple(scene.objects[n].matrix_world.translation) != t]
check("no object moved", not moved, f"{len(moved)} moved {moved[:5]}")
calls = draw_panel()
check("panel draws the line", any(l.startswith("Georeferencing read from graph") for l in labels(calls)))
check("panel offers Pull from graph next to Push", "em.georef_pull_graph" in ops(calls)
      and "em.georef_push_geonode" in ops(calls))
check("no discrepancy shown when they agree",
      not any("differ" in l for l in labels(calls)))

# ── (4) shift Z: the heights stay those of the vertices ──────────────────────
zr2 = world_z_range(meshes[:400])
check("models keep their heights (Z 0 adds nothing)", abs(zr2[0] - zr[0]) < 1e-6
      and abs(zr2[1] - zr[1]) < 1e-6, f"{zr2[0]:.2f} … {zr2[1]:.2f}")

# ── (2) a scene with other values: nothing overwritten, then the pull ───────
g.epsg, g.shift_x, g.shift_y, g.shift_z = OLD[0], OLD[1], OLD[2], OLD[3]
g.graph_note = ""
r = getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)
check("em.json reloaded over a different scene", r == {"FINISHED"}, str(r))
check("nothing overwritten", scene_tuple() == OLD, str(scene_tuple()))
check("the panel line says they differ", "differ" in g.graph_note, repr(g.graph_note))
calls = draw_panel()
lines = labels(calls)
print("[SMOKE] panel lines:", [l for l in lines if "scene" in l or "differ" in l])
check("EPSG scene vs graph listed", "EPSG: scene EPSG:31700 · graph EPSG:3844" in lines)
check("Shift Z scene vs graph listed", "Shift Z: scene 500.000 · graph 0.000" in lines)
r = bpy.ops.em.georef_pull_graph()           # exec: the confirm is invoke's
check("Pull from graph", r == {"FINISHED"}, str(r))
check("after the pull the scene is the graph's", scene_tuple() == GT16, str(scene_tuple()))
check("no discrepancy after the pull",
      not any(l.startswith("Scene and graph differ") for l in labels(draw_panel())))

# ── (3) push links the node to «Graph paradata», once; the save writes it ───
graph = gs.get_active_graph()
node = gs.get_geo_node(graph)


def geo_edges(gr):
    return [e for e in gr.edges if e.edge_source == node.node_id
            and e.edge_type == "is_in_paradata_nodegroup"]


print("[SMOKE] geo edges before push:", [e.edge_id for e in geo_edges(graph)])
r = bpy.ops.em.georef_push_geonode()
check("Push to GeoNode", r == {"FINISHED"}, str(r))
r = bpy.ops.em.georef_push_geonode()
edges = geo_edges(graph)
check("linked to Graph paradata once", len(edges) == 1
      and graph.find_node_by_id(edges[0].edge_target).name == "Graph paradata",
      str([e.edge_id for e in edges]))
try:
    r = getattr(bpy.ops, "export").em_save()
    with open(EMJSON, encoding="utf-8") as f:
        doc = json.load(f)
    gdoc = doc["graphs"][graph.graph_id]
    ids = [e["id"] for e in gdoc["edges"] if e.get("edge_type") == "is_in_paradata_nodegroup"
           and e.get("source") == node.node_id]
    geo = [n for n in gdoc["nodes"] if n.get("node_type") == "geo_position"][0]["data"]
    check("Save em.json writes the edge once", r == {"FINISHED"} and len(ids) == 1, f"{r} {ids}")
    check("and the values", geo.get("epsg") == 3844 and geo.get("shift_z") == 0, str(geo)[:200])
except Exception as exc:  # noqa: BLE001
    check("Save em.json", False, repr(exc))

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
