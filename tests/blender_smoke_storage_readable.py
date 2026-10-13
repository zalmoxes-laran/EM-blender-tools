"""Headless smoke · MICRO lo storage parla come una persona (13 Oct 2026) —
OFFLINE, on the working copy (not the installed extension).

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --factory-startup \\
        --python-use-system-env \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_storage_readable.py

Headless Blender has no region to draw in, so the Storage panel is drawn on a
RECORDING layout: every label is kept, every `prop` must name a property that
exists, every `operator` an operator that is registered. On the chain of US2
as the relay measured it (four versions) beside US1 and US5:

(1) one row each, by name, US2 «v4/4»; no row label holds a digest or a UUID;
(2) the card draws (name → state → versions → Details closed → gestures),
    the ✕ is in the row, the big red button is gone;
(3) «Use» on v1 through the operator: the citation moves, no node is born,
    the row says «v1/4»;
(4) «Where you work» puts the room's name whole and the host on its own line.
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


# ── the working copy, as an add-on package ──────────────────────────────────
PKG_DIR = "/tmp/storage-leggibile/pkg"
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
pc = importlib.import_module("emtools_wc.proxy_chain")
where = importlib.import_module("emtools_wc.sync_manager.where")
functions = importlib.import_module("emtools_wc.functions")

from s3dgraphy.graph import Graph  # noqa: E402
from s3dgraphy.nodes.stratigraphic_node import StratigraphicUnit  # noqa: E402

ROOM = "tavolo-2026-10-12"
HOSTS = ("http://localhost:8000", "https://em.localhost:8443/em",
         "http://MacBook-Pro-di-Emanuel.local:8000")
F4E4, E522 = "sha256:" + "f4e4" * 16, "sha256:" + "e522" * 16


def spec(d, host):
    return {"path": "US 2 · dopo A.glb", "url": gov.store_url(host, ROOM, d),
            "checksum": d, "size_bytes": 1234, "media_type": "model/gltf-binary"}


def the_room():
    g = Graph(ROOM)
    for uid, name, d in (("US1", "US 1", "sha256:" + "11" * 32),
                         ("US2", "US 2 · dopo A", F4E4),
                         ("US5", "US 5", "sha256:" + "55" * 32)):
        g.add_node(StratigraphicUnit(uid, name=name))
        rid = pc.ensure_unit_proxy(g, uid, name)["resource_id"]
        g.find_node_by_id(rid).data.update({"url": gov.store_url(HOSTS[0], ROOM, d),
                                            "checksum": d, "residency": "resident",
                                            "media_type": "model/gltf-binary"})
    rr = gov._rr()
    _s, res = pc.glb_proxy(g, "US2")
    ids, prev = [res.node_id], res.node_id
    for d, host in ((E522, HOSTS[1]), (F4E4, HOSTS[2]), (E522, HOSTS[1])):
        new = rr.revise_files(g, prev, [spec(d, host)], force=True)["new_resource_id"]
        g.find_node_by_id(new).data.update({"url": gov.store_url(host, ROOM, d),
                                            "checksum": d, "residency": "resident",
                                            "created_at": "2026-10-13T09:2%d:00Z" % len(ids),
                                            "created_by": "editor2"})
        rr.move_citations(g, prev, new, [c["edge_id"] for c in gov.citing(g, prev)])
        ids.append(new)
        prev = new
    return g, ids


GRAPH, IDS = the_room()
fake = lambda context=None: (True, GRAPH)          # noqa: E731 — the active graph
functions.is_graph_available = fake


class Rec:
    """A layout that records what it is asked to draw and checks it."""
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


def rows_now():
    results = [{"id": n.node_id, "state": "on_node", "node_type": n.node_type, "name": n.name}
               for n in GRAPH.nodes if getattr(n, "node_type", "") in ("resource", "resource_file")]
    rows = fl.build_rows(GRAPH, results)
    fl.fill(bpy.context, rows)
    return rows


CODE = re.compile(r"(?i)[0-9a-f]{12,}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

# (1) one row each, by name
rows = rows_now()
names = [r["file"] for r in rows]
print(f"[SMOKE]   rows: {[(r['file'], r['versions']) for r in rows]}")
check("one row each for US1, US2, US5", sorted(names) == sorted(
    ["US 1 — proxy", "US 2 · dopo A — proxy", "US 5 — proxy"]), str(names))
check("US2 says v4/4", next(r["versions"] for r in rows if r["file"].startswith("US 2")) == "v4/4")
check("no row label holds a digest or a UUID", not any(CODE.search(n) for n in names))

# (2) the rows and the card draw
wm = bpy.context.window_manager
for i, item in enumerate(wm.em_files):
    fl._CLASSES[1].draw_item(None, bpy.context, Rec(), None, item, 0, None, "", i)
check("the ✕ is in the row", ("em.files_withdraw", "") in Rec.operators)
wm.em_files_index = next(i for i, x in enumerate(wm.em_files) if x.file.startswith("US 2"))
Rec.labels.clear()
Rec.operators.clear()
fl.draw(Rec(), bpy.context, [])
print(f"[SMOKE]   card: {Rec.labels}")
check("the card draws without errors", not Rec.errors, "; ".join(Rec.errors))
check("the card names, never codes", not any(CODE.search(t) for t in Rec.labels),
      str([t for t in Rec.labels if CODE.search(t)]))
check("four versions, one line each, v4 in use",
      [t for t in Rec.labels if t.startswith("v")][-1].endswith("in use")
      and len([t for t in Rec.labels if re.match(r"^v\d( |$)", t)]) == 4)
check("a «Use» beside each version not in use",
      sum(1 for o in Rec.operators if o == ("em.files_use_version", "Use")) == 3)
check("the big red «Withdraw» is gone from the card",
      not any(o[0] == "em.files_withdraw" for o in Rec.operators))
check("Details is closed", not any(t in ("Digest", "Id") for t in Rec.labels))
wm.em_files_details = True
Rec.labels.clear()
fl.draw(Rec(), bpy.context, [])
check("Details opened shows the codes", "Digest" in Rec.labels and IDS[3] in Rec.labels)
wm.em_files_details = False

# (3) «Use» on v1: the pointer moves, nothing is born
before = len(GRAPH.nodes)
fl.show_in_scene = lambda context, graph, rid: {"kept": [], "said": "offline smoke"}
out = bpy.ops.em.files_use_version(resource_id=IDS[0])
check("«Use» runs", out == {"FINISHED"}, str(out))
check("no version is born", len(GRAPH.nodes) == before)
check("v1 is in use", gov.in_use(GRAPH, IDS[3]) == IDS[0])
rows = rows_now()
check("the row says v1/4", next(r["versions"] for r in rows if r["file"].startswith("US 2")) == "v1/4")

# (4) «Where you work»
z = where.zones({"place": "room", "room_title": "Tavolo · prova multiutente",
                 "node": "http://MacBook-Pro-di-Emanuel.local:8000", "members": 2,
                 "role": "editor", "author": "editor2"})
check("the room's name whole", z["place"][1] == "▣ Tavolo · prova multiutente · 2 present",
      z["place"][1])
check("the host on its own line", z["place_detail"][1] == "macbook-pro-di-emanuel.local:8000")

addon.unregister()
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILED: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
