"""Headless smoke: the community packages in EM Tools (MICRO-PL12, W9).

NOT a pytest test (needs bpy). The machine folders MUST be redirected, or the
real ~/.s3dgraphy is written::

    D=/tmp/pl12-smoke; S3DGRAPHY_PROFILES_DIR=$D/profiles S3DGRAPHY_EXTENSIONS_DIR=$D/ext \\
    S3DGRAPHY_PLUGINS_DIR=$D/plugins EM_VOCABULARIES_DIR=$D/vocab PL12_SRC=<copy of em-profiles/examples> \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-exit-code 1 \\
        --python tests/blender_smoke_community_packages.py

Installs esempio-statuaria-misto from disk (data only), draws the
Preferences box and the Visual Manager box on a recording layout, places the
face's canonical points and an infill surface with s3Dgraphy (as EMStudio
does), applies the package's colour scheme, takes a Proxy Box point from the
graph, shows the readings (the surface among them), makes an areale from the
graph surface on a plane RM, computes the package's measures, removes the
package (vocabularies stay), and reads two sentences in Italian.
"""
import importlib
import os
import sys

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


for env in ("S3DGRAPHY_PROFILES_DIR", "S3DGRAPHY_EXTENSIONS_DIR", "S3DGRAPHY_PLUGINS_DIR", "EM_VOCABULARIES_DIR"):
    if not os.environ.get(env, "").startswith("/tmp"):
        print(f"[SMOKE] FAIL: {env} must point into /tmp (the real machine folders are not written)")
        sys.exit(1)
SRC = os.environ["PL12_SRC"]

pkg = next((n.rsplit(".", 1)[0] for n in list(sys.modules)
            if n.startswith("bl_ext.") and n.endswith(".graph_updaters")), None)
if not check("addon loaded", pkg is not None and hasattr(bpy.ops.empkg, "confirm_install")):
    sys.exit(1)
core = importlib.import_module(pkg + ".community_packages.core")
ui = importlib.import_module(pkg + ".community_packages.ui")
i18n = importlib.import_module(pkg + ".community_packages.i18n")


class Rec:
    def __init__(self, calls): self.calls = calls
    def _c(self, *a, **k): return Rec(self.calls)
    column = row = box = split = _c
    alert = False
    def label(self, **k): self.calls.append(k.get("text", ""))
    def prop(self, data, name, **k): self.calls.append(f"prop:{name}")
    def operator(self, idname, **k):
        self.calls.append(f"op:{idname}")
        return type("OpProps", (), {})()
    def separator(self, **k): pass


scene = bpy.context.scene
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)

# ── install from disk, data only ────────────────────────────────────────────
r = bpy.ops.empkg.confirm_install('EXEC_DEFAULT', source=os.path.join(SRC, "esempio-statuaria-misto"))
check("installed", r == {"FINISHED"}, str(r))
rows = {x.id: x for x in core.package_rows()}
check("data in, code left out", "esempio-statuaria" in rows and rows["esempio-statuaria"].data == "installed"
      and rows["esempio-statuaria"].code == "not_installed")
try:
    r = bpy.ops.empkg.confirm_install('EXEC_DEFAULT', source=os.path.join(SRC, "facemesh_fit"))
except RuntimeError as exc:      # an operator that reports an ERROR raises in a script
    r = str(exc)
check("a plugin alone refused", "A plugin with no data" in str(r) and len(core.package_rows()) == 1, str(r))

calls = []
ui.draw_preferences(Rec(calls), bpy.context)
print("[SMOKE] prefs:", " | ".join(c for c in calls if c)[:700])
check("the Preferences box lists the package", any("esempio-statuaria" in c for c in calls)
      and "op:empkg.install_from_disk" in calls and "op:empkg.remove" in calls
      and any(c.startswith("code not installed") for c in calls))

# ── a graph with the chain, as EMStudio writes it ───────────────────────────
from s3dgraphy.annotation.extractors import place_extractor, place_landmark, start_landmark_pose  # noqa: E402
from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.multigraph.multigraph import multi_graph_manager  # noqa: E402
from s3dgraphy.nodes.property_node import PropertyNode  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402
from s3dgraphy import terms  # noqa: E402

ov = core.active_overlay([])[0]
g = Graph(graph_id="smoke_pl12")
g.add_node(RepresentationModelNode("rm1", "Plane_RM"))
pose = start_landmark_pose(g, ov, "stat:volto", "rm1")
for pid, p in {"nasion": [0.0, 0.0, -0.1], "gnathion": [0.0, 0.0, 0.02],
               "exocanthion_r": [-0.05, 0.0, -0.11], "exocanthion_l": [0.05, 0.0, -0.11]}.items():
    place_landmark(g, ov, "stat:volto", pid, "rm1", p, pose_id=pose, lang="it")
surf = place_extractor(g, ov, "stat:superficie_integrata", "rm1",
                       [[-0.3, 0.0, -0.3], [0.3, 0.0, -0.3], [0.3, 0.0, 0.3], [-0.3, 0.0, 0.3]])
us = StratigraphicUnit("us1", "USM01")
g.add_node(us)
FASE = "https://w3id.org/extendedmatrix/profile/esempio-statuaria/vocab/fase-superficie/"
pn = PropertyNode(node_id="pn1", name="Fase della superficie", property_type="stat:fase_di_superficie",
                  value="integrazione", description="integrazione")
terms.set_term(pn, {"concept": FASE + "integrazione", "label": "integrazione", "lang": "it"})
g.add_node(pn)
g.add_edge("e1", "us1", "pn1", "has_property")
multi_graph_manager.graphs["smoke_pl12"] = g
em_tools = scene.em_tools
em_tools.graphml_files.clear()
em_tools.graphml_files.add().name = "smoke_pl12"
em_tools.active_file_index = 0
core.forget_cache()

calls = []
ui.draw_visual_box(Rec(calls), bpy.context)
print("[SMOKE] visual:", " | ".join(c for c in calls if c)[:700])
check("the Visual Manager lists the scheme and the vocabularies",
      "op:empkg.apply_scheme" in calls and any("terms" in c for c in calls))

sid = core.package_schemes(ov, "en")[0]["id"]
r = bpy.ops.empkg.apply_scheme(scheme_id=sid)
vals = {v.value: tuple(v.color) for v in scene.property_values}
check("the package's scheme applied", r == {"FINISHED"} and scene.selected_property == "Fase della superficie"
      and "integrazione" in vals and vals["integrazione"][:3] != (0.5, 0.5, 0.5), str(vals)[:200])

# ── Proxy Box: a point from the graph ───────────────────────────────────────
nasion = next(p for p in core.measured_points(g, ov) if p.landmark.get("point") == "nasion")
r = bpy.ops.empkg.proxybox_point_from_graph(point_index=3, extractor=nasion.extractor_id)
pt = scene.em_tools.proxy_box.points[3]
check("Proxy Box point read from the chain", r == {"FINISHED"} and pt.is_recorded
      and pt.graph_extractor_id == nasion.extractor_id
      and all(abs(a - b) < 1e-6 for a, b in zip(pt.position, (0.0, 0.1, 0.0))), str(tuple(pt.position)))

# ── readings: the surface is drawn ──────────────────────────────────────────
r = bpy.ops.em.show_readings()
coll = bpy.data.collections.get("EM_readings")
kinds = sorted(o.get("em_reading_kind") for o in coll.objects if o.get("em_reading_id")) if coll else []
check("readings shown, the surface among them", r == {"FINISHED"} and kinds.count("surface") == 1
      and kinds.count("point") == 4, str(kinds))
so = next((o for o in coll.objects if o.get("em_reading_kind") == "surface"), None) if coll else None
check("the surface is a closed ring of 4 edges", so is not None and so.type == 'MESH'
      and len(so.data.vertices) == 4 and len(so.data.edges) == 4,
      f"{so and len(so.data.vertices)} v {so and len(so.data.edges)} e")

# ── Areale from the graph surface ───────────────────────────────────────────
bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0, 0, 0))
plane = bpy.context.active_object
plane.name = "Plane_RM"
sa = scene.em_tools.surface_areale
sa.target_rm = plane
before = set(bpy.data.objects)
r = bpy.ops.empkg.areale_from_graph(extractor=surf.extractor_id)
new = [o for o in bpy.data.objects if o not in before]
areale = next((o for o in new if o.get("em_areale_from_extractor") == surf.extractor_id), None)
check("an areale made from the surface", r == {"FINISHED"} and areale is not None
      and areale.type == 'MESH' and len(areale.data.polygons) > 0, f"{r} {[o.name for o in new]}")
if areale is not None:
    xs = [(areale.matrix_world @ v.co).x for v in areale.data.vertices]
    ys = [(areale.matrix_world @ v.co).y for v in areale.data.vertices]
    check("the areale covers the ring (±0.3 m)", abs(max(xs) - 0.3) < 0.05 and abs(min(ys) + 0.3) < 0.05,
          f"x {min(xs):.3f}..{max(xs):.3f} y {min(ys):.3f}..{max(ys):.3f}")

# ── the package's measures ──────────────────────────────────────────────────
r = bpy.ops.empkg.compute_measures()
props = {getattr(n, "name", ""): getattr(n, "value", None) for n in g.nodes
         if getattr(n, "node_type", "") == "property" and (n.data or {}).get("measure")}
# biorbital 0.10 m, face height |-0.1 - 0.02| = 0.12 m, index 120 % or 1.2
check("the measures computed", r == {"FINISHED"} and len(props) == 3
      and abs(float(props["stat:larghezza_biorbitale"]) - 0.10) < 1e-6
      and abs(float(props["stat:altezza_facciale"]) - 0.12) < 1e-6, str(props))

# ── Italian ─────────────────────────────────────────────────────────────────
prefs = bpy.context.preferences.view
prefs.language = 'it_IT'
prefs.use_translate_interface = True
check("Italian", i18n.tr("Remove") == "Rimuovi"
      and i18n.tr("This file uses packages not installed here: x 1.0") ==
      "Questo file usa pacchetti non installati qui: x 1.0", i18n.tr("Remove"))
prefs.language = 'en_US'

# ── remove: the vocabularies stay ───────────────────────────────────────────
r = bpy.ops.empkg.remove('EXEC_DEFAULT', package_id="esempio-statuaria")
from s3dgraphy.authorities import packages as pk  # noqa: E402
pk._changed()
check("removed, vocabularies stay", r == {"FINISHED"} and not core.package_rows()
      and bool(pk.find_installed(FASE)))

print(f"[SMOKE] {'OK' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
