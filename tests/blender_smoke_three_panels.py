"""Headless smoke · MICRO tre pannelli (13 Oct 2026) — OFFLINE, on the working
copy (not the installed extension).

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --factory-startup \\
        --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_three_panels.py

Headless Blender has no region to draw in, so the panels are drawn on a
RECORDING layout: every label is kept, every `prop` must name a property that
exists, every `operator` an operator that is registered. The room is the one
E.D. was in (`tavolo-2026-10-12`, editor2), its state given to the panel:

(1) Room, Files and Project storage draw, each without errors;
(2) no visible label holds an ORCID, a hex of 12+ digits or a UUID;
(3) «Open in EMStudio» is drawn ONCE in the whole N-panel (every panel of the
    tabs EM and EM Scene, in a room);
(4) the EM Data Tree in a room is one row;
(5) the card of US 2 does not offer «Replace» while US 3's object is the
    active one, and its operator's poll says no; with US 2's object it does;
(6) v1 and v2 of US 2 (the same bytes) are one version; the identity, the
    alignment and the files are each said once.

MICRO una verità (13 Oct 2026), on the same harness:
(7) ONE «Open in EMStudio» operator is registered (`em.room_open_elsewhere`
    is gone);
(8) no Heriverse hexagon (`is_publishable`) in the rows of the Data Tree;
(9) «Where you work» is ONE window in steps: no step draws an operator that
    opens another window; the three addresses of the node are one row,
    «● in use», without Use;
(10) the head of Files counts its rows; «No bucket» is grey;
(11) «Replace» is not offered with «US 2.001» active, bound to a version
    that is not in use.
"""
import importlib
import os
import re
import sys

import bpy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


PKG_DIR = os.environ.get("EM_SMOKE_PKG", "/tmp/una-verita/pkg")
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
pc = importlib.import_module("emtools_wc.proxy_chain")
where = importlib.import_module("emtools_wc.sync_manager.where")
panel = importlib.import_module("emtools_wc.sync_manager.panel")
graph_tree = importlib.import_module("emtools_wc.em_setup.graph_tree")
functions = importlib.import_module("emtools_wc.functions")

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402

ROOM = "tavolo-2026-10-12"
ORCID = "0000-0002-1825-2221"
TITLE = "Tavolo · prova multiutente del 12 ottobre"
where.ROOM_TITLES[ROOM] = TITLE


def the_room():
    g = Graph(ROOM)
    out = {}
    for uid, name, two in (("US1", "US 1", "11"), ("US2", "US 2 · dopo A", "6c"),
                           ("US3", "US 3", "33")):
        g.add_node(StratigraphicUnit(uid, name=name))
        rid = pc.ensure_unit_proxy(g, uid, name)["resource_id"]
        d = "sha256:" + two * 32
        g.find_node_by_id(rid).data.update({
            "url": gov.store_url("https://em.localhost:8443/em", ROOM, d), "checksum": d,
            "residency": "resident", "media_type": "model/gltf-binary",
            "created_by": ORCID, "created_at": "2026-10-13T08:51:00Z"})
        out[uid] = rid
    # US 2: the two doubled revisions of the morning, the same bytes
    rr = gov._rr()
    d = "sha256:" + "6c" * 32
    spec = {"path": "US 2 · dopo A.glb", "checksum": d, "size_bytes": 10,
            "url": gov.store_url("https://em.localhost:8443/em", ROOM, d),
            "media_type": "model/gltf-binary"}
    v2 = rr.revise_files(g, out["US2"], [spec], force=True)["new_resource_id"]
    g.find_node_by_id(v2).data.update({"checksum": d, "residency": "resident",
                                       "created_by": ORCID,
                                       "created_at": "2026-10-13T09:20:00Z"})
    rr.move_citations(g, out["US2"], v2, [c["edge_id"] for c in gov.citing(g, out["US2"])])
    out["US2v2"] = v2
    return g, out


GRAPH, IDS = the_room()
functions.is_graph_available = lambda context=None: (True, GRAPH)
functions.check_active_graph = lambda context=None, show_message=False: (True, GRAPH)
fl._in_room = lambda: True
fl._may_write = lambda context: True
fl._people = lambda context: {ORCID: "Editor Due"}

ROOM_STATE = {"place": "room", "declared": "room", "room_id": ROOM, "room_title": TITLE,
              "node": "https://em.localhost:8443/em", "members": 2, "connected": True,
              "author": "Editor Due", "user": "editor2", "role": "editor",
              "can_write": True, "sent": 4, "answered": 4, "waiting": 0, "refused": 0,
              "tally": {"here": 3, "missing": 0, "changed": 0, "external": 0, "only_here": 0},
              "signin_line": "signed in to https://em.localhost:8443/em as editor2",
              "signed_in_to": "https://em.localhost:8443/em"}
where.read_state = lambda context: dict(ROOM_STATE)


class Rec:
    """A layout that records what it is asked to draw and checks it."""
    labels: list = []
    operators: list = []
    errors: list = []
    rows = 0

    def __init__(self):
        self.alert = self.active = self.enabled = False
        self.scale_y = self.scale_x = 1.0
        self.alignment = "EXPAND"
        self.ui_units_x = 0

    def _child(self, *a, **k):
        return Rec()
    column = box = split = grid_flow = _child

    def row(self, *a, **k):
        Rec.rows += 1
        return Rec()

    def separator(self, *a, **k):
        pass

    def label(self, text="", icon="NONE", **k):
        Rec.labels.append(text)

    props: list = []

    def prop(self, data, name, text=None, **k):
        Rec.props.append(name)
        if not hasattr(data, name):
            Rec.errors.append(f"prop {name} is not on {data}")
        elif text:
            Rec.labels.append(text)

    def prop_enum(self, data, name, value, text=None, **k):
        self.prop(data, name, text=text)

    def template_list(self, *a, **k):
        pass

    def template_icon(self, *a, **k):
        pass

    def menu(self, idname, text="", **k):
        if not hasattr(bpy.types, idname):
            Rec.errors.append(f"menu {idname} is not registered")
        if text:
            Rec.labels.append(text)

    def popover(self, *a, **k):
        pass

    def operator(self, idname, text="", **k):
        cat, op = idname.split(".")
        try:
            rna = getattr(getattr(bpy.ops, cat), op).get_rna_type()
        except Exception as exc:  # noqa: BLE001
            Rec.errors.append(f"operator {idname}: {exc}")
            rna = None
        Rec.operators.append((idname, text))
        Rec.labels.append(text if text else (rna.name if rna is not None and "text" not in k
                                             and False else ""))

        class _Props:
            pass
        return _Props()


def reset():
    Rec.labels, Rec.operators, Rec.errors, Rec.props = [], [], [], []
    Rec.rows = 0


class _Self:
    """Stands for the panel: its layout is recording, its methods the class's."""
    def __init__(self, cls=object):
        self.layout = Rec()
        self._cls = cls

    def __getattr__(self, name):
        attr = getattr(self._cls, name)
        return attr.__get__(self) if callable(attr) and hasattr(attr, "__get__") else attr


def draw_panel(cls):
    me = _Self(cls)
    if hasattr(cls, "draw_header"):
        try:
            cls.draw_header(me, bpy.context)
        except Exception as exc:  # noqa: BLE001
            Rec.errors.append(f"{cls.__name__} header: {exc}")
    cls.draw(me, bpy.context)


CODE = re.compile(r"(?i)[0-9a-f]{12,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
                  r"[0-9a-f]{12}|\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")

# the files, checked as the entry would
RESULTS = [{"id": n.node_id, "state": "on_node" if n.node_id in (IDS["US2"], IDS["US2v2"])
            else "both", "node_type": n.node_type, "name": n.name, "positions": []}
           for n in GRAPH.nodes if getattr(n, "node_type", "") in ("resource", "resource_file")]
fs.ULTIMI.update({"results": RESULTS, "bucket": {}, "moved": []})
fl.fill(bpy.context, fl.build_rows(GRAPH, RESULTS))
wm = bpy.context.window_manager
rows = [(x.file, x.versions) for x in wm.em_files]
print(f"[SMOKE]   rows: {rows}")
check("(6) v1 and v2 of US 2, the same bytes, are one version: no «v2/2»",
      ("US 2 · dopo A — proxy", "") in rows, str(rows))

# ── (1) the three panels ────────────────────────────────────────────────────
wm.em_files_index = next(i for i, x in enumerate(wm.em_files) if x.file.startswith("US 2"))
seen = {}
for idname in ("VIEW3D_PT_em_sync", "EM_PT_resources", "EM_PT_project_storage"):
    reset()
    cls = getattr(bpy.types, idname)
    try:
        draw_panel(cls)
    except Exception as exc:  # noqa: BLE001
        Rec.errors.append(f"draw: {exc}")
    seen[idname] = (list(Rec.labels), list(Rec.operators))
    print(f"[SMOKE]   {cls.bl_label}: {[t for t in Rec.labels if t]}")
    check(f"(1) «{cls.bl_label}» draws", not Rec.errors, "; ".join(Rec.errors))

room_labels = [t for t in seen["VIEW3D_PT_em_sync"][0] if t]
files_labels = [t for t in seen["EM_PT_resources"][0] if t]
check("(1)(10) Project storage is closed by default and says «No bucket» (no S3_* here)",
      "DEFAULT_CLOSED" in bpy.types.EM_PT_project_storage.bl_options
      and "No bucket" in seen["EM_PT_project_storage"][0]
      and not fl.bucket_alert("No bucket"))
check("(1) the panel B is «Files»", bpy.types.EM_PT_resources.bl_label == "Files")

# ── (2) names, never codes ──────────────────────────────────────────────────
coded = [t for labels, _ops in seen.values() for t in labels if CODE.search(t or "")]
check("(2) no visible label holds an ORCID, a hex ≥12 or a UUID", not coded, str(coded))

# ── (6) each thing once ─────────────────────────────────────────────────────
check("(6) the room's name whole (wrapped, never cut)",
      " ".join(room_labels).count("Tavolo · prova multiutente del 12 ottobre") == 1
      or "".join(room_labels).replace(" ", "").count("Tavolo·provamultiutentedel12ottobre") == 1,
      str(room_labels[:3]))
check("(6) who you are once: «Editor Due · editor · em.localhost:8443»",
      room_labels.count("Editor Due · editor · em.localhost:8443") == 1
      and sum("em.localhost" in t for t in room_labels) == 1, str(room_labels))
check("(6) one state of the room", sum("ligned" in t for t in room_labels) == 1
      and "● Aligned" in room_labels)
check("(6) Sync the scene… is there, with the short commands",
      ("em.scene_check", "Sync the scene…") in seen["VIEW3D_PT_em_sync"][1]
      and ("em.where_change", "Change…") in seen["VIEW3D_PT_em_sync"][1])
check("(6) Files says itself in one sentence, no Check files, no Keep the N",
      files_labels[0] == fl.summary_line(fl.row_counts(wm.em_files), True)
      and files_labels[0].startswith(f"{len(wm.em_files)} files")
      and not any(t.startswith(("Check files", "Keep the")) for t in files_labels),
      str(files_labels[:2]))
check("(6) one Download in the head, ↻ beside it",
      ("em.files_keep", "Download") in seen["EM_PT_resources"][1]
      and ("em.files_check", "") in seen["EM_PT_resources"][1])
check("(6) no Withdrawn box, no «Where it comes from» box, no bucket in Files",
      not any(t.startswith(("Withdrawn", "Where it comes from", "Bucket")) for t in files_labels))

# ── (3) «Open in EMStudio» once in the whole N-panel ────────────────────────
opened, drawn, skipped = [], 0, []
for name in dir(bpy.types):
    cls = getattr(bpy.types, name, None)
    if not (isinstance(cls, type) and issubclass(cls, bpy.types.Panel)):
        continue
    if getattr(cls, "bl_space_type", "") != "VIEW_3D" or getattr(cls, "bl_region_type", "") != "UI":
        continue
    if not getattr(cls, "__module__", "").startswith("emtools_wc"):
        continue
    reset()
    try:
        if hasattr(cls, "poll") and not cls.poll(bpy.context):
            pass
        draw_panel(cls)
        drawn += 1
    except Exception as exc:  # noqa: BLE001 — a panel that needs a real scene
        skipped.append(f"{name}: {str(exc)[:60]}")
    opened += [name for _id, text in Rec.operators if text == "Open in EMStudio"]
for menu in ("EM_MT_room_more",):
    reset()
    getattr(bpy.types, menu).draw(_Self(), bpy.context)
    opened += [menu for _id, text in Rec.operators if text == "Open in EMStudio"]
    check("(3) the ⋯ menu: Archive this .blend, Leave the room",
          ("em.blend_backup_archive", "Archive this .blend") in Rec.operators
          and ("em.room_leave", "Leave the room") in Rec.operators)
print(f"[SMOKE]   panels drawn: {drawn}; not drawable headless: {skipped}")
check("(3) «Open in EMStudio» once in the N-panel", opened == ["VIEW3D_PT_em_sync"], str(opened))

# ── (4) the Data Tree in a room is one row ──────────────────────────────────
et = bpy.context.scene.em_tools
row = et.graphml_files.add()
row.name = ROOM
row.origin_kind = "ROOM"
row.origin_room = ROOM
row.origin_node = "https://em.localhost:8443/em"
et.active_file_index = len(et.graphml_files) - 1
reset()
graph_tree.draw_graph_tree(Rec(), bpy.context, et)
tree_text = [t for t in Rec.labels if t]
print(f"[SMOKE]   tree: {tree_text} · rows {Rec.rows}")
check("(4) the Data Tree in a room is one row", Rec.rows == 1 and tree_text == [TITLE],
      f"{Rec.rows} {tree_text}")
check("(8) no Heriverse hexagon in the row", "is_publishable" not in Rec.props, str(Rec.props))
graph_tree.in_room = lambda: True        # the harness's room, as fl._in_room
reset()
graph_tree.draw_toolbar(Rec(), bpy.context, et, {"indice": et.active_file_index})
check("(8) in a room the bar of the tree is the ▾ alone",
      not Rec.operators, str(Rec.operators))
check("(4) «the study in the room» and «Writing in» went to the tooltip",
      "the study in the room" in bpy.types.EM_OT_graph_activate.description(
          bpy.context, type("P", (), {"index": et.active_file_index})()))

# ── (5) «Replace» only with this resource's object ──────────────────────────
mesh = bpy.data.meshes.new("m")
us3 = bpy.data.objects.new("US 3", mesh)
us2 = bpy.data.objects.new("US 2 · dopo A", mesh)
for obj, uid in ((us3, "US3"), (us2, "US2")):
    bpy.context.scene.collection.objects.link(obj)
    obj["em_resource_id"] = IDS["US2v2" if uid == "US2" else uid]
    obj["em_rm_node_id"] = uid
bpy.context.view_layer.objects.active = us3
reset()
fl.draw(Rec(), bpy.context, RESULTS)
check("(5) US 3 active: no «Replace» in the card of US 2",
      not any(i == "em.files_replace" for i, _t in Rec.operators))
check("(5) …and the operator's poll says no", not bpy.ops.em.files_replace.poll())
bpy.context.view_layer.objects.active = us2
reset()
fl.draw(Rec(), bpy.context, RESULTS)
check("(5) US 2 active: «Replace with the selected object (US 2 · dopo A)»",
      ("em.files_replace", "Replace with the selected object (US 2 · dopo A)") in Rec.operators)
check("(5) …and the poll says yes", bpy.ops.em.files_replace.poll())

# ── the card's Details: provenance in words, the ORCID only there ───────────
wm.em_files_details = True
reset()
fl.draw(Rec(), bpy.context, RESULTS)
print(f"[SMOKE]   details: {[t for t in Rec.labels if t][-12:]}")
check("Details: where it comes from, in words",
      "No record of how it was made" in Rec.labels)
check("Details: the version with the same bytes is there, by name",
      "Same bytes as v1" in Rec.labels
      and any(t.endswith(IDS["US2v2"]) and "Editor Due" in t for t in Rec.labels))
wm.em_files_details = False

# ── (7) one «Open in EMStudio» ──────────────────────────────────────────────
check("(7) one «Open in EMStudio» operator registered",
      hasattr(bpy.types, "EM_OT_open_in_emstudio")
      and not hasattr(bpy.types, "EM_OT_room_open_elsewhere"))

# ── (9) one window, in steps; the node is one row ───────────────────────────
windows = importlib.import_module("emtools_wc.sync_manager.windows")
nc = importlib.import_module("emtools_wc.sync_manager.node_choice")
NODE = "https://em.localhost:8443/em"
MAC = "http://macbook-pro-di-emanuel.local:8000"
nc.FOUND.clear()
nc.FOUND.update({"local": [{"url": "http://localhost:8000", "reachable": True, "version": "1.6.0.dev17"},
                           {"url": NODE, "reachable": True, "version": "1.6.0.dev17"}],
                 "lan": [], "saved": [{"url": MAC, "reachable": True, "version": "1.6.0.dev17"}],
                 "typed": []})
nc.IDENTITY.update({"http://localhost:8000": NODE, NODE: NODE, MAC: NODE})
bpy.context.scene.em_room_url = NODE
windows._STEPPING["busy"] = True          # no network from the step's update
openers = {"em.node_choose", "em.room_enter", "em.where_change", "em.room_enter_choice"}
for step in ("places", "node", "rooms"):
    wm.em_where_step = step
    reset()
    windows.draw_window(Rec(), bpy.context)
    inside = [i for i, _t in Rec.operators if i in openers]
    print(f"[SMOKE]   step {step}: {[t for t in Rec.labels if t][:14]}")
    check(f"(9) step «{step}» draws, and opens no window from inside the window",
          not Rec.errors and not inside, "; ".join(Rec.errors) + str(inside))
    if step == "node":
        hosts = [t for t in Rec.labels if "1.6.0.dev17" in t]
        check("(9) the three addresses of the node are ONE row, in use, without Use",
              len(hosts) == 1 and "● in use" in Rec.labels
              and not any(i == "em.node_use" for i, _t in Rec.operators), str(hosts))
        check("(9) no «there is a node…», no «Turn on a node…» when one is in use",
              not any(t.startswith("There is a node") or t.startswith("Turn on") for t in Rec.labels))
    if step == "places":
        check("(9) in a room, the room is marked and «With EMStudio» is not",
              any(t.startswith("In the room") for t in Rec.labels))
windows._STEPPING["busy"] = False

# ── (11) «Replace» not with an object of a version not in use ───────────────
v3 = gov._rr().revise_files(GRAPH, IDS["US2v2"], [{"path": "x.glb", "checksum": "sha256:" + "a0" * 32,
                                                   "url": "u", "size_bytes": 1}],
                            force=True)["new_resource_id"]
GRAPH.find_node_by_id(v3).data.update({"checksum": "sha256:" + "a0" * 32, "residency": "resident"})
# v3 exists, the citation stays on v2: US 2.001 is bound to v3, not in use
us2b = bpy.data.objects.new("US 2.001", mesh)
bpy.context.scene.collection.objects.link(us2b)
us2b["em_resource_id"], us2b["em_rm_node_id"] = v3, "US2"
us2b["em_asset_sha256"] = "sha256:" + "a0" * 32
bpy.context.view_layer.objects.active = us2b
reset()
fl.draw(Rec(), bpy.context, RESULTS)
check("(11) US 2.001 (a version not in use) active: no «Replace»",
      not any(i == "em.files_replace" for i, _t in Rec.operators)
      and not bpy.ops.em.files_replace.poll(), str(Rec.operators))

addon.unregister()
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
