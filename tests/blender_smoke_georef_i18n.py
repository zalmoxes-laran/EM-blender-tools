"""Headless smoke · the Georeferencing panel in Blender's languages (MICRO georef
al salvataggio, parte 2, 24 Oct 2026), on a COPY of the GT16.

    EM_GEOREF_DIR=/tmp/emt-georef-save \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/emt-georef-save/SB/GreatTemple_2026_v2.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_georef_i18n.py

The catalogue is registered with ``bpy.app.translations``; with the interface
in Italian, then German, the panel draws the graph line, the discrepancy and the
save line in that language; with the translation off, in English. The
preferences are put back as they were.
"""
import importlib
import os
import sys
import types

import bpy

FAILURES = []
DIR = os.environ.get("EM_GEOREF_DIR", "/tmp/emt-georef-save")
EMJSON = os.path.join(DIR, "EM", "TempluMare_v4.em.json")


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


names = [n for n in sys.modules if n.endswith(".georef_manager.graph_sync")
         and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".georef_manager.graph_sync", 1)[0]
gs = importlib.import_module(PKG + ".georef_manager.graph_sync")
panel_mod = importlib.import_module(PKG + ".georef_manager.panel")


class StubLayout:
    def __init__(self, calls):
        self.calls, self.alert, self.enabled, self.scale_y = calls, False, True, 1.0

    def _child(self, *a, **k):
        return StubLayout(self.calls)

    box = row = column = split = _child

    def panel(self, *a, **k):
        return StubLayout(self.calls), None

    def prop(self, *a, **k):
        pass

    prop_search = prop_enum = prop

    def label(self, **k):
        self.calls.append(k.get("text", ""))

    def operator(self, idname, **k):
        self.calls.append(k.get("text", ""))
        return types.SimpleNamespace()

    def separator(self, *a, **k):
        pass


def panel_lines():
    calls = []
    panel_mod.EM_PT_georef.draw(types.SimpleNamespace(layout=StubLayout(calls)),
                                bpy.context)
    return calls


view = bpy.context.preferences.view
was = (view.language, view.use_translate_interface)
print("[SMOKE] preferences before:", was)

scene = bpy.context.scene
g = scene.em_georef
scene.em_tools.graphml_files.clear()
scene.em_tools.active_file_index = -1
g.reference_graph = ""
g.graph_agreed = ""
g.epsg = "31700"
gs.set_shift(g, 327300.0, 448370.0, 500.0)
r = getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)
check("em.json loaded over other values", r == {"FINISHED"}, str(r))

try:
    view.language = "it_IT"
    view.use_translate_interface = True
    tr = bpy.app.translations.pgettext_iface
    check("Blender knows the catalogue (it)", tr("Pull from graph") == "Prendi dal grafo",
          tr("Pull from graph"))
    lines = panel_lines()
    print("[SMOKE] it:", [l for l in lines if "grafo" in l or "Scena" in l or "salva" in l])
    check("the graph line in Italian",
          any(l.startswith("Scena e grafo") and "differiscono" in l for l in lines))
    check("the discrepancy in Italian", "Shift Z: scena 500.000 · grafo 0.000" in lines)
    check("the save line in Italian",
          any(l.startswith("Mai allineata a questi valori") for l in lines))
    check("the Z note in Italian", any(l.startswith("Shift Z = 500.000: una scelta") for l in lines))
    check("a CRS line in Italian", any(l.startswith("Accuratezza") for l in lines),
          str([l for l in lines if "ccura" in l]))

    view.language = "de_DE"
    lines = panel_lines()
    check("the discrepancy in German", "Verschiebung Z: Szene 500.000 · Graph 0.000" in lines,
          str([l for l in lines if "Szene" in l]))
    check("Shift X is not Blender's Shift key («Umschalt»)",
          "Verschiebung X: Szene 327300.000 · Graph 327372.560" in lines
          and not any("Umschalt" in l for l in lines))

    view.use_translate_interface = False
    lines = panel_lines()
    check("translation off: English", "Shift Z: scene 500.000 · graph 0.000" in lines
          and any(l.startswith("Never aligned to these values") for l in lines))
finally:
    view.language, view.use_translate_interface = was
print("[SMOKE] preferences after:", (view.language, view.use_translate_interface))
print(f"[SMOKE] DONE: {len(FAILURES)} failure(s)", FAILURES)
