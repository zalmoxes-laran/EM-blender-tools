"""Headless smoke · MICRO-CONSOLIDA-2 (E.D. 31 Oct 2026) on a COPY of Templu
Mare, Blender 5.2, EM Tools as the working copy, s3dgraphy of the working
tree (PYTHONPATH)::

    BO_PROJECT=/tmp/consolida2/D1 PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    BLENDER_USER_RESOURCES=<profile with EM Tools> \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python-exit-code 1 /tmp/consolida2/D1/SB/GreatTemple_2026_v2.blend \\
        --python tests/blender_smoke_consolida_2.py

1. «Consolidate for…» from the Deck: the files measured, lightness by
   default (why each model loads what it loads), the totals against the new
   bands, the container of the RB tileset with «Declare the master…»;
2. a version's file touched after its stamp: «Check files» says it, the
   Deck's row and «Check against the graph» say «modified after its stamp»;
   «Register as a new version» → the object shown has a newer revision;
3. «Declare the master…» of the tileset: the container's meshes.
The em.json on disk is never written."""
import hashlib
import json
import os
import shutil
import sys
import time

import bpy

PROJECT = os.environ.get("BO_PROJECT", "/tmp/consolida2/D1")
FAILURES = []
T = {}


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)
    return condition


def mod(suffix):
    for name, m in sys.modules.items():
        if name.endswith(suffix):
            return m
    raise RuntimeError(suffix + " not loaded")


class Layout:
    """A layout that records what a dialog draws (no window headless)."""
    lines: list = []

    def __getattr__(self, name):
        if name in ("row", "column", "box", "split"):
            return lambda *a, **k: Layout()
        if name == "label":
            return lambda text="", **k: Layout.lines.append(text)
        if name == "operator":
            return lambda op, text="", **k: (Layout.lines.append(f"[{op}] {text}"), Layout())[1]
        return lambda *a, **k: None

    def __setattr__(self, name, value):
        pass


def drawn(cls, **attrs):
    """Run an operator's ``draw`` on a recording layout; → the lines."""
    import types
    Layout.lines = []
    me = types.SimpleNamespace(layout=Layout(), **attrs)
    for name in dir(cls):
        if name.startswith("_") and callable(getattr(cls, name, None)) and not name.startswith("__"):
            setattr(me, name, types.MethodType(getattr(cls, name), me))
    cls.draw(me, bpy.context)
    return list(Layout.lines)


BO = mod(".sync_manager.blend_officina")
BD = mod(".sync_manager.blend_detail")
BC = mod(".sync_manager.blend_compose")
FS = mod(".sync_manager.file_states")
PH = mod(".publication_heriverse")
HD = mod(".publication_deck_ui.heriverse")
from s3dgraphy import api  # noqa: E402
from s3dgraphy.resources import consolidate as C, graph_compose as G  # noqa: E402
from s3dgraphy.resources.versions import asset_of, versions_of  # noqa: E402

emjson = os.path.join(PROJECT, "EM", "TempluMare_v6_optimized.em.json")
em_folder = os.path.dirname(emjson)
em_bytes = open(emjson, "rb").read()
ctx = bpy.context


def load_graph():
    emt = bpy.context.scene.em_tools
    emt.graphml_files.clear()
    row = emt.graphml_files.add()
    row.name = "TempluMare_v6"
    row.graphml_path = emjson
    row.is_publishable = True
    emt.active_file_index = 0
    getattr(bpy.ops, "import").em_emjson(file_index=0)
    graph, _doc, _f = BO.active_graph_doc(bpy.context)
    return graph


graph = load_graph()
check("graph loaded", graph is not None)
FS = mod(".sync_manager.file_states")
check("s3dgraphy with lightness by default", hasattr(C, "web_choice") and hasattr(G, "declare_tileset_master"))

# ── 1 · the Deck, measured ───────────────────────────────────────────────────
t0 = time.time()
deck = HD.make_consolidation(ctx, "heriverse")
T["deck"] = round(time.time() - t0, 2)
print("[SMOKE] DECK:", deck.get("say_it"), json.dumps(deck.get("counts"), default=str), f"{T['deck']} s")
for line in PH.totals_lines(deck):
    print("[SMOKE] DECK TOTAL:", line)
rows = deck.get("rows") or []
why = {}
for r in rows:
    why[r.get("loaded_why")] = why.get(r.get("loaded_why"), 0) + 1
print("[SMOKE] LOADED WHY:", why)
check("the web loads light by default (the lightest lod1 where there is no base)", why.get("lightest", 0) > 0, why)
measured = [r for r in rows if (r.get("loaded") or {}).get("measured")]
check("the files measured on this disk", len(measured) >= 80, len(measured))
tot = (deck.get("totals") or [{}])[0].get("platform") or {}
check("the scene's GPU measured: textures once, under the old 10 GB estimate",
      0 < tot.get("gpu_bytes", 0) < 2 * 1024 ** 3 and tot.get("shared_textures", 0) > 0,
      (tot.get("gpu_bytes"), tot.get("shared_textures")))
grp = next((r for r in rows if r.get("kind") == "container" and r.get("loaded_why") == "tileset"), None)
check("the container of the tileset has its row, base = its lowest level", grp is not None and grp.get("base")
      and "livello più basso" in (grp["base"].get("note") or ""), grp and grp.get("name"))
acts = {a["kind"]: a for a in PH.row_actions(grp or {})}
check("«Declare the master…» offered on it", "declare_master" in acts, list(acts))
HD.LAST.update(consolidated=deck, plan=HD.make_plan(ctx), folder="/tmp/x")
lines = drawn(HD.EM_OT_deck_heriverse, road="NODE", platform="heriverse")
check("the Deck draws «Declare the master…»", any(x.startswith("[em.deck_declare_tileset_master]") for x in lines),
      [x for x in lines if x.startswith("[")][:4])
check("the new operators are registered", hasattr(bpy.ops.em, "deck_register_new_version")
      and hasattr(bpy.ops.em, "deck_declare_tileset_master"))

# ── 2 · a version's file touched after its stamp ────────────────────────────
col = bpy.data.objects.get("Column_entrance1")
check("Column_entrance1 in the .blend", col is not None)
rm = next(n.node_id for n in graph.nodes if getattr(n, "name", "") == "Column_entrance1"
          and "representation_model" in str(getattr(n, "node_type", "")))
asset = next(e.edge_target for e in graph.edges if e.edge_type == "has_linked_resource" and e.edge_source == rm)
asset = asset_of(graph, asset)
lod0 = next(dict(e, asset_id=asset) for e in versions_of(graph, asset) if e.get("level") == "lod0")
BC.write_tags(col, G.graph_tags(graph, rm, lod0))
glb = os.path.normpath(os.path.join(em_folder, lod0["url"]))
with open(glb, "ab") as fh:
    fh.write(b"\0" * 8)                      # touched after the stamp (a glb still)
now = "sha256:" + hashlib.sha256(open(glb, "rb").read()).hexdigest()
t0 = time.time()
res = FS.resolve_active(ctx, graph)
T["check_files"] = round(time.time() - t0, 2)
changed = [r for r in res if r.get("changed")]
check("«Check files» says the file modified after its stamp", any(r["id"] == lod0["id"] for r in changed),
      [(r["name"], r["state"]) for r in changed if "master" not in r["id"]][:4])
deck = HD.make_consolidation(ctx, "heriverse")
row = next(r for r in deck["rows"] if r["id"] == rm)
mod_f = [f for f in row["findings"] if f["code"] == "modified_after_stamp"]
check("the Deck's row: «modificata dopo il timbro»", bool(mod_f) and mod_f[0]["action"]["checksum_now"] == now,
      [f["code"] for f in row["findings"]])
chk = BO.check_here(ctx)
ba = {b["name"]: b for b in chk.get("before_after") or []}
check("«Check against the graph»: modified after its stamp", ba.get("Column_entrance1", {}).get("state") == "modified",
      ba.get("Column_entrance1", {}).get("say_it"))
brow = next((r for r in BO.ba_rows(chk["before_after"]) if r["name"] == "Column_entrance1"), {})
check("… the row offers «Register as a new version», not ticked",
      brow.get("action") == "register_new_version" and not brow.get("tick"), brow.get("label"))
r = bpy.ops.em.deck_register_new_version("EXEC_DEFAULT", resource_id=lod0["id"], checksum_now=now)
cur = next(e for e in versions_of(graph, asset) if e.get("level") == "lod0")
check("registered as a new version: a revision at lod0 with today's sha256",
      "FINISHED" in r and cur["id"] != lod0["id"] and cur["checksum"] == now, cur["id"])
chk = BO.check_here(ctx)
ba = {b["name"]: b for b in chk.get("before_after") or []}
up = next((r for r in BO.ba_rows(chk["before_after"]) if r["name"] == "Column_entrance1"), {})
check("then the object shows an older revision: ↓ Update, ticked",
      ba.get("Column_entrance1", {}).get("state") == "revised" and up.get("tick"), up.get("label"))

# ── 3 · «Declare the master…» of the tileset ────────────────────────────────
t_id = grp["loaded"]["id"]
before = G.tileset_master(graph, t_id)
r = bpy.ops.em.deck_declare_tileset_master("EXEC_DEFAULT", tileset_id=t_id, container_id=grp["id"], mode="MEMBERS")
after = G.tileset_master(graph, t_id)
print("[SMOKE] TILESET MASTER:", before["say_it"], "→", after["say_it"], len(after["sources"]))
check("the master declared: the container's meshes", "FINISHED" in r and not before["declared"]
      and after["declared"] and len(after["sources"]) == 10, len(after["sources"]))
deck = HD.make_consolidation(ctx, "heriverse")
grp = next((r for r in deck["rows"] if r.get("kind") == "container" and r.get("loaded_why") == "tileset"), {})
check("the container no longer asks for it", not any(f["code"] == "tileset_master" for f in grp.get("findings") or []))
check("the em.json not written", open(emjson, "rb").read() == em_bytes)

print("[SMOKE] TIMES:", T)
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
if FAILURES:
    sys.exit(1)
