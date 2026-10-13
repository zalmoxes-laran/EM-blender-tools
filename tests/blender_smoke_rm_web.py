"""Headless smoke · MICRO-RM-WEB (13 Oct 2026) — OFFLINE, on the working copy
(not the installed extension), on the room as it was at 18:26
(`fixtures/tavolo_2026-10-13_1826.room.json`) with the RM E.D. pressed
«Upload» on at 19:30: «ME_EST_bk_LOD0 — model in this .blend».

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --factory-startup \\
        --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_rm_web.py

(1) the card of the datablock row offers «Send a web version», not «Upload»;
    a file of the disk still offers «Upload»;
(2) `em.files_upload` on the datablock row refuses and sends nothing;
(3) `em.files_send_web_version` (the node faked, the operations recorded):
    the glb made by «Prepare for a use…» for the web is sent, never the
    .blend; the graph has a distribution version, resident, model/gltf-binary,
    not a revision of the datablock; the room gets it with the RM, its epoch
    and its datablock, nothing dangling; `geometry_summary` gives it resident
    under the RM.
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


PKG_DIR = "/tmp/rm-web/pkg"
os.makedirs(PKG_DIR, exist_ok=True)
link = os.path.join(PKG_DIR, "emtools_wc")
if not os.path.islink(link):
    os.symlink(REPO, link)
sys.path.insert(0, PKG_DIR)
addon = importlib.import_module("emtools_wc")
addon.register()
check("the working copy registers", True)

fl = importlib.import_module("emtools_wc.sync_manager.files_list")
fs = importlib.import_module("emtools_wc.sync_manager.file_states")
gov = importlib.import_module("emtools_wc.resource_governance")
rs = importlib.import_module("emtools_wc.sync_manager.room_session")
room = importlib.import_module("emtools_wc.sync_manager.room")
upl = importlib.import_module("emtools_wc.sync_manager.asset_upload")
ops = importlib.import_module("emtools_wc.sync_manager.operators")
functions = importlib.import_module("emtools_wc.functions")
fs_web = importlib.import_module("emtools_wc.sync_manager.web_version")

from s3dgraphy import api  # noqa: E402
from s3dgraphy.api import load_container_file  # noqa: E402
from s3dgraphy.nodes.representation_node import RepresentationModelNode  # noqa: E402

ROOM = "tavolo-2026-10-12"
BASE = "https://em.localhost:8443/em"
RM, BLEND = "ME_EST_bk_LOD0_model", "ME_EST_bk_LOD0_model_res_blend"
EPOCH = "49f50053-5472-4a2f-8759-beb366f14ded"
DOC = json.load(open(FIXTURE))

path = tempfile.mktemp(suffix=".em.json")
json.dump(rs.live_view(DOC), open(path, "w"))
GRAPH = next(iter(load_container_file(path)[0].graphs.values()))
GRAPH.add_node(RepresentationModelNode(RM, name="Model for ME_EST_bk_LOD0", type="RM",
                                       description=""))
api.add_resource(GRAPH, resource_id=BLEND, name="Blend datablock for ME_EST_bk_LOD0",
                 kind="3d_model", tier="master", packaging="datablock",
                 files=[{"url": "blend://RB/TempluMare_2021.blend#Object/ME_EST_bk_LOD0"}])
GRAPH.add_edge(f"{RM}_has_linked_resource_{BLEND}", RM, BLEND, "has_linked_resource")
GRAPH.add_edge(f"{EPOCH}_has_representation_model_{RM}", EPOCH, RM, "has_representation_model")
api.add_resource(GRAPH, resource_id="D.32", name="D.32.jpg", kind="image",
                 files=[{"url": "/tmp/rm-web/D.32.jpg"}])
functions.is_graph_available = lambda context=None: (True, GRAPH)
functions.check_active_graph = lambda context=None, show_message=False: (True, GRAPH)
fl._in_room = lambda: True
fl._may_write = lambda context: True

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add()
lod = bpy.context.active_object
lod.name = "ME_EST_bk_LOD0"
lod["em_rm_node_id"] = RM
item = bpy.context.scene.rm_list.add()
item.name, item.node_id = lod.name, RM
lod.EM_ep_belong_ob.add().epoch = "Epoch 1"

BLEND_PATH = "/tmp/rm-web/TempluMare_2021.blend"
with open(BLEND_PATH, "wb") as fh:
    fh.write(b"BLENDER-v405" + b"\0" * 4096)
with open("/tmp/rm-web/D.32.jpg", "wb") as fh:
    fh.write(b"\xff\xd8\xff" + b"\0" * 64)
RESULTS = [{"id": BLEND, "state": "on_disk", "node_type": "resource",
            "name": "Blend datablock for ME_EST_bk_LOD0", "path": BLEND_PATH,
            "sha256": "sha256:" + upl.sha256_of_file(BLEND_PATH), "positions": []},
           {"id": "D.32", "state": "on_disk", "node_type": "resource", "name": "D.32.jpg",
            "path": "/tmp/rm-web/D.32.jpg", "sha256": None, "positions": []}]
fs.ULTIMI.update({"results": RESULTS, "bucket": {}, "moved": []})
fs.resolve_active = lambda context, graph: fs.ULTIMI["results"]   # no disk walk, no node
fl.fill(bpy.context, fl.build_rows(GRAPH, RESULTS))
wm = bpy.context.window_manager


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


def card_of(rid):
    Rec.labels, Rec.operators, Rec.errors = [], [], []
    it = next(x for x in wm.em_files if x.id == rid)
    fl.draw_card(Rec(), bpy.context, GRAPH, it)
    return it


# (1) the gestures of the two rows
it = card_of(BLEND)
check("the datablock row is «ME_EST_bk_LOD0 — model in this .blend»",
      it.file == "ME_EST_bk_LOD0 — model in this .blend", it.file)
check("its card draws", not Rec.errors, "; ".join(Rec.errors))
check("…with «Send a web version»",
      ("em.files_send_web_version", "Send a web version") in Rec.operators, str(Rec.operators))
check("…and no «Upload»", not any(i == "em.files_upload" for i, _t in Rec.operators))
check("…nor «Replace» (a glb is not a version of it)",
      not any(i == "em.files_replace" for i, _t in Rec.operators))
card_of("D.32")
check("a file of the disk still offers «Upload»",
      ("em.files_upload", "Upload") in Rec.operators, str(Rec.operators))

# the node, faked: what is sent is recorded, nothing leaves this machine
room._session.update({"base_url": BASE, "room_id": ROOM, "token": "t"})
room.public_base = lambda timeout=5.0: ""
fs._personal = lambda base: False
SENT = []


def fake_upload(node, room_id, path, sha256, media_type, token, *a, **k):
    hexd = upl._hex(sha256) if sha256 else upl.sha256_of_file(path)
    SENT.append({"path": path, "sha256": hexd, "media_type": media_type,
                 "size": os.path.getsize(path)})
    return {"ref": f"sha256:{hexd}", "sha256": hexd, "size": os.path.getsize(path),
            "media_type": media_type, "already": False}


upl.upload_asset = fake_upload
OPS = []
ops.emit_op = lambda op: (OPS.append(op), rs.note_op(rs.SESSION.holds, op))
rs.SESSION.holds = rs.room_holds(DOC, ROOM)

# (2) Upload on the datablock: refused, nothing sent
try:
    r = bpy.ops.em.files_upload("EXEC_DEFAULT", resource_id=BLEND)
except RuntimeError as exc:                  # a CANCELLED with its ERROR
    r = str(exc)
check("«Upload» on the datablock refuses, saying «Send a web version»",
      "Send a web version" in str(r), str(r))
check("…and sends nothing", SENT == [] and OPS == [], f"{SENT} {OPS}")

# (3) Send a web version
try:
    r = bpy.ops.em.files_send_web_version("EXEC_DEFAULT", resource_id=BLEND)
except RuntimeError as exc:
    r = str(exc)
check("«Send a web version» runs", r == {"FINISHED"}, str(r))
check("one glb was sent, never the .blend",
      len(SENT) == 1 and SENT[0]["path"].endswith(".glb")
      and SENT[0]["media_type"] == "model/gltf-binary"
      and not SENT[0]["path"].endswith(".blend"), str(SENT))
versions = [e for e in api.versions_of(GRAPH, BLEND) if not e["master"]]
check("the datablock has one version", len(versions) == 1, str(versions))
vid = versions[0]["id"] if versions else ""
v = (GRAPH.find_node_by_id(vid).data if vid else {}) or {}
check("…distribution, resident, a glb, for the web",
      v.get("tier") == "distribution" and v.get("residency") == "resident"
      and v.get("media_type") == "model/gltf-binary" and v.get("use") == ["web"], str(v))
check("…its digest is what was sent",
      bool(SENT) and v.get("checksum") == "sha256:" + SENT[0]["sha256"])
check("…its url on the room's base", v.get("url") == gov.store_url(BASE, ROOM, v.get("checksum")),
      str(v.get("url")))
check("…named after the object", GRAPH.find_node_by_id(vid).name == "ME_EST_bk_LOD0 lod0",
      GRAPH.find_node_by_id(vid).name if vid else "")
check("…and never taken for the datablock", not fs_web.is_datablock(GRAPH, vid))
check("…not a revision of the datablock",
      not any(e.edge_type == "was_revision_of" and e.edge_source == vid for e in GRAPH.edges))
held = rs.SESSION.holds
dangling = [eid for eid, (s, _t, d) in held["edges"].items()
            if s not in held["nodes"] or d not in held["nodes"]]
check("the room gets the version with the RM and its datablock",
      {vid, RM, BLEND} <= held["nodes"], str(sorted(held["nodes"] & {vid, RM, BLEND})))
check("…and its epoch", (EPOCH, "has_representation_model", RM) in held["edges"].values())
check("nothing in the room points at a node it lacks", not dangling, str(dangling))
rec = [x for x in api.geometry_summary(GRAPH)["resident"] if x["resource_id"] == vid]
check("geometry_summary gives it resident under the RM",
      len(rec) == 1 and rec[0]["node_id"] == RM, str(rec))

# Upload of a file of the disk records it
n_ops = len(OPS)
r = bpy.ops.em.files_upload("EXEC_DEFAULT", resource_id="D.32")
d = GRAPH.find_node_by_id("D.32").data
check("«Upload» of D.32 runs", r == {"FINISHED"}, str(r))
check("…and records checksum, residency, url",
      d.get("residency") == "resident" and str(d.get("checksum", "")).startswith("sha256:")
      and d.get("url") == gov.store_url(BASE, ROOM, d.get("checksum")), str(d))
check("…and the room hears it", any(o.get("op") in ("add_node", "update_field")
                                    for o in OPS[n_ops:]), str(OPS[n_ops:]))

addon.unregister()
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
