"""Headless inventory · T-T1/Z1/N1, «Where you work» measured state by state.
MICRO-EMTOOLS-PANNELLO (30 Oct 2026): no longer a panel — the chip at the head
of the EM Data Tree and the menu EM ▸ Mode it opens are what is measured.

The fake layout is COPIED from the desk's script
(`_datasets/SegniSanPietro/_lavoro-claude/script/inventario_pannello_room.py`,
left untouched there); here it also keeps each label's icon, so an
explanatory INFO line can be told from a zone. Headless, the .blend is NOT
saved; the room part runs on the dev node as the user `dev` of `em-dev`.

    cd ~/Documents/GitHub/stratigraph-server/dev-stack
    EM_DEV_TOKEN=$(./token.sh) EM_NODE=http://localhost:8000 \\
    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        ~/Documents/GitHub/_datasets/templu-mare-prove/GreatTemple_2026_v3_multigraph_test_CLAUDE.blend \\
        --python ~/Documents/GitHub/EM-blender-tools/tests/blender_inventory_where_you_work.py -- /tmp/inv.json

Measured: the tabs of every EM Tools panel (EM and EM Scene, no «EM Room»);
the four states (the file as it opens, on this computer, with EMStudio, in a
room) with their commands — 3 / 2 / 4 + the menu; no INFO line outside the
zones; no red alarm when the test file opens; EM ▸ Export opens its four
dialogs.
"""
import json
import os
import sys
import time
import traceback

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = ARGS[0] if ARGS else "/tmp/inventario_where.json"
NODE = os.environ.get("EM_NODE", "http://localhost:8000")
TOKEN = os.environ.get("EM_DEV_TOKEN", "")
FAILURES = []


def check(label, condition, detail=""):
    print(f"[INV] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def mod(suffix):
    names = [n for n in sys.modules if n.endswith("." + suffix) and n.startswith("bl_ext.")]
    return sys.modules[names[0]]


# ── the fake layout (copied; + the icon of each label) ─────────────────────

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


def measure(name):
    """MICRO-EMTOOLS-PANNELLO (30 Oct 2026) · «Where you work» is no longer a
    panel: its FIRST ROW of the EM Data Tree (the chip, `em.where_menu`, and
    the row of a fix when there is one) and the menu the chip opens, EM ▸ Mode
    (the places, then the commands of the place)."""
    tree = draw_with(bpy.types.VIEW3D_PT_EM_Tools_Setup)
    menu = draw_with(bpy.types.EM_MT_mode)
    excs = [r for r in tree + menu if r["k"] == "EXC"]
    try:
        first = next(i for i, r in enumerate(tree) if r.get("id") == "em.where_menu")
    except StopIteration:
        first = -1
    try:
        sep = next(i for i, r in enumerate(menu) if r["k"] == "sep")
    except StopIteration:
        sep = len(menu)
    places, below = menu[:sep], menu[sep + 1:]
    commands = [r for r in below if r["k"] == "op"]
    chip = tree[first] if first >= 0 else {}
    # the row of a fix: an op right after the chip's row that is not the
    # bar's (+ − ▾, the room's Sync)
    alerts = [r for r in tree if r.get("alert")]
    STATES[name] = {"tree": tree[:14], "menu": menu,
                    "chip": chip.get("text"), "chip_index": first,
                    "places": [r.get("text") for r in places if r["k"] in ("op", "label")],
                    "commands": [c["text"] or c["id"] for c in commands],
                    "command_ids": [c["id"] for c in commands],
                    "menus": [m["id"] for m in below if m["k"] == "menu"],
                    "labels_tree": [r.get("text") for r in tree if r["k"] == "label"],
                    "ops_tree": [r.get("id") for r in tree if r["k"] == "op"],
                    "exceptions": excs, "alerts": alerts}
    print(f"[INV] {name}: chip {STATES[name]['chip']!r} at {first}")
    print(f"[INV] {name}: places {STATES[name]['places']}")
    print(f"[INV] {name}: commands {STATES[name]['commands']} menus {STATES[name]['menus']}")
    check(f"{name}: drawn without an exception", not excs, str(excs[:1]))
    check(f"{name}: the chip is the first command of the EM Data Tree",
          first >= 0 and not any(r["k"] == "op" for r in tree[:first]), str(tree[:first + 1]))
    return STATES[name]


STATES = {}
RESULT = {"states": STATES}


def tabs():
    """Every registered panel of EM Tools and its tab, read off Blender."""
    pkg = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")][0]
    pkg = pkg.rsplit(".graph_origins", 1)[0]
    out = {}
    for cls in bpy.types.Panel.__subclasses__():
        if not str(getattr(cls, "__module__", "")).startswith(pkg):
            continue
        if getattr(cls, "bl_space_type", "") != "VIEW_3D" or getattr(cls, "bl_parent_id", ""):
            continue
        cat = getattr(cls, "bl_category", "")
        out.setdefault(cat, []).append(getattr(cls, "bl_label", cls.__name__))
    return out


def run():
    sc = bpy.context.scene
    ops = mod("sync_manager.operators")
    rs = mod("sync_manager.room_session")
    room_cfg = mod("sync_manager.room")

    found = tabs()
    RESULT["tabs"] = found
    print("[INV] tabs:", {k: len(v) for k, v in found.items()})
    check("two tabs, EM and EM Scene", set(found) == {"EM", "EM Scene"}, str(sorted(found)))
    check("no «EM Room»", "EM Room" not in found)
    check("no panel «Where you work» (the first row of the EM Data Tree)",
          "Where you work" not in sum(found.values(), []))
    check("the EM Data Tree is in EM", "EM Data Tree" in found.get("EM", []))
    # P3 (6 Oct 2026) · EM Scene is EMStudio's two spaces, then the Deck
    check("EM Scene: Contents, Space, then the Publication Deck",
          found.get("EM Scene", []) and
          set(found.get("EM Scene", [])) == {"Contents", "Space", "Publication Deck"},
          str(found.get("EM Scene")))
    # MICRO tre pannelli (13 Oct 2026) · Files, then Project storage (closed)
    check("Files (once Storage) is in Contents, Project storage after it",
          bpy.types.EM_PT_resources.bl_label == "Files"
          and bpy.types.EM_PT_resources.bl_parent_id == "EM_PT_scene_contents"
          and bpy.types.EM_PT_project_storage.bl_parent_id == "EM_PT_scene_contents")
    check("no Export Manager, no Export statistics panel",
          not ({"Export Manager", "Export statistics"} & set(sum(found.values(), []))))

    # ── 1 · the file as it opens (saved declaring Sidecar) ────────────────
    RESULT["declared"] = sc.em_session_mode
    st = measure("1_opened")
    check("1: no red alarm when the file opens", not st["alerts"], str(st["alerts"][:2]))
    if RESULT["declared"] != "standalone":
        check("1: the fix in sight under the chip: where this file worked last",
              any("Last time this file worked" in (t or "") for t in st["labels_tree"]),
              str(st["labels_tree"][:4]))

    # ── 2 · on this computer ───────────────────────────────────────────────
    bpy.ops.em.set_mode(mode=ops.MODE_STANDALONE)
    st = measure("2_here")
    check("2: the chip says On this computer", st["chip"] == "On this computer", str(st["chip"]))
    check("2: the places: With EMStudio, In a collaborative room…, Choose the node…",
          {"With EMStudio", "In a collaborative room…", "Choose the node…"} <= set(st["places"]),
          str(st["places"]))
    check("2: under them Create a collaborative room… and Log…",
          st["command_ids"] == ["em.room_bring", "em.sync_log"], str(st["command_ids"]))
    check("2: no line of state in the tree", not any(
        "On this computer ·" in (t or "") or "none needed here" in (t or "")
        for t in st["labels_tree"]), str(st["labels_tree"][:4]))

    # ── 3 · with EMStudio ──────────────────────────────────────────────────
    bpy.ops.em.set_mode(mode=ops.MODE_SIDECAR)
    time.sleep(0.5)
    st = measure("3_emstudio")
    check("3: the chip says With EMStudio", st["chip"] == "With EMStudio", str(st["chip"]))
    check("3: Stop = the place On this computer", "On this computer" in st["places"], str(st["places"]))
    check("3: Permissions… and Log…",
          st["command_ids"] == ["em.sidecar_permissions", "em.sync_log"], str(st["command_ids"]))
    bpy.ops.em.set_mode(mode=ops.MODE_STANDALONE)

    # ── 4 · in a room ──────────────────────────────────────────────────────
    if TOKEN:
        # the study of slot 0, its GraphML copied to a temporary folder first
        # (loading writes an em.json beside it; the .blend is not saved)
        import shutil, tempfile
        row0 = sc.em_tools.graphml_files[0]
        src0 = bpy.path.abspath(row0.graphml_path)
        if src0.lower().endswith(".graphml"):
            dst0 = os.path.join(tempfile.mkdtemp(prefix="em-inv-"), os.path.basename(src0))
            shutil.copy2(src0, dst0)
            row0.graphml_path = dst0
        sc.em_tools.active_file_index = 0
        getattr(bpy.ops, "import").em_graphml(graphml_index=0)
        sc.em_room_url = NODE
        room_cfg.set_room(NODE, None, TOKEN)
        name = f"T-Z1 {int(time.time())}"
        r = bpy.ops.em.room_bring(name=name, confirm=True)
        check("4: a room created from this study", r == {"FINISHED"}, str(r))
        RESULT["room"] = room_cfg.room().get("room_id")
        bpy.ops.em.scene_check(send="NONE")
        st = measure("4_room")
        # MICRO-EMTOOLS-PANNELLO · the chip names the room, Sync stays an icon
        # on its row; Open in EMStudio · Change… · Room ⋯ · Log… in the menu
        check("4: the chip names the room", (st["chip"] or "").startswith("Room: "), str(st["chip"]))
        check("4: Sync the scene on the chip's row", "em.scene_check" in st["ops_tree"])
        check("4: Sync, Open in EMStudio, Change…, Room and Log… in EM ▸ Mode",
              {"Sync the scene…", "Open in EMStudio", "Change…", "Log…"} <= set(st["commands"])
              and "EM_MT_room_more" in st["menus"], str(st["commands"]))
        check("4: no Create inside a room",
              not any("Create a collaborative room" in c for c in st["commands"]))
        RESULT["menu_room"] = draw_with(bpy.types.EM_MT_room_more)
        files = draw_with(bpy.types.EM_PT_resources)
        RESULT["files"] = files
        check("F1: Files draws", not any(r["k"] == "EXC" for r in files), str(files[-1:]))
        project = draw_with(bpy.types.EM_PT_project_storage)
        check("F1: the project folder is a menu, in Project storage",
              any(r.get("id") == "EM_MT_project_folder" for r in project)
              and not any(r.get("id") == "EM_MT_project_folder" for r in files))
        check("F1: no Promote to object store, no object-store section",
              not any("Object store" in str(r.get("text")) or "resources_promote" in str(r.get("id")) for r in files))
        check("F1: no «EM Setup» left in its words",
              not any("EM Setup" in str(r.get("text")) for r in files))
        versions = draw_with(bpy.types.VIEW3D_PT_em_asset_versions)
        check("F1: no scene package in Asset versions",
              not any("package" in str(r.get("id")) or "package" in str(r.get("text")).lower()
                      for r in versions), str([r.get("text") for r in versions][:6]))
        check("F1: Project storage has the archives of the .blend and the package",
              any("Archives of this .blend" in str(r.get("text")) for r in project)
              and any(r.get("id") == "em.scene_package_archive" for r in project),
              str(project[:3]))
        ops.leave_room()
    else:
        print("[INV] no EM_DEV_TOKEN: the room state is skipped")

    # ── EM ▸ Export opens its four dialogs ─────────────────────────────────
    menu = draw_with(bpy.types.EM_MT_export)
    RESULT["export_menu"] = menu
    entries = [r for r in menu if r["k"] == "op"]
    check("EM ▸ Export: four entries",
          len(entries) == 4, str([e["text"] for e in entries]))
    dialogs = mod("export_manager.dialogs")
    for e in entries:
        if e["id"] == "em.export_dialog":
            pid = e["args"]["provider"]
            fake = type("F", (object,), {"provider": pid, "layout": None})()
            out = []
            fake.layout = Lay(out)
            try:
                bpy.types.EM_OT_export_dialog.draw(fake, bpy.context)
                ok = not any(r["k"] == "EXC" for r in out) and len(out) > 1
            except Exception as exc:  # noqa: BLE001
                ok, out = False, [{"k": "EXC", "text": str(exc)}]
            check(f"the {pid} dialog draws its exporter", ok, str(out[:2]) if not ok else f"{len(out)} rows")
            check(f"…and {pid} opens as a dialog", hasattr(bpy.types, "EM_OT_export_dialog"))
        else:
            out = draw_with(bpy.types.EM_OT_export_statistics_dialog)
            check("the statistics dialog draws", not any(r["k"] == "EXC" for r in out)
                  and any(r.get("id") == "export_mesh.csv" for r in out), str(out[:2]))
    check("the header menu has Export", any(r.get("id") == "EM_MT_export"
                                             for r in draw_with(bpy.types.EM_MT_header)))


try:
    run()
except Exception:
    RESULT["fatal"] = traceback.format_exc()
    FAILURES.append("fatal")
    print(RESULT["fatal"])
with open(OUT, "w") as fh:
    json.dump(RESULT, fh, indent=1, ensure_ascii=False, default=str)
print("[INV] written", OUT)
print("[INV] RESULT:", "ALL PASS" if not FAILURES else f"FAILED {FAILURES}")
sys.stdout.flush()
os._exit(0 if not FAILURES else 1)
