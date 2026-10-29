"""Headless smoke · the site, its footprint and its GIS layers through EM Tools
(MICRO lab sito Sarmizegetusa, 30 Oct 2026), on a COPY of Templu Mare v4 made by
EMStudio Lab's door (s3dgraphy.gis through the bridge's lab routes):

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src EM_SITO_DIR=/tmp/emt-sito \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python tests/blender_smoke_site.py

$EM_SITO_DIR/EM/TempluMare_v4_sito.em.json: the GT16 with the site «Templu
Mare», its footprint (a POLYGON Z in EPSG:3844 from the proxies of
SU001–SU004) and the 2015 layers M_SR15_AREA_A and M_SR15_FOR1.

(1) opened in an empty scene: the graph holds them, no edge of the site
degraded; (2) the Georeferencing panel says the site, its footprint, its two
layers (drawn on a recording layout: -b has no region); (3) «Save em.json»: the
file still holds them, node for node and edge for edge; (4) reopened: the same.
"""
import importlib
import json
import os
import sys
import types

import bpy

FAILURES = []
DIR = os.environ.get("EM_SITO_DIR", "/tmp/emt-sito")
EMJSON = os.path.join(DIR, "EM", "TempluMare_v4_sito.em.json")


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


names = [n for n in sys.modules if n.endswith(".georef_manager.graph_sync") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".georef_manager.graph_sync", 1)[0]
print("[SMOKE] package:", PKG)
import s3dgraphy  # noqa: E402
print("[SMOKE] s3dgraphy from:", os.path.dirname(s3dgraphy.__file__))
panel_mod = importlib.import_module(PKG + ".georef_manager.panel")
site_info = importlib.import_module(PKG + ".georef_manager.site_info")
gs = importlib.import_module(PKG + ".georef_manager.graph_sync")


class StubLayout:
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

    def prop(self, *a, **k):
        pass

    prop_enum = prop_search = separator = prop

    def label(self, **k):
        self.calls.append(k.get("text", ""))

    def operator(self, *a, **k):
        return types.SimpleNamespace()


def panel_lines():
    calls = []
    panel_mod.EM_PT_georef.draw(types.SimpleNamespace(layout=StubLayout(calls)), bpy.context)
    return calls


def site_part(path=EMJSON):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    gd = doc["graphs"][doc["active_graph_id"]]
    site = [n for n in gd["nodes"] if n.get("node_type") == "LocationNodeGroup" and (n.get("data") or {}).get("level") == "sito"]
    sid = site[0]["id"] if site else None
    out_e = sorted((e["edge_type"], e["target"]) for e in gd["edges"] if e["source"] == sid)
    targets = {t for _k, t in out_e}
    layer_ids = [n["id"] for n in gd["nodes"] if (n.get("data") or {}).get("url_type") == "gis_layer"]
    files = sorted((e["source"], e["target"]) for e in gd["edges"] if e["edge_type"] == "has_file" and e["source"] in layer_ids)
    # data.name of the site is the copy of its name make_site_place writes; the
    # writer leaves out a data.name equal to the node's own name (measured: the
    # only difference), so it is not compared — the name stays on the node
    nodes = {n["id"]: {"name": n.get("name"), **{k: v for k, v in (n.get("data") or {}).items()
                                               if k != "field_clocks" and not (k == "name" and v == n.get("name"))}}
             for n in gd["nodes"] if n["id"] in targets | {sid} | set(layer_ids)}
    generic = sum(1 for e in gd["edges"] if e.get("edge_type") == "generic_connection")
    return {"site": site[0]["name"] if site else None, "edges": out_e, "files": files, "nodes": nodes, "generic": generic}


scene = bpy.context.scene
scene.em_tools.graphml_files.clear()
scene.em_tools.active_file_index = -1
before = site_part()
print("[SMOKE] the file before:", before["site"], len(before["edges"]), "edges of the site,", len(before["files"]), "layer files")

# (1) opened
r = getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)
check("em.json opened", r == {"FINISHED"}, str(r))
graph = gs.get_active_graph()
summary = site_info.site_summary(graph)
check("the graph holds the site", summary is not None and summary["name"] == "Templu Mare", str(summary)[:200])
types_site = sorted(e.edge_type for e in graph.edges if summary and e.edge_source == summary["id"])
check("no edge of the site degraded on load", "generic_connection" not in types_site, str(types_site))

# (2) the panel
lines = panel_lines()
said = [l for l in lines if l.startswith(("Site:", "Footprint:", "GIS layer:"))]
print("[SMOKE] the panel:", said)
check("the panel says the site", "Site: Templu Mare" in said)
check("…its footprint", any(l.startswith("Footprint: POLYGON Z, EPSG:3844") for l in said))
check("…its two layers", sum(1 for l in said if l.startswith("GIS layer: M_SR15_")) == 2)

# (3) saved
r = bpy.ops.export.em_save()
check("«Save em.json»", r == {"FINISHED"}, str(r))
after = site_part()
check("the site's edges kept", after["edges"] == before["edges"], f"{len(after['edges'])} vs {len(before['edges'])}")
check("the layers' files kept", after["files"] == before["files"], f"{len(after['files'])}")
check("the site, the footprint, the layers: data kept", after["nodes"] == before["nodes"])
check("no generic_connection written", after["generic"] == before["generic"], f"{after['generic']} vs {before['generic']}")

# (4) reopened
scene.em_tools.graphml_files.clear()
scene.em_tools.active_file_index = -1
r = getattr(bpy.ops, "import").em_emjson(filepath=EMJSON)
again = site_info.site_summary(gs.get_active_graph())
check("reopened: the same site", again == summary, str(again)[:200])

print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
