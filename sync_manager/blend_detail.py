"""MICRO-BLEND-OFFICINA-2 · detail on request (E.D.'s answers of 31 Oct 2026,
D1–D4): EM Tools' half.

In Blender one always starts from a LIGHT SET — the coarsest level of a
tileset (a folder, its ``tileset.json`` or a ``.3tz``) or the lightest LOD of
a master — and asks for more detail by portions: «More detail here» on the
box of the selected objects, down one level or to the densest; «Less detail»
frees it. The estimate (triangles, texture, Blender's memory) is shown in
the confirmation BEFORE anything is loaded: no threshold decides alone (D1).

What is loaded is CACHE (D2): ``<em.json's folder>/em_cache/local/detail/
<recipe key>/``, never stamped — the tiles written there as ``.gltf`` +
``.bin`` + their images as files beside them (D4). The objects carry
``em_detail_recipe`` / ``em_detail_tile`` / ``em_detail_document`` and live in
the collection «Detail (cache)»; «Export as master» and «Register as a
version» refuse them. The room shares the RECIPE (area, level or resolution,
the document): kept in the document node's ``data.detail_recipes`` and sent
to the room as an ``update_node`` when one is joined; «Regenerate» makes the
same files from it on another computer.

A master that is not tiled: its lightest LOD first (a stamped file, imported
from where it is); «More detail here» is a CROP of the master at 5 cm (1 cm
only on a small area — D3), made by 3D Survey Collection's headless
``crop_to_area`` into the cache.

The paradata of a proxy modelled on a detail cite the DOCUMENT
(``detail.paradata_source``), never the cache: :func:`document_for_cache_path`
redirects a cache file to its document, and EM Tools' document creation
refuses a cache path.

The plans are s3Dgraphy's (``resources.detail``, ≥ 1.6.0.dev79); the few pure
functions here are measured by ``tests/test_blend_detail.py``.
"""

# NOT `from __future__ import annotations`: operators are built in a function.
import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

NEEDS_DEV79 = ("«Detail on request» needs s3dgraphy ≥ 1.6.0.dev79 (the next bundle of EM Tools): "
               "this Blender's s3dgraphy has no resources.detail")

#: the collection the cache objects live in
COLLECTION = "Detail (cache)"
#: the scene's memory of what is loaded (JSON): source, kind, cut, recipes
STATE_PROP = "em_detail_state"
P_RECIPE, P_TILE, P_DOC, P_SOURCE = "em_detail_recipe", "em_detail_tile", "em_detail_document", "em_detail_source"


def dt():
    """s3Dgraphy's ``resources.detail``."""
    try:
        from s3dgraphy.resources import detail
        return detail
    except ImportError as exc:
        raise RuntimeError(NEEDS_DEV79) from exc


# ── pure ─────────────────────────────────────────────────────────────────────

def area_from_boxes(boxes: Iterable[Sequence[Sequence[float]]], pad: float = 0.0) -> Optional[List[float]]:
    """The area (min xyz, max xyz) around a set of world-space corners — the
    boxes of the selected objects — grown by ``pad`` metres."""
    pts = [p for b in boxes for p in b]
    if not pts:
        return None
    lo = [min(p[i] for p in pts) - pad for i in range(3)]
    hi = [max(p[i] for p in pts) + pad for i in range(3)]
    return lo + hi


def is_tileset_path(path: str) -> bool:
    p = str(path or "").lower()
    return p.endswith(".3tz") or p.endswith("tileset.json") or (
        os.path.isdir(path) and os.path.exists(os.path.join(path, "tileset.json")))


def empty_state() -> Dict[str, Any]:
    return {"kind": "", "source": "", "document": "", "resource": "", "cut": [], "recipes": [],
            "tiles": {}, "level": None}


def read_state(raw: Any) -> Dict[str, Any]:
    try:
        got = json.loads(raw) if isinstance(raw, str) and raw else {}
    except ValueError:
        got = {}
    st = empty_state()
    if isinstance(got, dict):
        st.update({k: got[k] for k in st if k in got})
    return st


def _node_data(node) -> Dict[str, Any]:
    d = getattr(node, "data", None)
    if not isinstance(d, dict):
        d = {}
        try:
            node.data = d
        except Exception:  # noqa: BLE001
            pass
    return d


def _url_of(node) -> str:
    return str(getattr(node, "url", "") or (_node_data(node).get("url") or ""))


def resource_for_path(graph, path: str, em_folder: str) -> Optional[Any]:
    """The graph's resource (or document) whose url is ``path`` (the tileset's
    folder, its tileset.json or its .3tz; a master's file)."""
    if graph is None or not path:
        return None
    want = {os.path.normpath(path)}
    if os.path.basename(path).lower() == "tileset.json":
        want.add(os.path.normpath(os.path.dirname(path)))
    elif os.path.isdir(path):
        want.add(os.path.normpath(os.path.join(path, "tileset.json")))
    for n in getattr(graph, "nodes", []) or []:
        if getattr(n, "node_type", None) not in ("resource", "document", "link"):
            continue
        url = _url_of(n)
        if not url or "://" in url:
            continue
        ab = os.path.normpath(url if os.path.isabs(url) else os.path.join(em_folder, url))
        if ab in want:
            return n
    return None


def document_of(graph, node) -> Optional[Any]:
    """The DOCUMENT a resource stands for: the node itself if it is one, else
    a document joined to it by any edge (``has_linked_resource`` and kin)."""
    if node is None:
        return None
    if getattr(node, "node_type", None) == "document":
        return node
    nid = node.node_id
    for e in getattr(graph, "edges", []) or []:
        other = e.edge_source if e.edge_target == nid else e.edge_target if e.edge_source == nid else None
        if other is None:
            continue
        n = graph.find_node_by_id(other)
        if getattr(n, "node_type", None) == "document":
            return n
    return None


def recipe_document(graph, key: str) -> Optional[Any]:
    """The document node whose ``data.detail_recipes`` holds ``key``."""
    for n in getattr(graph, "nodes", []) or []:
        if getattr(n, "node_type", None) != "document":
            continue
        for r in (_node_data(n).get("detail_recipes") or []):
            if isinstance(r, dict) and r.get("key") == key:
                return n
    return None


def cache_key_of_path(path: str) -> str:
    """``…/em_cache/local/detail/<key>/…`` → ``key`` (or "")."""
    parts = str(path or "").replace("\\", "/").split("/")
    for i in range(len(parts) - 3):
        if parts[i:i + 3] == ["em_cache", "local", "detail"]:
            return parts[i + 3]
    return ""


def is_cache_path(path: str) -> bool:
    p = "/" + str(path or "").replace("\\", "/").strip("/") + "/"
    return "/em_cache/local/" in p


def document_for_cache_path(graph, path: str) -> Optional[Any]:
    """A file of the detail cache → the DOCUMENT its recipe cites (the
    paradata cite the document, never the cache, E.D. 30 Oct)."""
    key = cache_key_of_path(path)
    return recipe_document(graph, key) if key else None


def source_texture_px(path: str) -> int:
    """The texture pixels a mesh file brings (an OBJ's .mtl maps, a glTF's
    images beside it), read from the images' first bytes: a crop keeps the
    master's materials, so its memory is mostly these (measured on Templu
    Mare's OB_INT_L_LOD0: 67 Mpx, ~260 MB of the crop's ~275 MB)."""
    try:
        from s3dgraphy.resources.use_profiles import image_size
    except ImportError:
        return 0
    folder = os.path.dirname(path)
    images: List[str] = []
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".obj":
            mtls = []
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh):
                    if line.startswith("mtllib "):
                        mtls.append(line[7:].strip())
                    if i > 2000:
                        break
            for m in mtls:
                with open(os.path.join(folder, m), "r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        if line.strip().lower().startswith(("map_kd ", "map_ka ")):
                            images.append(line.strip().split(None, 1)[1].split()[-1])
        elif ext == ".gltf":
            with open(path, "r", encoding="utf-8") as fh:
                images = [im.get("uri") for im in (json.load(fh).get("images") or []) if im.get("uri")]
    except OSError:
        return 0
    px = 0
    for im in dict.fromkeys(images):
        try:
            with open(os.path.join(folder, im), "rb") as fh:
                w, h, _f = image_size(fh.read(65536))
            px += w * h
        except OSError:
            continue
    return px


def estimate_lines(est: Dict[str, Any]) -> List[str]:
    """The confirmation's lines for an estimate (``detail.estimate``)."""
    out = [f"{est.get('pieces', 0)} pieces · {est.get('triangles', 0):,} triangles · "
           f"{(est.get('texture_px') or 0) / 1e6:.1f} Mpx of texture",
           f"≈ {est.get('ram_mb', 0):,.0f} MB in Blender · "
           f"{(est.get('file_bytes') or 0) / 1048576:,.1f} MB to write into the cache"]
    if est.get("unknown"):
        out.append(f"{est['unknown']} pieces not measured")
    return out


# ── reading a tileset (cached by path and mtime) ─────────────────────────────

_OPEN: Dict[str, Tuple[float, Any, Any]] = {}


def open_tileset(path: str):
    """``(tree, read_bytes)`` for a tileset, kept while its file is unchanged."""
    D = dt()
    key = os.path.normpath(path)
    try:
        mt = os.path.getmtime(path if not os.path.isdir(path) else os.path.join(path, "tileset.json"))
    except OSError:
        mt = 0.0
    got = _OPEN.get(key)
    if got and got[0] == mt:
        return got[1], got[2]
    tree, rb = D.open_tileset(path)
    _OPEN[key] = (mt, tree, rb)
    return tree, rb


def tiles_estimate(path: str, ids: Sequence[str]) -> Dict[str, Any]:
    D = dt()
    _tree, rb = open_tileset(path)
    stats = []
    for i in ids:
        b = rb(i)
        try:
            stats.append(D.glb_stats(b) if b else None)
        except ValueError:
            stats.append(None)
    return D.estimate(stats)


# ── Blender ──────────────────────────────────────────────────────────────────

def _bpy():  # pragma: no cover — bpy
    import bpy
    return bpy


def em_folder_of(context) -> str:  # pragma: no cover — bpy
    bpy = _bpy()
    try:
        from .project_files import active_emjson
        em = active_emjson(context)
        if em:
            return os.path.dirname(em)
    except Exception:  # noqa: BLE001
        pass
    return os.path.dirname(bpy.data.filepath) if bpy.data.filepath else ""


def _graph(context):  # pragma: no cover — bpy
    try:
        from ..functions import check_active_graph
        ok, graph = check_active_graph(context, show_message=False)
        return graph if ok else None
    except Exception:  # noqa: BLE001
        return None


def get_state(context) -> Dict[str, Any]:  # pragma: no cover — bpy
    return read_state(context.scene.get(STATE_PROP))


def put_state(context, st: Dict[str, Any]) -> None:  # pragma: no cover — bpy
    context.scene[STATE_PROP] = json.dumps(st)


def _collection(context):  # pragma: no cover — bpy
    bpy = _bpy()
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
    if col.name not in context.scene.collection.children:
        try:
            context.scene.collection.children.link(col)
        except RuntimeError:
            pass
    return col


def _import_gltf(path: str) -> List[Any]:  # pragma: no cover — bpy
    bpy = _bpy()
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def _import_any(path: str) -> List[Any]:  # pragma: no cover — bpy
    bpy = _bpy()
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".gltf", ".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise RuntimeError(f"cannot import {os.path.basename(path)}")
    return [o for o in bpy.data.objects if o not in before]


def _adopt(context, objs, *, recipe: str, document: str, source: str, tile: str = "") -> None:  # pragma: no cover
    col = _collection(context)
    for o in objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
        o[P_RECIPE] = recipe
        o[P_DOC] = document
        o[P_SOURCE] = source
        if tile:
            o[P_TILE] = tile


def _matrix(m: Sequence[float]):  # pragma: no cover — bpy
    from mathutils import Matrix
    # column-major (glTF, 3D Tiles) → Blender's rows
    return Matrix([[m[0], m[4], m[8], m[12]], [m[1], m[5], m[9], m[13]],
                   [m[2], m[6], m[10], m[14]], [m[3], m[7], m[11], m[15]]])


def load_tiles(context, path: str, ids: Sequence[str], folder: str, *, recipe: str, document: str,
               ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Write the tiles ``ids`` into ``folder`` (textures outside) and import
    them, each placed by its node's transform."""
    from mathutils import Matrix
    D = dt()
    tree, rb = open_tileset(path)
    made: Dict[str, List[str]] = {}
    for tid in ids:
        node = tree["nodes"].get(tid)
        blob = rb(tid) if node else None
        if not blob:
            continue
        got = D.unpack_glb(blob, folder, D.tile_name(tid))
        objs = _import_gltf(got["gltf"])
        T = _matrix(node["transform"])
        if got.get("rtc_center"):
            T = T @ Matrix.Translation(got["rtc_center"])
        for o in objs:
            if o.parent is None or o.parent not in objs:
                o.matrix_world = T @ o.matrix_world
        _adopt(context, objs, recipe=recipe, document=document, source=path, tile=tid)
        made[tid] = [o.name for o in objs]
    return made


def drop_tiles(context, tile_ids: Iterable[str]) -> int:  # pragma: no cover — bpy
    bpy = _bpy()
    gone = set(tile_ids)
    n = 0
    for o in list(bpy.data.objects):
        if o.get(P_TILE) in gone:
            mesh = o.data if o.type == "MESH" else None
            bpy.data.objects.remove(o, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
            n += 1
    return n


def _keep_recipe(context, r: Dict[str, Any], document_node) -> str:  # pragma: no cover — bpy
    """The recipe into the document's data (D2), and to the room."""
    D = dt()
    if document_node is None:
        return "no document of the graph cites this source: the recipe is kept only in this scene"
    data = _node_data(document_node)
    who = ""
    try:
        from . import room as _room
        who = str((_room.room() or {}).get("author") or "")
    except Exception:  # noqa: BLE001
        pass
    if not D.add_recipe(data, r, made_by=who, at=time.strftime("%Y-%m-%dT%H:%M:%S")):
        return "the recipe was already in the graph"
    try:
        from .operators import emit_op
        emit_op({"op": "update_node", "node_id": document_node.node_id,
                 "patch": {"data": {"detail_recipes": data["detail_recipes"]}}})
    except Exception as exc:  # noqa: BLE001 — the scene keeps it anyway
        return f"recipe kept in the graph; not sent: {exc}"
    return "recipe kept in the graph (and sent to the room when joined)"


def source_document(context, path: str):  # pragma: no cover — bpy
    graph = _graph(context)
    res = resource_for_path(graph, path, em_folder_of(context))
    return res, document_of(graph, res)


def plan_light(context, path: str, level: Optional[int]) -> Dict[str, Any]:  # pragma: no cover — bpy
    tree, _rb = open_tileset(path)
    cut = dt().light_set(tree, level)
    return {"cut": cut, "estimate": tiles_estimate(path, cut), "levels": tree["levels"]}


def do_load_set(context, path: str, level: Optional[int]) -> Dict[str, Any]:  # pragma: no cover — bpy
    D = dt()
    st = get_state(context)
    if st["kind"] == "tileset" and st["cut"]:
        drop_tiles(context, st["cut"])
    tree, _rb = open_tileset(path)
    cut = D.light_set(tree, level)
    res, doc = source_document(context, path)
    root = tree["nodes"][tree["root"]]
    em = em_folder_of(context)
    src = os.path.relpath(path, em).replace(os.sep, "/") if em else path
    r = D.recipe(document=getattr(doc, "node_id", "") or "", resource=getattr(res, "node_id", "") or "",
                 source=src, area=root["aabb"] or [0, 0, 0, 0, 0, 0],
                 level=level if level is not None else 0)
    folder = D.cache_folder(em, r)
    load_tiles(context, path, cut, folder, recipe=r["key"], document=r["document"])
    st.update(kind="tileset", source=path, document=r["document"], resource=r["resource"], cut=cut,
              level=level, recipes=[r])
    put_state(context, st)
    return {"cut": cut, "recipe": r, "folder": folder}


def plan_more(context, area: Sequence[float], to: Any) -> Dict[str, Any]:  # pragma: no cover — bpy
    st = get_state(context)
    tree, _rb = open_tileset(st["source"])
    got = dt().refine(tree, st["cut"], area, to=to)
    got["estimate"] = tiles_estimate(st["source"], got["load"])
    return got


def do_more(context, area: Sequence[float], to: Any) -> Dict[str, Any]:  # pragma: no cover — bpy
    D = dt()
    st = get_state(context)
    path = st["source"]
    tree, _rb = open_tileset(path)
    got = D.refine(tree, st["cut"], area, to=to)
    em = em_folder_of(context)
    src = os.path.relpath(path, em).replace(os.sep, "/") if em else path
    r = D.recipe(document=st["document"], resource=st["resource"], source=src, area=area, level=to)
    folder = D.cache_folder(em, r)
    drop_tiles(context, got["drop"])
    load_tiles(context, path, got["load"], folder, recipe=r["key"], document=r["document"])
    st["cut"] = got["cut"]
    st["recipes"] = list(st.get("recipes") or []) + [r]
    put_state(context, st)
    graph = _graph(context)
    doc = graph.find_node_by_id(st["document"]) if (graph is not None and st["document"]) else None
    said = _keep_recipe(context, r, doc)
    return {"loaded": len(got["load"]), "dropped": len(got["drop"]), "recipe": r, "said": said}


def do_less(context, area: Sequence[float], to: Any) -> Dict[str, Any]:  # pragma: no cover — bpy
    D = dt()
    st = get_state(context)
    path = st["source"]
    tree, _rb = open_tileset(path)
    got = D.coarsen(tree, st["cut"], area, to=to)
    em = em_folder_of(context)
    # what comes back up is what the light set's folder (or a new one) holds
    src = os.path.relpath(path, em).replace(os.sep, "/") if em else path
    r = D.recipe(document=st["document"], resource=st["resource"], source=src, area=area,
                 level=f"up:{to}")
    drop_tiles(context, got["drop"])
    load_tiles(context, path, got["load"], D.cache_folder(em, r), recipe=r["key"], document=r["document"])
    st["cut"] = got["cut"]
    put_state(context, st)
    return {"loaded": len(got["load"]), "dropped": len(got["drop"])}


def regenerate(context, r: Dict[str, Any], *, tileset_path: str = "") -> Dict[str, Any]:  # pragma: no cover
    """«Regenerate from the recipe»: the same cut (a tileset's), or the same
    crop, into this computer's cache."""
    D = dt()
    em = em_folder_of(context)
    path = tileset_path or (os.path.join(em, r["source"]) if not os.path.isabs(r["source"]) else r["source"])
    if r.get("kind") == "crop":
        return crop_into_cache(context, path, r["area"], r.get("resolution") or D.CROP_DEFAULT_M,
                               document=r.get("document") or "", resource=r.get("resource") or "")
    tree, _rb = open_tileset(path)
    got = D.plan_tiles(tree, r)
    st = get_state(context)
    if st["kind"] == "tileset" and st["source"] == path and st["cut"]:
        drop_tiles(context, st["cut"])
    load_tiles(context, path, got["cut"], D.cache_folder(em, r), recipe=r["key"], document=r.get("document") or "")
    st.update(kind="tileset", source=path, document=r.get("document") or "", resource=r.get("resource") or "",
              cut=got["cut"], recipes=[r])
    put_state(context, st)
    return {"loaded": len(got["cut"])}


# ── a master that is not tiled ───────────────────────────────────────────────

def find_3dsc_headless():  # pragma: no cover — bpy
    import sys
    for name, mod in list(sys.modules.items()):
        if name.endswith(".headless") and hasattr(mod, "crop_to_area"):
            return mod
    raise RuntimeError("the crop of a master is 3D Survey Collection's (crop_to_area): "
                       "enable 3D Survey Collection ≥ 1.7.0-dev.25")


def master_ladder(context, obj) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The LODs of the active object's master (light / intermediate /
    densest) with their files, from the graph."""
    graph = _graph(context)
    if graph is None:
        raise RuntimeError("no active graph")
    from .asset_versions import master_of
    from s3dgraphy import api
    mid = master_of(graph, obj, context.scene)
    if not mid:
        raise RuntimeError(f"{obj.name}: no master in the graph")
    em = em_folder_of(context)
    entries = []
    for e in api.versions_of(graph, mid):
        node = graph.find_node_by_id(e.get("id"))
        url = _url_of(node) if node is not None else ""
        if url and "://" not in url:
            e = dict(e)
            e["path"] = url if os.path.isabs(url) else os.path.normpath(os.path.join(em, url))
            entries.append(e)
    got = dt().master_levels(entries)
    got["master_id"] = mid
    got["document"] = getattr(document_of(graph, graph.find_node_by_id(mid)), "node_id", "") or ""
    return got


def load_master_level(context, path: str, *, document: str, resource: str) -> List[str]:  # pragma: no cover
    """A LOD of a master is a stamped file: imported from where it is (no
    copy), tagged as detail so it is never stamped again from here."""
    objs = _import_any(path)
    _adopt(context, objs, recipe="", document=document, source=path)
    st = get_state(context)
    st.update(kind="master", source=path, document=document, resource=resource, cut=[], recipes=[])
    put_state(context, st)
    return [o.name for o in objs]


def crop_into_cache(context, source: str, area: Sequence[float], resolution: float, *,
                    document: str = "", resource: str = "") -> Dict[str, Any]:  # pragma: no cover — bpy
    """The crop of a master (D3) through 3DSC, into the cache, imported."""
    D = dt()
    em = em_folder_of(context)
    src = os.path.relpath(source, em).replace(os.sep, "/") if em else source
    r = D.recipe(kind="crop", document=document, resource=resource, source=src, area=area,
                 resolution=resolution)
    folder = D.cache_folder(em, r)
    H = find_3dsc_headless()
    out = H.crop_to_area(source, list(area), resolution, folder, name="crop", emit=False)
    if not out.get("ok"):
        raise RuntimeError(out.get("error") or "the crop failed")
    objs = _import_gltf(out["path"])
    _adopt(context, objs, recipe=r["key"], document=document, source=source)
    graph = _graph(context)
    doc = graph.find_node_by_id(document) if (graph is not None and document) else None
    said = _keep_recipe(context, r, doc)
    st = get_state(context)
    st["recipes"] = list(st.get("recipes") or []) + [r]
    put_state(context, st)
    return {"recipe": r, "result": out, "objects": [o.name for o in objs], "said": said}


def selection_area(context, pad: float = 0.0) -> Optional[List[float]]:  # pragma: no cover — bpy
    from mathutils import Vector
    boxes = []
    for o in context.selected_objects:
        if o.type not in ("MESH", "EMPTY", "CURVE"):
            continue
        boxes.append([tuple(o.matrix_world @ Vector(c)) for c in o.bound_box])
    return area_from_boxes(boxes, pad)


def is_detail(obj) -> bool:
    try:
        return bool(obj.get(P_RECIPE) or obj.get(P_TILE) or obj.get(P_SOURCE))
    except Exception:  # noqa: BLE001
        return False


# ── operators, panel ─────────────────────────────────────────────────────────

def _operator_classes():  # pragma: no cover — bpy
    bpy = _bpy()
    from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty

    START = [("lightest", "Lightest", "the coarsest level of the tileset, or the lightest LOD"),
             ("intermediate", "Intermediate", "a level in the middle"),
             ("level", "A level", "the level given below")]

    class EM_OT_detail_load_set(bpy.types.Operator):
        """Load the light set of a tileset (folder, tileset.json, .3tz) or of the active
        object's master: the estimate is shown before anything is loaded"""
        bl_idname = "em.detail_load_set"
        bl_label = "Load the light set"
        bl_options = {"REGISTER", "UNDO"}
        filepath: StringProperty(name="Tileset", subtype="FILE_PATH", default="")  # type: ignore
        start: EnumProperty(name="Start from", items=START, default="lightest")  # type: ignore
        level: IntProperty(name="Level", default=2, min=0)  # type: ignore

        def _level(self, path: str):
            if self.start == "lightest":
                return None
            if self.start == "level":
                return self.level
            tree, _rb = open_tileset(path)
            return max(0, int(tree["depth"]) // 2)

        def invoke(self, context, event):
            try:
                dt()
            except RuntimeError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            if not self.filepath:
                self.filepath = context.scene.get("em_detail_last_source", "") or ""
            return context.window_manager.invoke_props_dialog(self, width=520)

        def draw(self, context):
            col = self.layout.column()
            col.prop(self, "filepath")
            col.prop(self, "start")
            if self.start == "level":
                col.prop(self, "level")
            path = bpy.path.abspath(self.filepath)
            if path and is_tileset_path(path):
                try:
                    p = plan_light(context, path, self._level(path))
                    col.label(text="Levels: " + ", ".join(f"{k}:{v}" for k, v in p["levels"].items()))
                    for line in estimate_lines(p["estimate"]):
                        col.label(text=line, icon="MEMORY")
                except Exception as exc:  # noqa: BLE001
                    col.label(text=str(exc), icon="ERROR")
            elif not path and context.active_object is not None:
                col.label(text=f"No tileset: the lightest LOD of {context.active_object.name}'s master",
                          icon="INFO")

        def execute(self, context):
            path = bpy.path.abspath(self.filepath)
            try:
                if path and is_tileset_path(path):
                    context.scene["em_detail_last_source"] = self.filepath
                    got = do_load_set(context, path, self._level(path))
                    self.report({"INFO"}, f"Light set: {len(got['cut'])} tile(s) in the cache")
                    return {"FINISHED"}
                obj = context.active_object
                if obj is None:
                    self.report({"WARNING"}, "Give a tileset, or select an object with a master")
                    return {"CANCELLED"}
                lad = master_ladder(context, obj)
                pick = lad["light"] if self.start == "lightest" else lad["intermediate"]
                if not pick:
                    self.report({"WARNING"}, "The master has no file to load")
                    return {"CANCELLED"}
                names = load_master_level(context, pick["path"], document=lad["document"],
                                          resource=lad["master_id"])
                self.report({"INFO"}, f"Loaded {pick.get('level') or 'master'}: {len(names)} object(s)")
                return {"FINISHED"}
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}

    TO = [("next", "One level more", "the next level of the tileset"),
          ("densest", "Densest", "down to the densest level where asked")]
    RES = [("0.05", "5 cm", "the default for a master that is not tiled"),
           ("0.01", "1 cm", "only on a small area (a few metres a side)")]

    class EM_OT_detail_more_here(bpy.types.Operator):
        """More detail on the box of the selected objects: the estimate before confirming"""
        bl_idname = "em.detail_more_here"
        bl_label = "More detail here"
        bl_options = {"REGISTER", "UNDO"}
        to: EnumProperty(name="Down to", items=TO, default="next")  # type: ignore
        resolution: EnumProperty(name="Resolution", items=RES, default="0.05")  # type: ignore
        pad: FloatProperty(name="Margin (m)", default=0.0, min=0.0)  # type: ignore

        def invoke(self, context, event):
            try:
                dt()
            except RuntimeError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            if selection_area(context) is None:
                self.report({"WARNING"}, "Select the objects whose box asks for more detail")
                return {"CANCELLED"}
            return context.window_manager.invoke_props_dialog(self, width=520)

        def draw(self, context):
            col = self.layout.column()
            st = get_state(context)
            area = selection_area(context, self.pad)
            a = area or [0] * 6
            col.label(text=f"Area {a[3] - a[0]:.1f} × {a[4] - a[1]:.1f} × {a[5] - a[2]:.1f} m")
            col.prop(self, "pad")
            if st["kind"] == "tileset":
                col.prop(self, "to")
                try:
                    p = plan_more(context, area, self.to)
                    col.label(text=f"{len(p['load'])} tiles to load, {len(p['drop'])} to drop")
                    for line in estimate_lines(p["estimate"]):
                        col.label(text=line, icon="MEMORY")
                except Exception as exc:  # noqa: BLE001
                    col.label(text=str(exc), icon="ERROR")
            else:
                col.prop(self, "resolution")
                src = st["source"] if st["kind"] == "master" else ""
                p = dt().crop_plan(area, float(self.resolution),
                                   texture_px=source_texture_px(src) if src else 0)
                col.label(text=p["say"], icon="MEMORY" if p["ok"] else "ERROR")

        def execute(self, context):
            st = get_state(context)
            area = selection_area(context, self.pad)
            try:
                if st["kind"] == "tileset":
                    got = do_more(context, area, self.to)
                    self.report({"INFO"}, f"Loaded {got['loaded']}, dropped {got['dropped']} — {got['said']}")
                    return {"FINISHED"}
                plan = dt().crop_plan(area, float(self.resolution))
                if not plan["ok"]:
                    self.report({"WARNING"}, plan["say"])
                    return {"CANCELLED"}
                obj = context.active_object
                lad = master_ladder(context, obj) if obj is not None and not st["source"] else None
                source = (lad["densest"]["path"] if lad else "") or ""
                if lad is None and st["kind"] == "master":
                    graph = _graph(context)
                    from s3dgraphy import api
                    master = graph.find_node_by_id(st["resource"]) if graph is not None else None
                    url = _url_of(master) if master is not None else ""
                    source = (url if os.path.isabs(url) else os.path.join(em_folder_of(context), url)) \
                        if url else st["source"]
                if not source:
                    self.report({"WARNING"}, "No master to crop: load the light set first")
                    return {"CANCELLED"}
                got = crop_into_cache(context, source, area, float(self.resolution),
                                      document=st["document"] or (lad or {}).get("document", ""),
                                      resource=st["resource"] or (lad or {}).get("master_id", ""))
                self.report({"INFO"}, f"Crop: {got['result'].get('triangles')} triangles — {got['said']}")
                return {"FINISHED"}
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}

    UP = [("previous", "One level less", "back one level"),
          ("light", "Back to the light set", "the light set's level")]

    class EM_OT_detail_less(bpy.types.Operator):
        """Less detail on the box of the selected objects (frees memory)"""
        bl_idname = "em.detail_less"
        bl_label = "Less detail"
        bl_options = {"REGISTER", "UNDO"}
        to: EnumProperty(name="Up to", items=UP, default="previous")  # type: ignore

        def invoke(self, context, event):
            if get_state(context)["kind"] != "tileset":
                self.report({"WARNING"}, "Less detail works on a tileset's light set; delete a crop by hand")
                return {"CANCELLED"}
            return context.window_manager.invoke_props_dialog(self)

        def execute(self, context):
            area = selection_area(context)
            if area is None:
                self.report({"WARNING"}, "Select the tiles (or objects) where to free detail")
                return {"CANCELLED"}
            try:
                got = do_less(context, area, self.to)
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            self.report({"INFO"}, f"Dropped {got['dropped']}, loaded {got['loaded']}")
            return {"FINISHED"}

    class EM_OT_detail_regenerate(bpy.types.Operator):
        """Regenerate the recipes of the room (the active document's) into this computer's cache"""
        bl_idname = "em.detail_regenerate"
        bl_label = "Regenerate from the recipes"
        bl_options = {"REGISTER", "UNDO"}
        document: StringProperty(default="")  # type: ignore

        def execute(self, context):
            graph = _graph(context)
            D = dt()
            recs = []
            for n in getattr(graph, "nodes", []) or []:
                if getattr(n, "node_type", None) == "document" and (not self.document or n.node_id == self.document):
                    recs += D.recipes_of(_node_data(n))
            if not recs:
                self.report({"INFO"}, "No recipe of detail in the graph")
                return {"CANCELLED"}
            n = 0
            for r in recs:
                try:
                    regenerate(context, r)
                    n += 1
                except Exception as exc:  # noqa: BLE001
                    self.report({"WARNING"}, f"{r.get('key')}: {exc}")
            self.report({"INFO"}, f"Regenerated {n} of {len(recs)}")
            return {"FINISHED"}

    return (EM_OT_detail_load_set, EM_OT_detail_more_here, EM_OT_detail_less, EM_OT_detail_regenerate)


def draw(layout, context) -> None:  # pragma: no cover — bpy
    """«Detail on request» in «Asset versions»."""
    box = layout.box()
    box.label(text="Detail on request (cache, never stamped)", icon="MOD_MULTIRES")
    st = read_state(context.scene.get(STATE_PROP))
    col = box.column(align=True)
    col.operator("em.detail_load_set", icon="IMPORT", text="Load the light set…")
    row = col.row(align=True)
    row.enabled = bool(st["kind"]) and bool(context.selected_objects)
    row.operator("em.detail_more_here", icon="ZOOM_IN", text="More detail here")
    row.operator("em.detail_less", icon="ZOOM_OUT", text="Less detail")
    col.operator("em.detail_regenerate", icon="FILE_REFRESH", text="Regenerate from the recipes")
    if st["kind"]:
        box.label(text=f"{st['kind']}: {os.path.basename(st['source'])} · {len(st['cut'])} tiles · "
                       f"{len(st['recipes'])} recipe(s)", icon="INFO")


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    bpy = _bpy()
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():  # pragma: no cover — bpy
    bpy = _bpy()
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
