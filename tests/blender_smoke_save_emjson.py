"""Headless smoke · MICRO salva l'em.json (17 Oct 2026) — OFFLINE, on the
working copy, Blender 5.0.1 (Python 3.11: the cp311 wheels unpacked in
EM_SMOKE_SITE), on a COPY of Templu Mare (EM_SMOKE_PROJECT: EM/ with the v3.2
em.json, SB/GreatTemple_2026_v2.blend as E.D. saved it on 17 Oct, RB/)::

    EM_SMOKE_SITE=/tmp/salva17/site EM_SMOKE_PROJECT=/tmp/salva17/proj \\
    "/Applications/Blender 501.app/Contents/MacOS/Blender" -b --factory-startup \\
        /tmp/salva17/proj/SB/GreatTemple_2026_v2.blend \\
        --python tests/blender_smoke_save_emjson.py

1. the .blend's graph slot pointed at a copy of v3.2 (as E.D. loads it), loaded;
2. the containers of the .blend measured (Survey2015 10, the reconstruction 88);
3. the unsaved mark and the save row in the EM Data Tree panel (drawn on a
   RECORDING layout: -b has no region), File › Export › Extended Matrix;
4. «Save em.json» (export.em_save) in place: the safety copy, both containers
   in the file, the mark off;
5. XX_tileset's tileset declared the alternative of Survey2015 («Choose…» →
   a tileset of the graph), saved again, the hat in the file;
6. a change after the save, then the .blend saved: the status line.
The comparison of the files is the report's (s3Dgraphy and EMStudio's reader).
"""
import glob
import importlib
import json
import os
import shutil
import sys

import bpy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.environ.get("EM_SMOKE_SITE", "/tmp/salva17/site")
PROJECT = os.environ.get("EM_SMOKE_PROJECT", "/tmp/salva17/proj")
OUT = os.environ.get("EM_SMOKE_OUT", "/tmp/salva17/logs")
TARGET = os.path.join(PROJECT, "EM", os.environ.get("EM_SMOKE_FILE", "salva_smoke.em.json"))
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


sys.path.insert(0, SITE)
PKG = os.path.join(OUT, "pkg")
os.makedirs(PKG, exist_ok=True)
link = os.path.join(PKG, "emtools_wc")
if not os.path.islink(link):
    os.symlink(REPO, link)
sys.path.insert(0, PKG)
addon = importlib.import_module("emtools_wc")
addon.register()
unsaved = importlib.import_module("emtools_wc.em_setup.unsaved")
setup_ui = importlib.import_module("emtools_wc.em_setup.ui")
ao = importlib.import_module("emtools_wc.rm_manager.alternative_operators")
check("the working copy registers", hasattr(bpy.ops.export, "em_save"))

scene = bpy.context.scene
em = scene.em_tools

# ── 1 · the v3.2 copy as the active graph ───────────────────────────────────
for old in glob.glob(TARGET + "*"):
    os.remove(old)
shutil.copy2(os.path.join(PROJECT, "EM", "TempluMare_v3.2.em.json"), TARGET)
print("[SMOKE] the slot of the .blend:", em.graphml_files[em.active_file_index].graphml_path)
em.graphml_files[em.active_file_index].graphml_path = "//../EM/" + os.path.basename(TARGET)
r = getattr(bpy.ops, "import").em_emjson(file_index=em.active_file_index)
from s3dgraphy import get_graph  # noqa: E402
row = em.graphml_files[em.active_file_index]
graph = get_graph(row.name)
check("v3.2 loaded", r == {"FINISHED"} and graph is not None,
      f"{r} {len(graph.nodes) if graph else 0} nodes {len(graph.edges) if graph else 0} edges")

# ── 2 · the containers of the .blend ────────────────────────────────────────
conts = [(c.label, len(c.mesh_names), c.doc_name, c.group_node_id) for c in scene.rm_containers]
print("[SMOKE] containers:", conts)
by = {c.label: c for c in scene.rm_containers}
survey = by.get("Survey2015")
recon = next((c for c in scene.rm_containers if c.label != "Survey2015"), None)
check("Survey2015 holds 10 meshes", survey is not None and len(survey.mesh_names) == 10)
check("the reconstruction holds 88", recon is not None and len(recon.mesh_names) == 88,
      f"{recon.label if recon else None}")


# ── 3 · the panel: the mark, the save row; File › Export ────────────────────
class Rec:
    lines: list = []
    errors: list = []

    def __init__(self, depth=0):
        self.depth = depth
        self.alert = self.active = self.enabled = False
        self.scale_y = self.scale_x = 1.0
        self.alignment = "EXPAND"
        self.ui_units_x = 0
        self.operator_context = 'INVOKE_DEFAULT'
        self.use_property_split = self.use_property_decorate = False

    def _say(self, text):
        Rec.lines.append("  " * self.depth + text)

    def row(self, *a, **k):
        self._say("— row")
        return Rec(self.depth + 1)

    def column(self, *a, **k):
        return Rec(self.depth + 1)

    def box(self, *a, **k):
        self._say("[box]")
        return Rec(self.depth + 1)

    split = grid_flow = column

    def separator(self, *a, **k):
        pass

    def label(self, text="", icon="NONE", icon_value=0, **k):
        self._say(f"label «{text}»" + (f" ({icon})" if icon != "NONE" else ""))

    def prop(self, data, name, text=None, icon="NONE", **k):
        self._say(f"prop {name}")

    def prop_search(self, *a, **k):
        self._say("prop_search")

    def template_list(self, listtype, *a, **k):
        self._say(f"list {listtype}")

    def template_icon(self, *a, **k):
        pass

    def menu(self, idname, text="", **k):
        self._say(f"menu {idname} «{text}»")

    def popover(self, *a, **k):
        pass

    def operator(self, idname, text="", icon="NONE", **k):
        cat, op = idname.split(".")
        try:
            getattr(getattr(bpy.ops, cat), op).get_rna_type()
        except Exception as exc:  # noqa: BLE001
            Rec.errors.append(f"operator {idname}: {exc}")
        alert = " [lit]" if self.alert else ""
        self._say(f"button {idname} «{text}»" + (f" ({icon})" if icon != "NONE" else "") + alert)

        class _P:
            pass
        return _P()


def draw_tree(title):
    Rec.lines, Rec.errors = [], []
    tree = importlib.import_module("emtools_wc.em_setup.graph_tree")
    lay = Rec()
    tree.draw_toolbar(lay, bpy.context, em, setup_ui.EM_SetupPanel._catena(bpy.context, em))
    tree.draw_graph_tree(lay, bpy.context, em)
    text = "\n".join(Rec.lines)
    with open(os.path.join(OUT, f"tree-{title}.txt"), "w") as fh:
        fh.write(text + "\n")
    check(f"the tree draws ({title})", not Rec.errors, str(Rec.errors[:3]))
    return text


unsaved.measure(scene)
said = unsaved.reasons(importlib.import_module("emtools_wc.graph_origins").file_origin(TARGET))
print("[SMOKE] unsaved after the load:", said)
check("after the load the mark says the two containers are not in the file",
      len(said) == 1 and said[0].startswith("2 RM container(s) not yet in the em.json"), str(said))
before = draw_tree("1-after-load")
name = os.path.basename(TARGET)
check("● on the file's name", f"label «● {name}»" in before)
check("«Save em.json» lit and «Save as…» under the name",
      "button export.em_save «Save em.json» (FILE_TICK) [lit]" in before
      and "button export.em_saveas «Save as…»" in before)
check("the line says why", "Unsaved: 2 RM container(s) not yet in the em.json" in before)
funcs = [getattr(f, "__name__", "") for f in getattr(bpy.types.TOPBAR_MT_file_export.draw, "_draw_funcs", [])]
check("File › Export carries Extended Matrix (.em.json)", "menu_func_export" in funcs
      and any(getattr(f, "__module__", "").endswith("exporter_emjson")
              for f in bpy.types.TOPBAR_MT_file_export.draw._draw_funcs), str(funcs))
print("[SMOKE] export.em_save:", repr(bpy.ops.export.em_save.get_rna_type().name),
      "·", bpy.ops.export.em_save.get_rna_type().description)

# ── 4 · «Save em.json» ──────────────────────────────────────────────────────
r = bpy.ops.export.em_save()
check("export.em_save in place", r == {"FINISHED"}, str(r))
baks = glob.glob(TARGET + ".bak-*")
check("the safety copy beside the file, the v3.2 bytes", len(baks) == 1
      and open(baks[0], "rb").read() == open(os.path.join(PROJECT, "EM", "TempluMare_v3.2.em.json"), "rb").read(),
      str([os.path.basename(b) for b in baks]))
conts = [(c.label, len(c.mesh_names), c.group_node_id) for c in scene.rm_containers]
print("[SMOKE] containers after the save:", conts)
check("both containers have their group", all(c.group_node_id for c in scene.rm_containers))
with open(TARGET) as fh:
    doc = json.load(fh)
g = doc["graphs"][row.name]
groups = {n["id"]: n["name"] for n in g["nodes"] if n["node_type"] == "RepresentationModelNodeGroup"}
members = {}
for e in g["edges"]:
    if e["edge_type"] == "is_in_representation_model_group":
        members[e["target"]] = members.get(e["target"], 0) + 1
print("[SMOKE] groups in the file:", groups, members)
check("2 groups in the file, 10 and 88 members",
      len(groups) == 2 and sorted(members.values()) == [10, 88], str(members))
unsaved.measure(scene)
check("the mark is off after the save", unsaved.reasons(
    importlib.import_module("emtools_wc.graph_origins").file_origin(TARGET)) == [])
draw_tree("2-after-save")
shutil.copy2(TARGET, TARGET.replace(".em.json", "_1-saved.em.json"))

# ── 5 · the alternative of Survey2015, then save ────────────────────────────
si = list(scene.rm_containers).index(survey)
asset = "templu-mare.rb.tileset.master"
got = ao.measure_choice(bpy.context, survey, 'GRAPH', asset)
r = bpy.ops.rmcontainer.alt_confirm('EXEC_DEFAULT', container_index=si, source='GRAPH',
                                    asset_id=asset, name=got["name"], uses=got["uses"],
                                    action=got["action"])
from s3dgraphy.resources.alternatives import hats_of  # noqa: E402
check("XX_tileset's tileset declared: the container is the hat",
      r == {"FINISHED"} and hats_of(graph, asset) == [survey.group_node_id],
      f"{r} {hats_of(graph, asset)} action {got['action']}")
unsaved.measure(scene)
said = unsaved.reasons(importlib.import_module("emtools_wc.graph_origins").file_origin(TARGET))
check("the declaration lights the mark", said == ["the graph changed"], str(said))
r = bpy.ops.export.em_save()
check("saved again, no second safety copy", r == {"FINISHED"}
      and len(glob.glob(TARGET + ".bak-*")) == 1)
with open(TARGET) as fh:
    text = fh.read()
check("the file carries the hat on the group",
      f'"source": "{survey.group_node_id}"' in text and asset in text)
shutil.copy2(TARGET, TARGET.replace(".em.json", "_2-alternative.em.json"))

# ── 6 · a change, then the .blend saved: the status line ────────────────────
graph.find_node_by_id(survey.group_node_id).description = "changed after the save"
blend_copy = os.path.join(OUT, "salva_smoke_copy.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_copy, copy=True)
line = unsaved.warning_line(scene)
print("[SMOKE] status line:", line)
check("saving the .blend warns about the em.json", "the em.json has unsaved changes"
      in line and "Save em.json" in line)
check("the .blend save did not write the em.json", "changed after the save" not in open(TARGET).read())

# ── Part 4 · the versions in two families (Asset versions) ──────────────────
av = importlib.import_module("emtools_wc.sync_manager.asset_versions")
for obj_name, want in (("Column_entrance1", ["Whole: the author made no levels of detail",
                                             "Derived versions (the recipe's)"]),
                       ("ME_EST_L_LOD2", ["LOD0 · analysis", "LOD2 · preview",
                                          "Derived version · web · decimated to 0.50"])):
    Rec.lines, Rec.errors = [], []
    obj = bpy.data.objects.get(obj_name)
    av.draw_families(Rec(), bpy.context, obj)
    text = "\n".join(Rec.lines)
    with open(os.path.join(OUT, f"versions-{obj_name}.txt"), "w") as fh:
        fh.write(text + "\n")
    check(f"Asset versions · {obj_name}: the two families", obj is not None
          and all(w in text for w in want), text.replace("\n", " | ")[:400])

print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
