"""Headless smoke · T-D1, «Where it comes from»: the DTC of one asset as a
card in the four lists that have a selection — on the COPY of Templu Mare.

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        <copy of GreatTemple_2026_v3_multigraph_test_CLAUDE.blend> \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_smoke_provenance_card.py -- rm
    EM_DEV_TOKEN=$(./token.sh) … <copy of a .blend saved in its room> … -- dosco

`rm` on the copy of Templu Mare (its GraphML has no DosCo: the 70 files the
resolver finds there are 66 proxies, 2 extractors, 1 RM — measured); `dosco`
in the room the study lives in, where the DosCo files are.

(1) ME_PODIO gets a version for the web («Prepare for a use…»): its card says
the lod_generation step, its technique, the tool and the master as input — in
Asset versions with the version shown, and in the RM list; (2) a file of the
DosCo: its card under Files (its row's button), and in the Document Manager for its
document; (3) Files draws no DTC section any more.
"""
import importlib
import os
import shutil
import sys
import tempfile
import traceback

import bpy

FAILURES = []


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


class Op:
    def __init__(self, rec): object.__setattr__(self, "_rec", rec)
    def __setattr__(self, k, v): self._rec.setdefault("args", {})[k] = str(v)[:60]


class Lay:
    def __init__(self, out, depth=0, flags=None):
        object.__setattr__(self, "_out", out)
        object.__setattr__(self, "_d", depth)
        object.__setattr__(self, "_f", dict(flags or {}))
    def __setattr__(self, k, v):
        self._f[k] = v
    def __getattr__(self, k):
        if k in self._f: return self._f[k]
        if k in ("alert", "enabled", "active", "use_property_split"): return False
        if k in ("scale_y", "scale_x", "ui_units_x"): return 1.0
        def anything(*a, **kw): return Lay(self._out, self._d + 1, self._f)
        return anything
    def _child(self, kind):
        self._out.append({"d": self._d, "k": kind})
        return Lay(self._out, self._d + 1, self._f)
    def row(self, *a, **kw): return Lay(self._out, self._d, self._f)
    def column(self, *a, **kw): return Lay(self._out, self._d, self._f)
    def split(self, *a, **kw): return Lay(self._out, self._d, self._f)
    def grid_flow(self, *a, **kw): return Lay(self._out, self._d, self._f)
    def box(self): return self._child("box")
    def separator(self, *a, **kw): self._out.append({"d": self._d, "k": "sep"})
    def _flags(self):
        return {k: v for k, v in self._f.items() if k in ("alert", "enabled") and (v if k == "alert" else v is False)}
    def label(self, text="", icon="NONE", **kw):
        self._out.append({"d": self._d, "k": "label", "text": text, "icon": icon, **self._flags()})
    def operator(self, idname, text=None, icon="NONE", depress=False, **kw):
        rec = {"d": self._d, "k": "op", "id": idname, "text": text if text is not None else "", "depress": bool(depress), **self._flags()}
        self._out.append(rec); return Op(rec)
    def prop(self, data, prop, text=None, **kw):
        self._out.append({"d": self._d, "k": "prop", "id": prop, "text": text if text is not None else "", "expand": bool(kw.get("expand")), **self._flags()})
    def template_list(self, uitype, list_id, *a, **kw):
        self._out.append({"d": self._d, "k": "list", "id": f"{uitype}:{list_id}"})
    def template_icon(self, *a, **kw): pass
    def menu(self, name, text="", **kw):
        self._out.append({"d": self._d, "k": "menu", "id": name, "text": text})


def draw_with(cls, method="draw"):
    out = []
    fake_cls = type("F", (object,), {k: v for k, v in vars(cls).items()
                                     if callable(v) or isinstance(v, (staticmethod, classmethod))})
    fake = fake_cls()
    fake.layout = Lay(out)
    try:
        getattr(cls, method)(fake, bpy.context)
    except Exception as exc:
        out.append({"k": "EXC", "text": f"{type(exc).__name__}: {exc}",
                    "tb": traceback.format_exc()[-600:]})
    return out


def draw_with(cls):
    out = []
    fake_cls = type("F", (object,), {k: v for k, v in vars(cls).items()
                                     if callable(v) or isinstance(v, (staticmethod, classmethod))})
    fake = fake_cls()
    fake.layout = Lay(out)
    try:
        cls.draw(fake, bpy.context)
    except Exception as exc:
        out.append({"k": "EXC", "text": f"{type(exc).__name__}: {exc}",
                    "tb": traceback.format_exc()[-600:]})
    return out


def card_of(drawn):
    """The lines of the card in a drawn panel ([] when there is none)."""
    try:
        i = next(n for n, r in enumerate(drawn)
                 if r["k"] == "label" and r.get("text") == "Where it comes from")
    except StopIteration:
        return []
    out = []
    for r in drawn[i + 1:]:
        if r["k"] == "op" and r["id"] == "em.open_in_emstudio":
            out.append("[Open in EMStudio]")
            break
        if r["k"] == "label":
            out.append(r["text"])
    return out


names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
pc = importlib.import_module(PKG + ".provenance_card")
fs = importlib.import_module(PKG + ".sync_manager.file_states")
scene = bpy.context.scene
PART = (sys.argv[sys.argv.index("--") + 1:] or ["rm"])[0] if "--" in sys.argv else "rm"
from s3dgraphy import get_graph  # noqa: E402


def _data(n):
    return getattr(n, "data", None) or {}


if PART == "rm":
    row0 = scene.em_tools.graphml_files[0]
    src0 = bpy.path.abspath(row0.graphml_path)
    if src0.lower().endswith(".graphml"):
        dst0 = os.path.join(tempfile.mkdtemp(prefix="em-d1-"), os.path.basename(src0))
        shutil.copy2(src0, dst0)
        row0.graphml_path = dst0
    scene.em_tools.active_file_index = 0
    getattr(bpy.ops, "import").em_graphml(graphml_index=0)
    graph = get_graph(scene.em_tools.graphml_files[0].name)

    # ── (1) an RM with versions ────────────────────────────────────────────
    obj = bpy.data.objects["ME_PODIO"]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    r = bpy.ops.em.asset_prepare_for_use(use={"web"}, ratio=0.5, max_texture=1024, draco=True)
    check("ME_PODIO has a version for the web", r == {"FINISHED"}, str(r))
    web = [n for n in graph.nodes if _data(n).get("tier") == "distribution"
           and "web" in (_data(n).get("use") or [])]
    check("…in the graph", bool(web), str(len(web)))
    levels = [lv for lv in av.levels_of(obj) if lv != "master"]
    check("…as a level of ME_PODIO", bool(levels), str(levels))
    bpy.ops.em.asset_set_level(level=levels[0], scope="ACTIVE")
    shown = pc.resource_of_object(graph, obj, scene)
    check("the object shows the version", bool(web) and shown == web[-1].node_id,
          f"{shown} level {levels[0]}")
    card = card_of(draw_with(bpy.types.VIEW3D_PT_em_asset_versions))
    print("[SMOKE]   Asset versions:", card)
    check("Asset versions: the card of the version shown",
          any("lod_generation" in l and "decimation" in l for l in card), str(card))
    check("…when and with which tool", any(l.startswith("by ") or l.startswith("on ")
                                            for l in card), str(card))
    check("…the master as its input", any(l.startswith("from:") for l in card), str(card))
    check("…and Open in EMStudio", card[-1:] == ["[Open in EMStudio]"], str(card[-1:]))
    rm_idx = next((i for i, it in enumerate(scene.rm_list) if it.name == "ME_PODIO"), -1)
    check("ME_PODIO is in the RM list", rm_idx >= 0, str(len(scene.rm_list)))
    scene.rm_list_index = rm_idx
    card = card_of(draw_with(bpy.types.VIEW3D_PT_RM_Manager))
    print("[SMOKE]   RM list:", card)
    check("RM list: the same card", any("lod_generation" in l for l in card), str(card))
    bpy.ops.em.asset_set_level(level="master", scope="ACTIVE")
    card = card_of(draw_with(bpy.types.VIEW3D_PT_em_asset_versions))
    print("[SMOKE]   Asset versions, master shown:", card)
    check("the master's card: used by the step that made the version",
          any(l.startswith("used by") for l in card), str(card))
else:
    # ── (2) a file of the DosCo, in the room ───────────────────────────────
    room_cfg = importlib.import_module(PKG + ".sync_manager.room")
    room_cfg.set_room(scene.em_room_url, scene.em_room_id, os.environ.get("EM_DEV_TOKEN", ""))
    bpy.ops.em.room_reconnect()
    ok, graph = importlib.import_module(PKG + ".functions").is_graph_available(bpy.context)
    check("in the room, the study's graph", ok and graph is not None)
    bpy.ops.em.files_check()
    results = fs.ULTIMI.get("results") or []
    check("Files: resolved", bool(results), str(len(results)))
    doc_res = None
    for d in graph.nodes:
        if getattr(d, "node_type", "") != "document":
            continue
        rid = pc.resource_linked_to(graph, d.node_id)
        if rid and any(r["id"] == rid for r in results):
            doc_res = (d, rid)
            break
    check("a document of the DosCo with its file", doc_res is not None)
    d, rid = doc_res
    bpy.context.window_manager.em_provenance_resource = rid
    drawn = draw_with(bpy.types.EM_PT_resources)
    card = card_of(drawn)
    print("[SMOKE]   Files:", d.name, card)
    check("Files: the card of the row chosen", len(card) >= 2, str(card))
    check("…with the file's sign", bool(card) and card[0][:1] in "●☁◉↗✕◌", str(card[:1]))
    check("…named by its file, never «Link to …»", bool(card) and "Link to" not in card[0],
          str(card[:1]))
    check("Files: every row has its button", sum(1 for r in drawn if r["k"] == "op"
          and r["id"] == "em.provenance_show") >= 1)
    check("Files: no DTC section", not any(r["k"] == "prop"
          and "DTC" in (r.get("text") or "") for r in drawn))
    importlib.import_module(PKG + ".document_manager.data").sync_doc_list(scene)
    idx = next((i for i, it in enumerate(scene.doc_list) if it.node_id == d.node_id), -1)
    check("the document is in the Document Manager", idx >= 0, f"{d.name} of {len(scene.doc_list)}")
    if idx >= 0:
        scene.doc_list_index = idx
        card = card_of(draw_with(bpy.types.VIEW3D_PT_3DDocumentManager))
        print("[SMOKE]   Document Manager:", d.name, card)
        check("Document Manager: the card of its file", len(card) >= 2, str(card))
    importlib.import_module(PKG + ".sync_manager.operators").leave_room()
print("[SMOKE] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
sys.exit(0 if not FAILURES else 1)
