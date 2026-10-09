"""Headless smoke · the recipe of a version for Heriverse/ATON (E.D., 6 Oct 2026),
on a COPY of Templu Mare v2 (never saved).

    PYTHONPATH=~/Documents/GitHub/s3Dgraphy/src \\
    "/Applications/Blender 520.app/Contents/MacOS/Blender" -b --python-use-system-env \\
        /tmp/hrec/v2/SB/GreatTemple_2026_v2.blend \\
        --python tests/blender_smoke_heriverse_recipe.py -- /tmp/hrec/run

On three objects — an RM with its baked texture, an RMDoc made here from a
document of the DosCo and moved off the origin, the RMSF of the anastylosis
list — «Prepare for a use…» for Heriverse/ATON with the recipe of each
category: a glTF with its textures, born with its dtcstamp. Then «Write the
package on disk», and the OLD exporter (`_dead_code`, loaded under the live
package so its relative imports resolve) on the same objects, for the
comparison. Everything measured is dumped in `<work>/measures.json`.
"""
import hashlib
import importlib
import importlib.util
import json
import math
import os
import shutil
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WORK = ARGS[0] if ARGS else "/tmp/hrec/run"
FAILURES = []
M = {}


def check(label, condition, detail=""):
    print(f"[SMOKE] {'PASS' if condition else 'FAIL'}: {label} {detail}")
    if not condition:
        FAILURES.append(label)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


shutil.rmtree(WORK, ignore_errors=True)
os.makedirs(WORK)
names = [n for n in sys.modules if n.endswith(".graph_origins") and n.startswith("bl_ext.")]
PKG = names[0].rsplit(".graph_origins", 1)[0]
av = importlib.import_module(PKG + ".sync_manager.asset_versions")
heri = importlib.import_module(PKG + ".publication_deck_ui.heriverse")
PH = importlib.import_module(PKG + ".publication_heriverse")
VS = importlib.import_module(PKG + ".version_stamp")
VR = importlib.import_module(PKG + ".version_recipe")
import s3dgraphy  # noqa: E402
print("[SMOKE] s3dgraphy", s3dgraphy.__file__)

scene = bpy.context.scene
blend_before = sha(bpy.data.filepath)
r = getattr(bpy.ops, "import").em_emjson(file_index=0)
check("the em.json of the copy loads", r == {"FINISHED"}, str(r))
from s3dgraphy import api, get_graph  # noqa: E402
graph = get_graph(scene.em_tools.graphml_files[0].name)
EM_DIR = os.path.normpath(os.path.join(os.path.dirname(bpy.data.filepath), "..", "EM"))

#: an RM with its texture AND placed off the origin (the placement must travel
#: in the glTF), else the first textured one
def _textured(o):
    return any(getattr(n, "image", None) for s in o.material_slots
               if s.material and s.material.node_tree for n in s.material.node_tree.nodes)


_rms = [bpy.data.objects.get(r.name) for r in scene.rm_list]
_rms = [o for o in _rms if o is not None and o.type == "MESH" and _textured(o)]
_placed = [o for o in _rms if o.matrix_world.translation.length > 0.5]
RM = (_placed or _rms)[0].name
print("[SMOKE] the RM:", RM, tuple(round(v, 3) for v in bpy.data.objects[RM].matrix_world.translation))
SF = "GT16.USV136"


def select(obj):
    #: in memory only: the object's collection included in the view layer (an
    #: excluded collection, as some of the scene's are, cannot be selected)
    if obj.name not in bpy.context.view_layer.objects:
        utils = importlib.import_module(PKG + ".export_operators.heriverse.utils")
        for col in obj.users_collection:
            lc = utils.find_layer_collection(bpy.context.view_layer.layer_collection, col.name)
            if lc is not None:
                lc.exclude = False
        bpy.context.view_layer.update()
    obj.hide_set(False)
    obj.hide_viewport = False
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def gltf_of(entry):
    with open(entry, encoding="utf-8") as fh:
        return json.load(fh)


# ── (1) the RM: a glTF with its texture, its placement in the glTF ──────────
obj = bpy.data.objects[RM]
select(obj)
if obj.matrix_world.translation.length < 0.5:
    #: in memory: moved off the origin, so the placement has something to carry
    #: (the old exporter below sees the same placement)
    obj.location = (3.0, 2.0, 1.0)
    bpy.context.view_layer.update()
before = [e for e in api.versions_of(graph, av.master_of(graph, obj, scene))
          if not e["master"]]
M["rm_before"] = [{k: e[k] for k in ("id", "level", "lod_level", "use", "url", "checksum")}
                  for e in before]
r = bpy.ops.em.asset_prepare_for_use("EXEC_DEFAULT", use={"heriverse", "aton"})
check("RM: Prepare for a use… (heriverse, aton)", r == {"FINISHED"}, str(r))
P = dict(av.PREPARED)
rm_v = P.get("version_id")
files = P.get("files") or []
check("RM: a glTF with its .bin and its texture, one version of several files",
      len(files) >= 3 and files[0]["path"].endswith(".gltf")
      and any(f["path"].endswith(".bin") for f in files)
      and any(f["path"].lower().endswith((".jpg", ".png")) for f in files),
      [f["path"] for f in files])
node = graph.find_node_by_id(rm_v)
check("RM: the version's url is its .gltf, its checksum the members digest",
      node.data.get("url", "").endswith(".gltf") and node.data.get("digest_covers") == "members",
      node.data.get("url"))
check("RM: it REVISES the glb version made for Heriverse (same level, same use)",
      bool(P.get("revises")) and P.get("revises") in [e["id"] for e in before], P.get("revises"))
step = api.derivation_chain(graph, rm_v)["made_by"]
params = (graph.find_node_by_id(step[0]["id"]).data.get("parameters") or {}) if step else {}
M["rm_step"] = params
check("RM: the recipe is in the DTC step", params.get("format") == "gltf_separate"
      and params.get("transform") == "world" and params.get("category") == "rm", params)
st = VS.check(graph, rm_v)
M["rm_stamp"] = st
check("RM: born with its stamp, the bytes are the stamped ones, from its mother",
      st["state"] == "ok" and st["mother"], st)
stamp = json.load(open(st["stamp_path"]))
check("RM: the stamp's recipe and its revision", stamp["how"]["parameters"].get("format") ==
      "gltf_separate" and (stamp["self"].get("was_revision_of") or {}).get("resource_id")
      == P.get("revises"), stamp["self"].get("was_revision_of"))
g = gltf_of(files[0]["url"])
gnode = next(n for n in g["nodes"] if "mesh" in n)
mw = obj.matrix_world
t = gnode.get("translation", [0, 0, 0])
# glTF is Y-up: Blender (x, y, z) → glTF (x, z, -y)
want = [mw.translation.x, mw.translation.z, -mw.translation.y]
M["rm_gltf_node"] = gnode
check("RM: the object's placement is in the glTF node (transform: world)",
      all(abs(a - b) < 1e-3 for a, b in zip(t, want)), f"{t} vs {want}")
choice = api.version_for(graph, obj.get("em_rm_node_id") or av.master_of(graph, obj, scene),
                         list(PH.USES))
check("RM: the rule picks the glTF", choice and choice["entry"]["id"] == rm_v,
      (choice or {}).get("entry", {}).get("url"))
card = importlib.import_module(PKG + ".provenance_card")
lines = card.lines(card.card(graph, rm_v))
M["rm_card"] = lines
check("RM: «Where it comes from» says the stamp", any(x.startswith("stamp ✓") for x in lines),
      lines)

# ── (2) an RMDoc: a document placed in space, moved off the origin ─────────
item = scene.em_tools.graphml_files[0]
item.dosco_dir = os.path.join(EM_DIR, "DosCo")
docs = []
for i, d in enumerate(scene.doc_list):
    if str(getattr(d, "url", "")).lower().endswith((".jpg", ".jpeg", ".png")):
        docs.append((i, d.name, d.url, getattr(d, "node_id", "")))
#: a large JPEG first: «Compress Textures» caps it at 2048 px and re-encodes it
#: (D.06 TMplan1A.JPG is 5391 × 6757 px)
docs.sort(key=lambda d: (not d[2].lower().endswith((".jpg", ".jpeg")), not d[1] == "D.06"))
print("[SMOKE] documents with an image:", docs[:8])
quad = None
for i, name, url, nid in docs:
    scene.doc_list_index = i
    try:
        r = bpy.ops.em.rmdoc_create_from_document(doc_node_id=nid, width=2.0,
                                                  orientation="ZENITH")
    except RuntimeError as exc:
        print("[SMOKE] rmdoc", name, exc)
        continue
    if r == {"FINISHED"}:
        quad = next((o for o in bpy.data.objects if o.get("em_doc_node_id") == nid), None)
        if quad is not None:
            break
check("RMDoc: a quad made from a document of the DosCo", quad is not None,
      quad.name if quad else "")
quad.location = (12.5, -4.0, 3.25)
quad.rotation_euler = (math.radians(80), 0.0, math.radians(30))
quad.scale = (1.5, 1.5, 1.5)
bpy.context.view_layer.update()
img = next((n.image for s in quad.material_slots if s.material and s.material.node_tree
            for n in s.material.node_tree.nodes if getattr(n, "image", None)), None)
M["rmdoc_image"] = {"name": img.name, "size": list(img.size), "file": img.filepath} if img else None
select(quad)
r = bpy.ops.em.asset_prepare_for_use("EXEC_DEFAULT", use={"heriverse", "aton"})
check("RMDoc: Prepare for a use… (heriverse, aton)", r == {"FINISHED"}, str(r))
P2 = dict(av.PREPARED)
doc_v = P2.get("version_id")
dfiles = P2.get("files") or []
rmdoc_id = f"{quad['em_doc_node_id']}_rm_doc"
check("RMDoc: its version hangs off the RMDoc node",
      any(e.edge_source == rmdoc_id and e.edge_type == "has_linked_resource"
          for e in graph.edges), rmdoc_id)
dparams = P2["step"]["parameters"]
M["rmdoc_step"] = dparams
SV = VR.scene_values(scene)
M["scene_values"] = SV
check("RMDoc: the recipe of the category (node, the scene's max size and quality)",
      dparams.get("category") == "rmdoc" and dparams.get("transform") == "node"
      and dparams.get("max_texture_px") == SV.get("max_texture_px", 2048)
      and dparams.get("jpeg_quality") == SV.get("jpeg_quality", 60), (dparams, SV))
rnode = graph.find_node_by_id(rmdoc_id)
tr = (rnode.data or {}).get("transform") or {}
check("RMDoc: the placement preserved on the RMDoc node",
      [round(float(v), 4) for v in tr.get("position", [])] == [12.5, -4.0, 3.25]
      and [round(float(v), 4) for v in tr.get("scale", [])] == [1.5, 1.5, 1.5], tr)
dg = gltf_of(dfiles[0]["url"])
dn = next(n for n in dg["nodes"] if "mesh" in n)
check("RMDoc: the glTF at the origin", not any(dn.get(k) for k in ("translation", "rotation"))
      and dn.get("scale") in (None, [1, 1, 1], [1.0, 1.0, 1.0]), dn)
texs = [f for f in dfiles if f["path"].lower().endswith((".jpg", ".jpeg", ".png"))]
sizes = []
for f in texs:
    im = bpy.data.images.load(f["url"], check_existing=False)
    sizes.append((f["path"], list(im.size), f["size_bytes"]))
    bpy.data.images.remove(im)
M["rmdoc_textures"] = sizes
CAP = dparams.get("max_texture_px")
check(f"RMDoc: textures capped at {CAP} px", sizes and all(max(s[1]) <= CAP for s in sizes), sizes)
check("RMDoc: …and this one was larger: reduced", (M["rmdoc_image"] or {}).get("size")
      and max(M["rmdoc_image"]["size"]) > CAP and dparams.get("textures_resized", 0) >= 1,
      M["rmdoc_image"])
check("RMDoc: the JPEG re-encoded (Compress Textures)",
      dparams.get("reencoded", 0) >= 1 or not any(p.lower().endswith((".jpg", ".jpeg"))
                                                  for p, _s, _b in sizes), dparams)
st2 = VS.check(graph, doc_v)
M["rmdoc_stamp"] = st2
check("RMDoc: stamped, bytes = stamp, from its mother", st2["state"] == "ok" and st2["mother"], st2)

# ── (3) the RMSF ────────────────────────────────────────────────────────────
sf = bpy.data.objects[SF]
select(sf)
r = bpy.ops.em.asset_prepare_for_use("EXEC_DEFAULT", use={"heriverse", "aton"})
check("RMSF: Prepare for a use… (heriverse, aton)", r == {"FINISHED"}, str(r))
P3 = dict(av.PREPARED)
sf_v = P3.get("version_id")
sparams = P3["step"]["parameters"]
M["rmsf_step"] = sparams
check("RMSF: the recipe of the category (world)", sparams.get("category") == "rmsf"
      and sparams.get("transform") == "world", sparams)
rmsf_id = sf.get("em_rm_node_id")
check("RMSF: its version hangs off the RMSF node",
      graph.find_node_by_id(rmsf_id) is not None
      and graph.find_node_by_id(rmsf_id).node_type == "representation_model_sf", rmsf_id)
st3 = VS.check(graph, sf_v)
M["rmsf_stamp"] = st3
check("RMSF: stamped, bytes = stamp", st3["state"] == "ok" and st3["mother"], st3)
M["rmsf_files"] = [f["path"] for f in P3.get("files") or []]

# ── (4) the package on disk ─────────────────────────────────────────────────
for r_ in scene.rm_list:
    r_.is_publishable = r_.name == RM
for a in scene.em_tools.anastylosis.list:
    a.is_publishable = a.name == SF
PKG_DIR = os.path.join(WORK, "TempluMare_v2_heriverse")
r = bpy.ops.em.deck_heriverse_write_disk("EXEC_DEFAULT", folder=PKG_DIR, from_node=False)
check("the package is written", r == {"FINISHED"}, str(r))
rep = heri.LAST.get("package") or {}
M["package"] = {k: rep.get(k) for k in ("written", "failed", "extras", "stamp", "zip")}
print("[SMOKE] package:", json.dumps(M["package"], indent=1, default=str)[:3000])
cats = {w["category"]: w for w in rep.get("written") or []}
check("the package has the RM, the RMDoc and the RMSF", set(cats) >= {"rm", "rmdoc", "rmsf"},
      list(cats))
doc = json.load(open(os.path.join(PKG_DIR, "em.json")))
nodes = {n["id"]: n for sec in doc["graphs"].values() for n in sec["nodes"]}
for cat, w in cats.items():
    base = os.path.dirname(os.path.join(PKG_DIR, *w["rel"].split("/")))
    on_disk = sorted(os.path.relpath(os.path.join(dp, f), base)
                     for dp, _d, fs in os.walk(base) for f in fs)
    M[f"package_{cat}"] = {"rel": w["rel"], "files": on_disk}
    check(f"{cat}: its folder in the package, the .gltf and what it names",
          w["rel"].endswith(".gltf") and len(on_disk) == w["files"], on_disk)
check("the version's url in the package em.json is relative",
      nodes[rm_v]["data"]["url"] == cats["rm"]["rel"], nodes[rm_v]["data"]["url"])
check("the RMDoc node's url is its version (Heriverse opens it by its url)",
      nodes[rmdoc_id]["data"]["url"] == cats["rmdoc"]["rel"], nodes[rmdoc_id]["data"].get("url"))
geo = [n for n in nodes.values() if n.get("node_type") == "geo_position"]
M["package_geo"] = [n.get("data") for n in geo]
gnode = next((n for n in graph.nodes if getattr(n, "node_type", "") == "geo_position"), None)
want_geo = {k: (gnode.data or {}).get(k) for k in ("epsg", "shift_x", "shift_y", "shift_z")} \
    if gnode is not None else {}
M["graph_geo"] = want_geo
M["scene_georef"] = {k: getattr(scene.em_georef, k, None)
                     for k in ("epsg", "shift_x", "shift_y", "shift_z", "rotation")}
check("the study's georeferencing travels as the em.json holds it (not the scene's)",
      geo and {k: (geo[0].get("data") or {}).get(k) for k in want_geo} == want_geo,
      (M["package_geo"], want_geo, M["scene_georef"]))
rm_nodes = [n for n in nodes.values() if n.get("node_type") == "representation_model"]
M["package_rm_nodes"] = len(rm_nodes)
check("only the published RM is in the package em.json (the others left out, as before)",
      [n["id"] for n in rm_nodes] == [obj.get("em_rm_node_id") or rm_nodes[0]["id"]]
      and len(rm_nodes) == 1, len(rm_nodes))
check("the RMDoc's placement travels in the em.json",
      nodes[rmdoc_id]["data"].get("transform", {}).get("position") == tr.get("position"))
ex = rep.get("extras") or {}
check("the proxies are in proxies/, checked", len(ex.get("proxies") or []) >= 60,
      f"{len(ex.get('proxies') or [])} written, {len(ex.get('proxies_failed') or [])} failed")
check("the DosCo is in dosco/", os.path.isdir(os.path.join(PKG_DIR, "dosco")), ex.get("dosco"))
if scene.heriverse_export_panorama:
    check("the default panorama is named in defaults.panorama",
          all((sec.get("defaults") or {}).get("panorama") == "panorama/defsky.jpg"
              for sec in doc["graphs"].values()), ex.get("panorama"))
else:
    check("no panorama: this scene turned it off, as the old exporter read it",
          not os.path.isdir(os.path.join(PKG_DIR, "panorama")), ex.get("panorama"))
check("the package is stamped", (rep.get("stamp") or {}).get("state") in ("stamped", "revised"),
      rep.get("stamp"))
check("the zip is there", os.path.isfile(rep.get("zip") or ""), rep.get("zip"))
# the rule read back from the package picks the same versions
from s3dgraphy.importer.emjson_importer import parse_emjson  # noqa: E402
pg, _ = parse_emjson(json.loads(json.dumps(doc)))
for rid, cat in ((obj.get("em_rm_node_id"), "rm"), (rmdoc_id, "rmdoc"), (rmsf_id, "rmsf")):
    c = api.version_for(pg, rid, list(PH.USES)) if rid and pg.find_node_by_id(rid) else None
    check(f"{cat}: the rule reads the package and picks its glTF",
          c and c["entry"]["url"] == cats[cat]["rel"], (c or {}).get("entry", {}).get("url"))

# ── (5) the OLD exporter: in a clean session of another copy, on the same
#     objects in the same state (`old_export.py` of the report) — run after a
#     version, it meets the RMDoc's mesh already moved into its library
check("the .blend on disk is untouched", sha(bpy.data.filepath) == blend_before)
with open(os.path.join(WORK, "measures.json"), "w") as fh:
    json.dump(M, fh, indent=1, default=str)
print(f"[SMOKE] {'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
sys.exit(1 if FAILURES else 0)
