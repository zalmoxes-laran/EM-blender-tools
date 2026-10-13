"""Headless smoke · MICRO RM e aggancio (13 Oct 2026) — OFFLINE, on the
working copy (not the installed extension), on the room as it was at 18:26
(`fixtures/tavolo_2026-10-13_1826.room.json`).

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --factory-startup \\
        --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_rm_aggancio.py

(1) Files says «1 object here is not in the graph: US 4» with «Make it the
    proxy of…»; Object ▸ EM has the same gesture; `listitem.toobj` says what it
    does;
(2) «Make it the proxy of…» on US 4 → the unit «US 4 · B online…»: the
    object takes its proxy name, leaves «only here», and the Sync offers it
    ticked as a new proxy;
(3) the Sync's repair (no network: the operations are recorded): 2f69bffb,
    the glb on the LOD2 datablock, withdrawn with Undo; the RM of the list
    arrives with its node, its epoch and its datablock; nothing the room
    would hold points at a node it lacks; «US 2.001» stays, marked withdrawn.
"""
import copy
import importlib
import json
import os
import sys
import tempfile

import bpy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(REPO, "tests", "fixtures", "tavolo_2026-10-13_1826.room.json")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


PKG_DIR = "/tmp/rm-aggancio/pkg"
os.makedirs(PKG_DIR, exist_ok=True)
link = os.path.join(PKG_DIR, "emtools_wc")
if not os.path.islink(link):
    os.symlink(REPO, link)
sys.path.insert(0, PKG_DIR)
addon = importlib.import_module("emtools_wc")
addon.register()
check("the working copy registers", True)

fl = importlib.import_module("emtools_wc.sync_manager.files_list")
gov = importlib.import_module("emtools_wc.resource_governance")
rs = importlib.import_module("emtools_wc.sync_manager.room_session")
ss = importlib.import_module("emtools_wc.sync_manager.scene_sync")
sc = importlib.import_module("emtools_wc.sync_manager.scene_check")
ph = importlib.import_module("emtools_wc.sync_manager.proxy_hook")
ops = importlib.import_module("emtools_wc.sync_manager.operators")
commands = importlib.import_module("emtools_wc.sync_manager.commands")
functions = importlib.import_module("emtools_wc.functions")
names = importlib.import_module("emtools_wc.operators.addon_prefix_helpers")

from s3dgraphy.api import load_container_file  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402

ROOM = "tavolo-2026-10-12"
RM, BLEND = "ME_EST_bk_LOD2_model", "ME_EST_bk_LOD2_model_res_blend"
LOD2 = "2f69bffb-1757-58ed-bfe7-d7990d79196e"
EPOCH = "49f50053-5472-4a2f-8759-beb366f14ded"
DOC = json.load(open(FIXTURE))

path = tempfile.mktemp(suffix=".em.json")
json.dump(rs.live_view(DOC), open(path, "w"))
GRAPH = next(iter(load_container_file(path)[0].graphs.values()))
from s3dgraphy import api  # noqa: E402
GRAPH.add_node(RepresentationModelNode(RM, name="Model for ME_EST_bk_LOD2", type="RM",
                                       description=""))
api.add_resource(GRAPH, resource_id=BLEND, name="Blend datablock for ME_EST_bk_LOD2",
                 kind="3d_model", tier="master", packaging="datablock",
                 files=[{"url": "blend://RB/TempluMare_2021.blend#Object/ME_EST_bk_LOD2"}])
for eid, s, t, kind in ((f"{RM}_has_linked_resource_{LOD2}", RM, LOD2, "has_linked_resource"),
                        (f"{LOD2}~revision~>{BLEND}", LOD2, BLEND, "was_revision_of")):
    if GRAPH.find_edge_by_id(eid) is None:
        GRAPH.add_edge(eid, s, t, kind)
functions.is_graph_available = lambda context=None: (True, GRAPH)

# the scene as measured at 17:50: US 4 (an Icosphere), US 2.001 on 2f69, the RM
for o in list(bpy.data.objects):            # the factory scene's Cube, camera, light
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1)
bpy.context.active_object.name = "US 4"
bpy.ops.mesh.primitive_monkey_add()
monkey = bpy.context.active_object
monkey.name = "US 2.001"
monkey.update_tag()
for k, v in (("em_resource_id", LOD2), ("em_rm_node_id", LOD2),
             ("em_asset_sha256", "sha256:8ddcb5155edd8d7d1cc33fe90468b09029d763b82fcc36cc448a3475c8ba0715")):
    monkey[k] = v
bpy.ops.mesh.primitive_cube_add()
lod = bpy.context.active_object
lod.name = "ME_EST_bk_LOD0"
lod["em_rm_node_id"] = RM
item = bpy.context.scene.rm_list.add()
item.name, item.node_id = lod.name, RM
lod.EM_ep_belong_ob.add().epoch = "Epoch 1"


class Rec:
    labels: list = []
    operators: list = []
    errors: list = []

    def __init__(self):
        self.alert = self.active = self.enabled = False
        self.scale_y = 1.0
        self.alignment = "EXPAND"

    def _child(self, *a, **k):
        return Rec()
    row = column = box = split = grid_flow = _child

    def separator(self, *a, **k):
        pass

    def label(self, text="", icon="NONE", **k):
        Rec.labels.append(text)

    def prop(self, data, name, **k):
        if not hasattr(data, name):
            Rec.errors.append(f"prop {name} is not on {data}")

    def template_list(self, *a, **k):
        pass

    def menu(self, *a, **k):
        pass

    def operator(self, idname, text="", **k):
        cat, op = idname.split(".")
        try:
            getattr(getattr(bpy.ops, cat), op).get_rna_type()
        except Exception as exc:  # noqa: BLE001
            Rec.errors.append(f"operator {idname}: {exc}")
        Rec.operators.append((idname, text))

        class _Props:
            pass
        return _Props()


# (1) the scene check marks US 4 «only here», and Files says it
report = sc.classify_scene({}, sc.scene_objects(bpy.context, GRAPH))
sc.mark_only_here(report["only_here"])
check("US 4 is only here", report["only_here"] == ["US 4"], str(report["only_here"]))
fl.draw(Rec(), bpy.context, [])
check("Files draws without errors", not Rec.errors, "; ".join(Rec.errors))
check("Files says «1 object here is not in the graph: US 4»",
      "1 object here is not in the graph: US 4" in Rec.labels)
check("with «Make it the proxy of…»",
      ("em.make_proxy_of", "Make it the proxy of…") in Rec.operators)
check("Object ▸ EM has the gesture",
      hasattr(bpy.types, "EM_MT_object_em")
      and ph._object_menu in getattr(bpy.types.VIEW3D_MT_object.draw, "_draw_funcs", []))
check("listitem.toobj says what it does",
      bpy.ops.listitem.toobj.get_rna_type().name == "Use the selected object as this US's proxy")

# (2) the gesture, as the dialog leaves it
ranked = ph.rank_units("US 4", ph.graph_units(GRAPH))
ph._ITEMS[:] = [(uid, name, uid) for uid, name in ranked]
check("the dialog proposes «US 4 · B online…» first",
      ranked[0][1] == "US 4 · B online (più recente) 19:56:23", str(ranked[:3]))
out = bpy.ops.em.make_proxy_of("EXEC_DEFAULT", object_name="US 4", unit="US4")
check("«Make it the proxy of…» runs", out == {"FINISHED"}, str(out))
proxy_name = names.node_name_to_proxy_name("US 4 · B online (più recente) 19:56:23",
                                           context=bpy.context, graph=GRAPH)
obj = bpy.data.objects.get(proxy_name)
check("the object takes the unit's proxy name", obj is not None, proxy_name)
check("it is not «only here» any more", obj is not None and not obj.get("em_only_here"))
check("the unit has a proxy in the scene", "US4" in commands.scene_proxy_units(bpy.context, GRAPH))
models = ss.classify_models([m for m in ss.read_models(bpy.context, GRAPH)
                             if m["object"] == proxy_name])
check("the Sync offers it as a new proxy",
      [(m["kind"], m["target"]) for m in models["new"]] == [("proxy", "US4")], str(models))
check("…ticked", sc._made_proxy(proxy_name))

# (3) the Sync's repair, the operations recorded
sent = []
ops.emit_op = lambda op: (sent.append(op), rs.note_op(rs.SESSION.holds, op))
rs.SESSION.holds = rs.room_holds(DOC, ROOM)
room_before = copy.deepcopy(rs.SESSION.holds)
report = ss.migrate_proxy_models(bpy.context, GRAPH)
held = rs.SESSION.holds
dangling = [eid for eid, (s, _t, d) in held["edges"].items()
            if s not in held["nodes"] or d not in held["nodes"]]
check("2f69bffb withdrawn", report.get("retired") == [LOD2] and LOD2 not in held["nodes"],
      str(report.get("retired")))
check("…with Undo", LOD2 in rs.WITHDRAWN)
check("the RM arrives with its datablock", RM in held["nodes"] and BLEND in held["nodes"])
check("…and its epoch", any(t == (EPOCH, "has_representation_model", RM)
                            for t in held["edges"].values()))
check("…citing its datablock", any(t == (RM, "has_linked_resource", BLEND)
                                   for t in held["edges"].values()))
check("nothing in the room points at a node it lacks", not dangling, str(dangling))
check("the room had two such edges before", len([
    e for e, (s, _t, d) in room_before["edges"].items()
    if s not in room_before["nodes"] or d not in room_before["nodes"]]) == 2)
check("US 2.001 stays, marked withdrawn",
      bpy.data.objects.get("US 2.001") is not None and gov.object_status(
          GRAPH, LOD2, removed=rs.REMOVED_IN_ROOM) == gov.STATUS_WITHDRAWN)
again = len(sent)
ss.migrate_proxy_models(bpy.context, GRAPH)
check("a second Sync sends nothing more", len(sent) == again, f"{len(sent) - again} op(s)")

addon.unregister()
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
