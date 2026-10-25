"""Headless smoke · MICRO l'alternativa del contenitore (17 Oct 2026) — OFFLINE,
on the working copy, Blender 5.0.1 (Python 3.11: the cp311 wheels unpacked in
EM_SMOKE_SITE), on a COPY of Templu Mare (EM_SMOKE_PROJECT: EM/ with the v3.2
em.json, SB/GreatTemple_2026_v2.blend, RB/ the survey)::

    EM_SMOKE_SITE=/tmp/altc17/site EM_SMOKE_PROJECT=/tmp/altc17/proj \\
    "/Applications/Blender 501.app/Contents/MacOS/Blender" -b --factory-startup \\
        /tmp/altc17/proj/SB/GreatTemple_2026_v2.blend \\
        --python tests/blender_smoke_container_alternative.py

Headless Blender has no region to draw in: the RM panel is drawn on a
RECORDING layout and its rows are printed (the report describes them in place
of a screenshot). A dialog cannot open in -b: the measure of the dialog runs as
its invoke runs it (``measure_choice``), then the operator runs with EXEC.
"""
import importlib
import json
import os
import shutil
import sys

import bpy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.environ.get("EM_SMOKE_SITE", "/tmp/altc17/site")
PROJECT = os.environ.get("EM_SMOKE_PROJECT", "/tmp/altc17/proj")
OUT = os.environ.get("EM_SMOKE_OUT", "/tmp/altc17/logs")
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
check("the working copy registers", hasattr(bpy.ops.rmcontainer, "alt_confirm"))
check("the FileHandler for a dropped .3tz/.zip is registered",
      hasattr(bpy.types, "RMCONTAINER_FH_tileset"))

ao = importlib.import_module("emtools_wc.rm_manager.alternative_operators")
ca = importlib.import_module("emtools_wc.rm_manager.container_alternative")
ui = importlib.import_module("emtools_wc.rm_manager.ui")
cont_mod = importlib.import_module("emtools_wc.rm_manager.containers")

scene = bpy.context.scene
em = scene.em_tools

# ── the graph: the slot of the .blend, pointed at the v3.2 copy ─────────────
em.graphml_files[em.active_file_index].graphml_path = "//../EM/TempluMare_v3.2.em.json"
r = getattr(bpy.ops, "import").em_emjson(file_index=em.active_file_index)
graph = ao._graph(bpy.context)
check("the v3.2 graph is loaded", r == {"FINISHED"} and graph is not None,
      f"{r} {len(graph.nodes) if graph else 0} nodes")

print("[SMOKE] containers:", [(c.label, len(c.mesh_names), c.doc_name, c.group_node_id)
                              for c in scene.rm_containers])


def ensure(label, names, doc=""):
    for i, c in enumerate(scene.rm_containers):
        if c.label == label:
            return i, c
    c = scene.rm_containers.add()
    c.label = label
    for n in names:
        if bpy.data.objects.get(n) is not None:
            e = c.mesh_names.add()
            e.name = n
    return len(scene.rm_containers) - 1, c


survey_names = sorted(o.name for o in bpy.data.objects if o.name.startswith("ME_")
                      and o.type == "MESH" and "TM0" not in o.name)
si, survey = ensure("Survey2015", survey_names)
check("Survey2015 holds the 10 ME_ meshes", len(survey.mesh_names) == 10,
      str([e.name for e in survey.mesh_names]))
scene.rm_containers_index = si


# ── a recording layout: the panel's rows, in order ─────────────────────────
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

    def prop(self, data, name, text=None, icon="NONE", expand=False, **k):
        if not hasattr(data, name):
            Rec.errors.append(f"prop {name} is not on {data}")
        val = getattr(data, name, None)
        self._say(f"prop {name}={val!r}" + (" [expanded]" if expand else "")
                  + (f" ({icon})" if icon != "NONE" else ""))

    def prop_search(self, *a, **k):
        self._say("prop_search")

    def template_list(self, listtype, *a, **k):
        self._say(f"list {listtype}")

    def template_icon(self, *a, **k):
        pass

    def menu(self, idname, text="", **k):
        if not hasattr(bpy.types, idname):
            Rec.errors.append(f"menu {idname} is not registered")
        self._say(f"menu {idname} «{text}»")

    def popover(self, *a, **k):
        pass

    def operator(self, idname, text="", icon="NONE", **k):
        cat, op = idname.split(".")
        try:
            getattr(getattr(bpy.ops, cat), op).get_rna_type()
        except Exception as exc:  # noqa: BLE001
            Rec.errors.append(f"operator {idname}: {exc}")
        self._say(f"button {idname} «{text}»" + (f" ({icon})" if icon != "NONE" else ""))

        class _P:
            pass
        return _P()


def draw_panel(title):
    Rec.lines, Rec.errors = [], []

    class Fake:
        layout = Rec()
    ui.VIEW3D_PT_RM_Manager.draw(Fake(), bpy.context)
    rows_list = []

    class FakeList:
        pass
    for i, c in enumerate(scene.rm_containers):
        rec = Rec()
        ui.RMCONTAINER_UL_list.draw_item(FakeList(), bpy.context, rec, scene, c, 0, scene,
                                         "rm_containers_index", i)
    rows_list = list(Rec.lines)
    text = "\n".join(rows_list)
    with open(os.path.join(OUT, f"panel-{title}.txt"), "w") as fh:
        fh.write(text + "\n")
    check(f"the panel draws ({title})", not Rec.errors, str(Rec.errors[:3]))
    return text


before = draw_panel("1-before")
check("no document: the light warning and its cure",
      "No document wraps this container" in before and "Link to document…" in before)
check("«Alternative: —» and «Choose…»", "Alternative: —" in before and "«Choose…»" in before)

# ── Part 4 · the document the models say ───────────────────────────────────
co = importlib.import_module("emtools_wc.rm_manager.container_operators")


def proposal_for(c):
    """What «Link to document…» computes when it opens (its invoke)."""
    return co.container_proposal(bpy.context, graph, c)


prop = proposal_for(survey)
check("Survey2015: the proposal is D.01", prop["name"] == "D.01",
      f"{prop['count']}/{prop['of']} by id {prop['by_id']}, by place {len(prop['twins'])}: "
      f"{sorted(prop['twins'].items())[:3]}")
other = next((c for c in scene.rm_containers if c.label != "Survey2015"), None)
if other is not None:
    prop9 = proposal_for(other)
    print(f"[SMOKE] «{other.label}» ({len(other.mesh_names)} meshes): proposal "
          f"{prop9['name'] or None}, {prop9['count']}/{prop9['of']}, by id {prop9['by_id']}, "
          f"by place {len(prop9['twins'])}, ranking {prop9['ranking'][:3]}, "
          f"not counted {prop9['skipped']}")
    check("the reconstruction's meshes say D.09 (the tileset object apart)",
          prop9["name"] == "D.09" and prop9["skipped"] == ["XX_tileset"])
rms_before = sum(1 for n in graph.nodes if n.node_type == "representation_model")
co._PROPOSAL.clear()
co._PROPOSAL.update(prop)
r = bpy.ops.rmcontainer.link_or_create_doc('EXEC_DEFAULT', container_index=si,
                                           target_doc_name="D.01")
rms_after = sum(1 for n in graph.nodes if n.node_type == "representation_model")
check("linked to D.01, no RM made twice", r == {"FINISHED"} and survey.doc_name == "D.01"
      and rms_after == rms_before, f"{r} RMs {rms_before}→{rms_after}")
cont_mod.reconcile_container_groups(bpy.context, create_missing=True)
grp_doc = [e.edge_source for e in graph.edges
           if e.edge_type == "has_representation_model" and e.edge_target == survey.group_node_id]
d01 = next(n.node_id for n in graph.nodes if n.node_type == "document" and n.name == "D.01")
check("has_representation_model D.01 → the group", grp_doc == [d01],
      f"{survey.group_node_id} {grp_doc}")

# ── Part 1/2 · a tileset of the graph, the coverage ─────────────────────────
assets = ca.tileset_assets(graph)
print("[SMOKE] tilesets of the graph:", [(a["name"], a["uses"], ca.human_size(a["size_bytes"]),
                                          a["hat_names"]) for a in assets])
got = ao.measure_choice(bpy.context, survey, 'GRAPH', "templu-mare.rb.tileset.master")
cov = ao._PENDING.get("coverage")
check("the coverage is measured on the tileset of the graph", cov is not None,
      ao._PENDING.get("error", ""))
if cov:
    for line in ca.coverage_lines(cov):
        print("[SMOKE]   ", line)
    check("Survey2015: TEMPLUM more, nothing missing",
          cov["extra"] == ["SM_OB_TEMPLUM_LOD1"] and cov["missing"] == [],
          f"extra {cov['extra']} missing {cov['missing']} shares {cov['shares']}")
check("the dialog proposes «Confirm anyway»", got["action"] == 'ANYWAY')
r = bpy.ops.rmcontainer.alt_confirm('EXEC_DEFAULT', container_index=si, source='GRAPH',
                                    asset_id="templu-mare.rb.tileset.master",
                                    name=got["name"], uses=got["uses"], action='ANYWAY')
from s3dgraphy.resources.alternatives import hats_of  # noqa: E402
check("declared: the container is the hat", r == {"FINISHED"}
      and hats_of(graph, "templu-mare.rb.tileset.master") == [survey.group_node_id],
      f"{r} {hats_of(graph, 'templu-mare.rb.tileset.master')}")
check("the row keeps the warning", survey.alt_note == "confirmed with 1 more", survey.alt_note)
after = draw_panel("2-after")
check("the alternative row: name, uses, eye, modes, remove",
      "alternative · web, realtime" in after and "alt_shown" in after
      and "alt_mode='MODELS' [expanded]" in after and "rmcontainer.alt_remove" in after)

# ── Part 3 · the mode and the eye ──────────────────────────────────────────
survey.alt_mode = 'TILESET'
box = bpy.data.objects.get(ao.box_name(survey))
hidden = [e.name for e in survey.mesh_names if bpy.data.objects[e.name].hide_get()]
check("Tileset: the members hidden, the box shown", box is not None and len(hidden) == 10
      and not box.hide_get(), f"{len(hidden)} hidden, box {box and box.name}")
if box is not None:
    print("[SMOKE] the box:", [round(x, 2) for x in box.location], [round(x, 2) for x in box.scale])
survey.alt_shown = False
check("the eye hides the box", box is not None and box.hide_get())
survey.alt_mode = 'AUTO'
check("Automatic is Models in Blender",
      not any(bpy.data.objects[e.name].hide_get() for e in survey.mesh_names))
survey.alt_mode = 'MODELS'
survey.alt_shown = True

# ── the em.json keeps it ───────────────────────────────────────────────────
saved = os.path.join(PROJECT, "EM", "alt_smoke_saved.em.json")
r = bpy.ops.export.em_saveas(filepath=saved)
with open(saved) as fh:
    text = fh.read()
check("the saved em.json carries the hat on the group",
      f'"source": "{survey.group_node_id}"' in text and "templu-mare.rb.tileset.master" in text, str(r))

# ── «Remove the alternative» ───────────────────────────────────────────────
r = bpy.ops.rmcontainer.alt_remove('EXEC_DEFAULT', container_index=si)
check("removed: no hat, the resource stays", r == {"FINISHED"} and not survey.alt_asset_id
      and graph.find_node_by_id("templu-mare.rb.tileset.master") is not None
      and bpy.data.objects.get(ao.box_name(survey)) is None)

# ── a file from the disk: a .3tz outside the project ───────────────────────
outside = os.path.join(OUT, "outside")
os.makedirs(outside, exist_ok=True)
src = os.path.join(outside, "TempluMare.3tz")
if not os.path.exists(src):
    shutil.copy2(os.path.join(PROJECT, "RB", "cesium", "TempluMare.3tz"), src)
got = ao.measure_choice(bpy.context, survey, 'DISK', path=src)
plan = ao._PENDING.get("plan")
check("from the disk: the name proposed, the plan into RM/tilesets",
      got["name"] == "TempluMare" and plan["locator"] == "../RM/tilesets/TempluMare.3tz",
      f"{got['name']} {plan}")
r = bpy.ops.rmcontainer.alt_confirm('EXEC_DEFAULT', container_index=si, source='DISK', path=src,
                                    name=got["name"], uses={"web", "realtime"}, action='ANYWAY')
dest = os.path.join(PROJECT, "RM", "tilesets", "TempluMare.3tz")
check("the .3tz is in the project's storage", r == {"FINISHED"} and os.path.isfile(dest))
check("the same bytes are the resource the graph had (the .3tz of v3.2)",
      survey.alt_asset_id == "templu-mare.rb.tileset.lod0.3tz", survey.alt_asset_id)
draw_panel("3-from-disk")

# «Add to the container»: TEMPLUM is in the graph only — said, not invented
bpy.ops.rmcontainer.alt_remove('EXEC_DEFAULT', container_index=si)
got = ao.measure_choice(bpy.context, survey, 'GRAPH', "templu-mare.rb.tileset.master")
n_before = len(survey.mesh_names)
r = bpy.ops.rmcontainer.alt_confirm('EXEC_DEFAULT', container_index=si, source='GRAPH',
                                    asset_id="templu-mare.rb.tileset.master",
                                    name=got["name"], uses=got["uses"], action='ADD')
check("Add to the container: TEMPLUM has no object, nothing added, declared anyway",
      r == {"FINISHED"} and len(survey.mesh_names) == n_before and survey.alt_asset_id
      and survey.alt_note == "", f"{r} {len(survey.mesh_names)}")

# the drop: the operator the FileHandler calls (in -b the dialog cannot open)
try:
    r = bpy.ops.rmcontainer.alt_drop('EXEC_DEFAULT', filepath=src)
    print(f"[SMOKE] the drop operator in -b: {r} (the dialog needs a window)")
except Exception as exc:  # noqa: BLE001
    print(f"[SMOKE] the drop operator in -b: {type(exc).__name__}: {exc}")
fh = bpy.types.RMCONTAINER_FH_tileset
check("the FileHandler takes .3tz, .zip and the RealityScan .json, for rmcontainer.alt_drop",
      fh.bl_file_extensions == ".3tz;.zip;.json" and fh.bl_import_operator == "rmcontainer.alt_drop")

# «Add Cesium Tileset»: the file chosen, the name proposed, into the storage
if len(em.epochs.list):
    em.epochs.list_index = 0
    before = set(bpy.data.objects.keys())
    r = bpy.ops.rm.add_tileset('EXEC_DEFAULT', filepath=src)
    new = [bpy.data.objects[n] for n in set(bpy.data.objects.keys()) - before]
    obj = next((o for o in new if "tileset_path" in o), None)
    check("Add Cesium Tileset: chosen file, proposed name, a path into the storage",
          r == {"FINISHED"} and obj is not None and obj.name.startswith("TempluMare")
          and obj["tileset_path"].endswith(os.path.join("RM", "tilesets", "TempluMare.3tz")),
          f"{r} {obj and obj.name} {obj and obj['tileset_path']}")

print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
