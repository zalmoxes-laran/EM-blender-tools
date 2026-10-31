"""Headless smoke · MICRO-BLEND-OFFICINA-3 (E.D. 31 Oct 2026) on a COPY of
Templu Mare, Blender 5.2, EM Tools as the working copy, s3dgraphy ≥ 1.6.0.dev80
(the working tree, PYTHONPATH)::

    BO_PROJECT=/tmp/officina3/A1 PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    BLENDER_USER_RESOURCES=<profile with EM Tools> \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        --python-exit-code 1 /tmp/officina3/A1/SB/GreatTemple_2026_v2.blend \\
        --python tests/blender_smoke_blend_officina_3.py

1. «Consolidate for…» from the Deck's functions (no interface) on TempluMare_v6;
2. «Compose a .blend from the graph» with NO .blend to start from (the
   study, modelling, from the disk) in a separate Blender; reopened and counted;
   the tileset's light set; the same from «the room» with a fake fetch;
3. the graph's tags; «Update» one object after a newer version is registered
   in the graph (a real glb copied): mesh and tags changed, name, place and
   collections kept; the before/after of «Check against the graph»;
4. the RB tileset's document (D.01) through graph_compose;
5. the detail box (the button; the modal's pure functions) and «More detail
   here» on it.
The em.json on disk is never written."""
import hashlib
import json
import os
import shutil
import sys
import time

import bpy

PROJECT = os.environ.get("BO_PROJECT", "/tmp/officina3/A1")
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

# ── 1 · «Consolidate for…» from the Deck (no interface) ─────────────────────
t0 = time.time()
deck = HD.make_consolidation(ctx, "heriverse")
T["deck"] = round(time.time() - t0, 2)
check("the Deck asks s3Dgraphy's consolidate", deck.get("available") and deck.get("rows") is not None,
      deck.get("note", ""))
print("[SMOKE] DECK:", deck.get("say_it"), json.dumps(deck.get("counts")), f"{T['deck']} s")
for line in PH.totals_lines(deck):
    print("[SMOKE] DECK TOTAL:", line)
whole = PH.consolidation(graph, C.published_models(graph))
print("[SMOKE] ALL PUBLISHED:", whole["say_it"], json.dumps(whole["counts"]))
print("[SMOKE] CONTAINERS:", [(r["name"], r["status"], r.get("loaded_is"), [f["code"] for f in r["findings"]])
                              for r in whole["rows"] if r["kind"] == "container"])
check("every RM of TempluMare_v6: 97, 1 with the base, 96 without", whole["counts"]["rms"] == 97
      and whole["counts"]["with_base"] == 1 and whole["counts"]["without_base"] == 96, whole["counts"])
no_base = next((r for r in deck["rows"] if r["kind"] == "rm" and not r["base"]), None)
if no_base is not None:
    acts = PH.row_actions(no_base)
    prep = next((a for a in acts if a["kind"] == "prepare"), {})
    check("a row without the base → «Prepare» with mobile_ar on its object",
          prep.get("uses") == ("mobile_ar",) and bool(prep.get("object")), prep)
HD.LAST.update(consolidated=deck, plan=HD.make_plan(ctx), folder="/tmp/x")
lines = drawn(HD.EM_OT_deck_heriverse, road="NODE", platform="heriverse")
print("[SMOKE] DECK DRAWN:", len(lines), "lines;", lines[:3], "…", [x for x in lines if x.startswith("[")][:3])
check("the Deck's popup draws the consolidation", any("mobile webXR" in x for x in lines)
      and any(x.startswith("[em.deck_heriverse_prepare]") for x in lines)
      and any("Prepare the missing bases" in x for x in lines))
check("the Deck's operators are registered", hasattr(bpy.ops.em, "deck_heriverse")
      and hasattr(bpy.ops.em, "deck_heriverse_make_missing"))

# ── 2 · «Compose a .blend from the graph», from the disk ────────────────────
t0 = time.time()
plan = BC.graph_plan(ctx, "modelling", "link")
T["plan"] = round(time.time() - t0, 2)
check("the plan: modelling, from the disk", plan["ok"] and len(plan["items"]) >= 97 and not plan["fetch"],
      plan["say_it"])
import types  # noqa: E402
_cls = next(c for c in BC._CLASSES if c.__name__ == "EM_OT_compose_from_graph")
_wm = bpy.context.window_manager.em_compose_scope
_wm.clear()
for _n in graph.nodes:
    if str(getattr(_n, "node_type", "")) in G._hats()["container"]:
        _r = _wm.add()
        _r.kind, _r.node_id, _r.label = "container", _n.node_id, _n.name
lines = drawn(_cls, profile="modelling", how="link", source="disk", only_selected=False)
print("[SMOKE] COMPOSE DIALOG:", [x for x in lines if "oggett" in x or "tileset" in x])
check("the compose dialog draws the plan", any("98 oggetti per modellazione" in x for x in lines)
      and any("light set" in x for x in lines), lines[-4:])
refused = BC.graph_plan(ctx, "webxr", "link")
check("a publication profile goes to «Consolidate for…»", not refused["ok"] and refused["go"] == "consolidate",
      refused["say_it"])
tiles_items = [i for i in plan["items"] if i["kind"] == "tileset"]
check("the container's tileset is one item, with its document (D.01)",
      len(tiles_items) == 1 and graph.find_node_by_id(tiles_items[0]["detail"]["document"]).name == "D.01",
      [(i["name"], i.get("detail")) for i in tiles_items])
out = BC.graph_out(emjson, "modelling")
t0 = time.time()
got = BC.run_detached(plan, out, mode="graph", timeout=900)
T["compose"] = round(time.time() - t0, 2)
print("[SMOKE] COMPOSED:", {k: got[k] for k in ("objects", "tagged", "tiles", "seconds")},
      "missing:", got["missing"][:4], f"wall {T['compose']} s")
check("composed in a separate Blender", got["ok"] and os.path.isfile(got["path"]) and got["objects"] >= 97,
      got["path"])
check("every model tagged", got["tagged"] == got["objects"], (got["tagged"], got["objects"]))
check("the tileset's light set", got["tiles"] >= 1, got["tiles"])
check("the em.json not written (compose)", open(emjson, "rb").read() == em_bytes)

# reopened and counted (the add-on stays; the graph is loaded again)
bpy.ops.wm.open_mainfile(filepath=got["path"])
ctx = bpy.context
objs = [o for o in bpy.data.objects if o.get("em_rm_node_id")]
detail = [o for o in bpy.data.objects if o.get(BD.P_TILE)]
eps_ok = [o for o in objs if [e.epoch for e in o.EM_ep_belong_ob]]
print("[SMOKE] REOPENED:", len(bpy.data.objects), "objects,", len(objs), "tagged,", len(detail), "tiles,",
      len(eps_ok), "with epochs; collections:", sorted(c.name for c in bpy.data.collections))
check("reopened: the tagged objects are there", len(objs) == got["objects"])
need = set(G.TAG_KEYS) - {"em_version_id"}
check("the tags present (EM_ep_belong_ob through the add-on's RNA)",
      all(all(k in o.keys() for k in need - {"EM_ep_belong_ob"}) for o in objs) and len(eps_ok) == len(objs),
      [o.name for o in objs if not all(k in o.keys() for k in need - {"EM_ep_belong_ob"})][:3])
st = BD.read_state(ctx.scene.get(BD.STATE_PROP))
check("the light set is the detail's state, its recipe under D.01", st["kind"] == "tileset" and st["cut"]
      and st["document"] == tiles_items[0]["detail"]["document"], (st["kind"], st["cut"], st["document"]))

graph = load_graph()
check("graph loaded in the composed file", graph is not None)

# ── 3 · «Update» an object after a newer version is registered ──────────────
col = bpy.data.objects.get("Column_entrance1")
check("Column_entrance1 composed", col is not None)
col.location = (1.0, 2.0, 3.0)
ctx.view_layer.update()
mw_before = [list(r) for r in col.matrix_world]
cols_before = sorted(c.name for c in col.users_collection)
verts_before = len(col.data.vertices)
tags_before = BO.object_tags(col)
res = BO.check_here(ctx)
ba = {b["name"]: b for b in res.get("before_after") or []}
check("before/after: Column aligned before", ba.get("Column_entrance1", {}).get("state") == "aligned",
      ba.get("Column_entrance1", {}).get("say_it"))
print("[SMOKE] BEFORE/AFTER:", len(ba), "objects,", sum(1 for b in ba.values() if b["state"] == "aligned"),
      "aligned; Column here:", ba.get("Column_entrance1", {}).get("here", {}).get("made_say"))
# measured: three objects composed at lod1 are «newer» because the LOD chain's
# lod4 (lowres for Walls) was born after it — another rung, offered but not ticked
_rung = [r for r in BO.ba_rows(list(ba.values())) if r["state"] == "newer"]
check("a newer RUNG of the LOD chain is offered, not ticked", all(not r["tick"] for r in _rung
      if BO.other_rung(ba[r["name"]]["here"]["level"], ba[r["name"]]["latest"]["level"])),
      [(r["name"], r["tick"]) for r in _rung])
print("[SMOKE] BEFORE/AFTER STATES:", sorted((b["name"], b["state"], b.get("say_it")) for b in ba.values()
                                              if b["state"] != "aligned"))
src_glb = os.path.join(PROJECT, "SB", "versions", "Column_entrance2@lod1-realtime-web.glb")
if not os.path.isfile(src_glb):
    src_glb = next(os.path.join(PROJECT, "SB", "versions", f) for f in sorted(os.listdir(
        os.path.join(PROJECT, "SB", "versions"))) if f.endswith(".glb") and "Column_entrance1" not in f)
day = time.strftime("%Y-%m-%d")
dest = os.path.join(PROJECT, "SB", "versions", f"Column_entrance1@manual-{day}.glb")
shutil.copyfile(src_glb, dest)
sha = "sha256:" + hashlib.sha256(open(dest, "rb").read()).hexdigest()
asset = asset_of(graph, tags_before["em_version_id"])
new = api.add_version(graph, asset, use=["realtime"], level=f"manual-{day}", files=[{
    "path": os.path.basename(dest), "url": os.path.relpath(dest, em_folder).replace(os.sep, "/"),
    "checksum": sha}])
status = G.update_status(graph, tags_before)
check("the graph has a newer version", status["state"] == "newer"
      and status["action"].get("resource_id") == new["version_id"], status["say_it"])
res = BO.check_here(ctx)
lines = drawn(next(c for c in BO._CLASSES if c.__name__ == "EM_OT_blend_check_graph"), source="disk", index=0)
check("the check dialog says the versions", any(x.startswith("Versions:") and "with a newer" in x for x in lines),
      [x for x in lines if x.startswith("Versions")])
rows = {r["name"]: r for r in BO.ba_rows(res.get("before_after") or [])}
r = rows.get("Column_entrance1") or {}
print("[SMOKE] CHECK ROW:", r.get("label"))
check("«Check against the graph»: ↓ Update ticked, before → after with who and when",
      r.get("sign") == "↓" and r.get("tick") and r.get("action") == "update_version" and "→" in r.get("label", ""),
      r)
t0 = time.time()
out_apply = BO.apply_rows(ctx, graph, [r], emjson)
T["update"] = round(time.time() - t0, 2)
check("«Apply» updates", out_apply["done"] and not out_apply["failed"], out_apply)
col = bpy.data.objects.get("Column_entrance1")
tags_after = BO.object_tags(col)
check("the mesh changed", len(col.data.vertices) != verts_before, (verts_before, len(col.data.vertices)))
check("the tags follow the new version", tags_after.get("em_version_id") == new["version_id"]
      and tags_after.get("em_asset_sha256") == sha and tags_after.get("em_level") == f"manual-{day}",
      {k: tags_after.get(k) for k in ("em_version_id", "em_level")})
ctx.view_layer.update()
check("name, place and collections kept", col.name == "Column_entrance1"
      and [list(x) for x in col.matrix_world] == mw_before
      and sorted(c.name for c in col.users_collection) == cols_before,
      (col.name, tuple(col.location), sorted(c.name for c in col.users_collection), cols_before))
check("epochs kept", tags_after.get("EM_ep_belong_ob") == tags_before.get("EM_ep_belong_ob"),
      tags_after.get("EM_ep_belong_ob"))
st2 = G.update_status(graph, tags_after)
check("now aligned", st2["state"] == "aligned", st2["say_it"])

# ── 4 · the RB tileset's document through graph_compose ─────────────────────
tz = os.path.join(PROJECT, "RB", "cesium", "TempluMare.3tz")
folder = os.path.join(PROJECT, "RB", "cesium", "TempluMare")
_r, d_folder = BD.source_document(ctx, folder)
_r, d_tz = BD.source_document(ctx, tz)
print("[SMOKE] DOC before registering: folder →", getattr(d_folder, "name", None), "· .3tz →",
      getattr(d_tz, "name", None))
check("the tileset (folder) → D.01", getattr(d_folder, "name", None) == "D.01")
ts_id = tiles_items[0]["entry"]["id"]
reg = G.register_tileset_whole(graph, ts_id, tiles_items[0]["container"])
_r, d_tz = BD.source_document(ctx, tz)
check("registered under D.01: the .3tz → D.01 too", getattr(d_tz, "name", None) == "D.01", reg["said"])

# ── 5 · the detail box and «More detail here» on it ─────────────────────────
for o in ctx.view_layer.objects:
    o.select_set(False)
r0 = bpy.ops.em.detail_add_box()
box = BD.last_box(ctx)
check("«Add a detail box»: an Empty cube, selected", "FINISHED" in r0 and box is not None
      and box.empty_display_type == "CUBE" and box.select_get())
area, frm = BD.detail_area(ctx)
check("the selected box is the area", frm == "box" and area is not None, (frm, area))
# over the column of round 2 (4 m, Templu Mare's frame) — the box moved there
zs = BD.loaded_z_span(ctx)
check("the light set gives the box its height", zs is not None, zs)
pts = [BD.ray_plane((x, y, 600.0), (0.0, 0.0, -1.0), (0.0, 0.0, (zs[0] + zs[1]) / 2))
       for x, y in ((-17.0, -9.0), (-13.0, -9.0), (-13.0, -5.0), (-17.0, -5.0))]
b = BD.rect_box(pts, zs[0], zs[1])
box.location = b["center"]
box.scale = b["half"]
ctx.view_layer.update()
box.select_set(False)
area, frm = BD.detail_area(ctx)
check("not selected: the last box", frm == "last_box" and abs((area[3] - area[0]) - 4.0) < 1e-6, (frm, area))
before = len([o for o in bpy.data.objects if o.get(BD.P_TILE)])
p = BD.plan_more(ctx, area, "densest")
print("[SMOKE] MORE DETAIL on the box:", len(p["load"]), "to load,", len(p["drop"]), "to drop —",
      p["estimate"].get("say"))
got_more = BD.do_more(ctx, area, "densest")
after = len([o for o in bpy.data.objects if o.get(BD.P_TILE)])
check("«More detail here» on the box", got_more["loaded"] > 1 and after > before, (before, after))
check("the recipe goes to D.01 (in the graph, and to the room when joined)",
      "recipe kept in the graph" in got_more["said"], got_more["said"])

# ── the same, from «the room» (a fake fetch: the room's bytes by sha256) ────
ids = ["Column_entrance1_model", "Architrave_1_BAKE_SM_Architrave_1_BAKE_model"]
FS.ULTIMI.update({"graph_id": str(graph.graph_id), "results": [], "at": "smoke"})
room_plan = G.compose_from_graph(graph, "modelling", em_folder=em_folder, project_folder=PROJECT, models=ids,
                                 resolved=[{"id": i["entry"]["id"], "state": "on_node"}
                                           for i in plan["items"] if i["model_id"] in ids],
                                 in_room=True)
room_plan = BC.decorate_plan(graph, room_plan, em_folder=em_folder, project_folder=PROJECT, em_json=emjson)
check("from the room: every file fetched by sha256 into em_cache/files",
      len(room_plan["items"]) == 2 and all(i["source"]["how"] == "fetch" for i in room_plan["items"])
      and all("/em_cache/files/" in f["to"] for f in room_plan["fetch"]), room_plan["say_it"])
disk = {}
for i in plan["items"]:
    if i["model_id"] in ids:
        disk[BC.sha_hex(i["entry"]["checksum"])] = i["source"]["file"]
asked = []


def fake_get(ref):
    asked.append(ref)
    return open(disk[ref.split(":")[1]], "rb").read(), "model/gltf-binary"


fetched = BC.fetch_files(room_plan["fetch"], fake_get)
check("fetched and checked", fetched["fetched"] == 2 and not fetched["failed"], fetched)
got_room = BC.run_detached(room_plan, BC.graph_out(emjson, "modelling-room"), mode="graph")
check("composed from the room's bytes", got_room["objects"] == 2 and got_room["tagged"] == 2,
      {k: got_room[k] for k in ("objects", "tagged", "missing")})

check("the em.json was not written", open(emjson, "rb").read() == em_bytes)
print("[SMOKE] TIMES:", json.dumps(T))
print("[SMOKE] " + ("ALL PASS" if not FAILURES else f"FAILED: {FAILURES}"))
if FAILURES:
    sys.exit(1)
