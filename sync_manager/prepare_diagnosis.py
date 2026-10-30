"""Prepare a model for a use: the DIAGNOSIS, the grid of the improvements, the
version they make (MICRO-PREPARA-DIAGNOSI, E.D. 30 Oct 2026).

Templu Mare, II century (SB/versions, measured on 30 Oct): 87 objects,
``lod0-aton-heriverse`` 3.03 M triangles / 223 MB, ``lod1-realtime-web`` 1.53 M
/ 23 MB; some sixty columns, each a COPY of one of three meshes. The options of
the old «Export to Heriverse» (Draco, separate textures, GPU instancing, texture
compression) had left the menus; «Export a version for a use…» kept Draco only.

Here, for the selection (by default the RM container of the active object, or
the selected objects), and a PROFILE of use:

* the numbers are MEASURED in Blender (:func:`measure_objects`) and the
  DIAGNOSIS is s3Dgraphy's (``resources.use_profiles.diagnose``): the same
  table of profiles and the same pure function EMStudio's bridge reads, so the
  same objects give the same numbers here, in ``blender -b`` and in EMStudio;
* the GRID: one row per problem, its action, its effect, a tick;
* «Apply the ticks» (:func:`apply`) writes the version for that use in the
  canonical folder ``RB|SB/versions/<model>@<level>-<destination>.glb|gltf``
  (beside the .blend), stamped as derived and registered in the graph — never
  over a file already there without the person saying so, and the .blend is
  not touched: everything is done on temporary copies, removed at the end.

Actions: copies of one geometry become ONE mesh drawn as instances (the copies
are the same topology and UVs, placed by a similarity: the transform is
measured, a copy it does not explain stays a copy); textures reduced to the
profile's side and written as JPEG (Blender cannot write KTX2: gltfpack in
EMStudio can, the row says so); an object over the budget decimated with a
normal map baked from the full mesh (3D Survey Collection's headless
``make_lod_set(normal_map=True)``); Draco when the profile wants compressed
geometry and Blender is the engine (meshopt is gltfpack's).

The pure parts (:func:`similarity`, :func:`target_name`, :func:`level_for`,
:func:`file_rows_lines`) are measured by ``tests/test_prepare_diagnosis.py``.
"""

# NOT `from __future__ import annotations` (the operators' annotations are
# evaluated by Blender in this module's globals; see asset_versions).
import hashlib
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence

#: the last measurement and diagnosis, for the dialog (session state)
LAST: Dict[str, Any] = {}

TOO_OLD = ("this Blender's s3dgraphy has no profiles of use "
           "(s3dgraphy.resources.use_profiles, after 1.6.0.dev72): "
           "./em.sh rebundle --python 3.13 in EM-blender-tools, then restart Blender")

_NS = uuid.uuid5(uuid.NAMESPACE_URL, "https://extendedmatrix.org/emtools/prepared-for-use")


def use_profiles():
    """s3Dgraphy's table and diagnosis, or ``RuntimeError(TOO_OLD)``."""
    try:
        from s3dgraphy.resources import use_profiles as UP
    except ImportError as exc:
        raise RuntimeError(TOO_OLD) from exc
    return UP


# ── pure ────────────────────────────────────────────────────────────────────

def similarity(a, b, *, tol: float = 1e-3):
    """The affine map that takes the vertices ``a`` (N×3, the prototype) onto
    ``b`` (N×3, a copy with the same vertex order), when it is a SIMILARITY
    (rotation, uniform scale, translation; a mirror allowed) and explains every
    vertex within ``tol`` × the size of ``a``. → ``(4×4 list, residual)`` or
    ``(None, why)``. Measured on Templu Mare: the columns are copies at scale
    0.857 or 1, residual ≤ 3e-5 m."""
    import numpy as np
    a = np.asarray(a, dtype=np.float64).reshape(-1, 3)
    b = np.asarray(b, dtype=np.float64).reshape(-1, 3)
    if a.shape != b.shape or len(a) < 4:
        return None, "not the same vertices"
    ah = np.hstack([a, np.ones((len(a), 1))])
    x, *_ = np.linalg.lstsq(ah, b, rcond=None)
    lin = x[:3].T
    size = float(np.linalg.norm(a.max(axis=0) - a.min(axis=0))) or 1.0
    res = float(np.abs(ah @ x - b).max())
    if res > tol * size + 1e-6:
        return None, f"not the same shape (residual {res:.4g})"
    sv = np.linalg.svd(lin, compute_uv=False)
    if sv.min() <= 0 or (sv.max() - sv.min()) > 1e-3 * sv.max():
        return None, "stretched, not only scaled"
    m = np.eye(4)
    m[:3, :3] = lin
    m[:3, 3] = x[3]
    return m.tolist(), res


def level_for(checked_kinds: Iterable[str]) -> str:
    """``lod1`` when the geometry is decimated, else ``lod0`` (the version keeps
    the master's triangles)."""
    return "lod1" if "decimate" in set(checked_kinds) else "lod0"


def target_name(folder: str, model: str, level: str, prof: Dict[str, Any],
                packaging: Optional[str] = None) -> str:
    """Where the version goes: ``<folder>/<model>@<level>-<destination>.glb``
    (``.gltf`` in a folder of its own for a glTF separate:
    ``<model>@<level>-<destination>/<model>.gltf``)."""
    UP = use_profiles()
    name = UP.version_file_name(model, level, prof, packaging)
    if name.endswith(".gltf"):
        stem = name[:-5]
        return os.path.join(folder, stem, name.split("@")[0] + ".gltf")
    return os.path.join(folder, name)


def target_files(entry: str) -> List[str]:
    """What is there already at the target (the glb and its stamp, or the
    folder of the glTF): what «replace» removes first."""
    out = []
    if entry.endswith(".gltf"):
        d = os.path.dirname(entry)
        if os.path.isdir(d):
            out.append(d)
    elif os.path.exists(entry):
        out.append(entry)
    for f in (entry + ".stamp.json",):
        if os.path.exists(f):
            out.append(f)
    return out


def mb(n: float) -> str:
    return f"{n / (1024 * 1024):.1f} MB"


def effect_line(eff: Dict[str, Any]) -> str:
    """«−11 meshes · −23.6 MB download · −70.2 MB GPU · −11 draw calls»."""
    parts = []
    if eff.get("triangles"):
        parts.append(f"{eff['triangles']:+,} tris")
    elif eff.get("triangles_stored"):
        parts.append(f"{eff['triangles_stored']:+,} tris stored")
    if eff.get("download_bytes"):
        parts.append(f"{eff['download_bytes'] / 1048576:+.1f} MB download")
    if eff.get("gpu_bytes"):
        parts.append(f"{eff['gpu_bytes'] / 1048576:+.1f} MB GPU")
    if eff.get("draw_calls"):
        parts.append(f"{eff['draw_calls']:+} draw calls")
    return " · ".join(parts) or "—"


def file_rows_lines(rows: Sequence[Dict[str, Any]], nodes: Dict[str, List[str]]) -> List[str]:
    """The warning of a removal: which files, which nodes of the graph."""
    out = []
    for r in rows:
        n = len(r.get("files") or [])
        out.append(f"{r['name']}: {n} file(s), {mb(r.get('bytes') or 0)}")
        for name in nodes.get(r["name"], []):
            out.append(f"   graph: {name}")
    return out


# ── Blender: the numbers ────────────────────────────────────────────────────

def _bpy():  # pragma: no cover — bpy
    import bpy  # type: ignore
    return bpy


def _image_bytes(img) -> int:  # pragma: no cover — bpy
    if img.packed_file is not None:
        return int(img.packed_file.size)
    try:
        p = _bpy().path.abspath(img.filepath)
        return os.path.getsize(p) if p and os.path.isfile(p) else 0
    except Exception:  # noqa: BLE001
        return 0


_FORMATS = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp", "OPEN_EXR": "exr",
            "TARGA": "tga", "TIFF": "tiff", "BMP": "bmp"}


def geometry_key(mesh) -> str:  # pragma: no cover — bpy
    """The same geometry wherever it is placed: the faces' vertex order and the
    UVs (a copy moved, turned or scaled keeps both)."""
    import numpy as np
    h = hashlib.sha256()
    lv = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", lv)
    ls = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get("loop_start", ls)
    h.update(lv.tobytes())
    h.update(ls.tobytes())
    if mesh.uv_layers.active is not None:
        uv = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        mesh.uv_layers.active.data.foreach_get("uv", uv)
        h.update(np.round(uv, 5).tobytes())
    h.update(str((len(mesh.vertices), len(mesh.polygons))).encode())
    return "b:" + h.hexdigest()[:16]


def _tris(mesh) -> int:  # pragma: no cover — bpy
    import numpy as np
    n = len(mesh.polygons)
    if not n:
        return 0
    lt = np.empty(n, dtype=np.int32)
    mesh.polygons.foreach_get("loop_total", lt)
    return int((lt - 2).sum())


def measure_objects(objs, context=None) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The objects and textures of ``objs`` in the shape s3Dgraphy's
    ``diagnose`` takes. The mesh is the EVALUATED one (modifiers applied, what
    an export writes); objects showing one mesh with no modifiers share its
    ``mesh_id``."""
    import numpy as np
    bpy = _bpy()
    ctx = context or bpy.context
    deps = ctx.evaluated_depsgraph_get()
    objects, textures = [], {}
    for obj in objs:
        if obj.type != "MESH" or obj.data is None:
            continue
        ev = obj.evaluated_get(deps)
        mesh = ev.to_mesh()
        try:
            tris = _tris(mesh)
            mi = np.empty(len(mesh.polygons), dtype=np.int32)
            mesh.polygons.foreach_get("material_index", mi)
            slots = sorted(set(int(x) for x in mi)) if len(mi) else []
            tex, normal = [], False
            for s in slots:
                mat = obj.material_slots[s].material if s < len(obj.material_slots) else None
                if mat is None or mat.node_tree is None:
                    continue
                for node in mat.node_tree.nodes:
                    if node.bl_idname == "ShaderNodeNormalMap":
                        normal = True
                    img = getattr(node, "image", None)
                    if img is None or not img.size[0]:
                        continue
                    tex.append(img.name)
                    if img.name not in textures:
                        textures[img.name] = {
                            "width": int(img.size[0]), "height": int(img.size[1]),
                            "bytes": _image_bytes(img),
                            "format": _FORMATS.get(img.file_format, img.file_format.lower())}
            objects.append({
                "name": obj.name, "triangles": tris, "vertices": len(mesh.vertices),
                "materials": max(1, len(slots)) if tris else 0,
                "mesh_id": obj.data.name if not obj.modifiers else f"{obj.name}|evaluated",
                "geometry_key": geometry_key(mesh), "textures": sorted(set(tex)),
                "normal_map": normal})
        finally:
            ev.to_mesh_clear()
    return {"objects": objects, "textures": textures}


def container_of(scene, obj):  # pragma: no cover — bpy
    """The first RM container that holds ``obj`` (its row), or None."""
    for c in getattr(scene, "rm_containers", ()):
        if any(e.name == obj.name for e in c.mesh_names):
            return c
    return None


def selection(context, scope: str):  # pragma: no cover — bpy
    """``(objects, model name, container row or None)`` for ``scope``:
    CONTAINER — the meshes of the active object's container; SELECTED — the
    selected meshes (the model is named after the active one, or its
    container when they all sit in it)."""
    bpy = _bpy()
    act = context.active_object
    if scope == "CONTAINER" and act is not None:
        c = container_of(context.scene, act)
        if c is not None:
            objs = [bpy.data.objects.get(e.name) for e in c.mesh_names]
            objs = [o for o in objs if o is not None and o.type == "MESH"]
            return objs, (c.label or c.doc_name or act.name), c
    objs = [o for o in context.selected_objects if o.type == "MESH"]
    if act is not None and act.type == "MESH" and act not in objs:
        objs.insert(0, act)
    if not objs:
        return [], "", None
    c = container_of(context.scene, objs[0])
    if c is not None and len(objs) > 1 and all(container_of(context.scene, o) == c for o in objs):
        return objs, (c.label or c.doc_name or objs[0].name), c
    name = act.name if act is not None and act in objs else objs[0].name
    return objs, (name if len(objs) == 1 else f"{name}+{len(objs) - 1}"), c if len(objs) == 1 else None


def headless_3dsc():  # pragma: no cover — bpy
    """3D Survey Collection's headless module (``make_lod_set``), or None."""
    for name, mod in list(sys.modules.items()):
        if name.endswith(".headless") and hasattr(mod, "make_lod_set"):
            return mod
    return None


def diagnose_here(context, objs, prof_key: str) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Measure (once per selection) and diagnose for ``prof_key``; the
    decimation rows say when 3DSC is not there to bake the normal map."""
    UP = use_profiles()
    key = tuple(sorted(o.name for o in objs))
    if LAST.get("key") != key:
        t0 = time.time()
        LAST.clear()
        LAST.update(key=key, measured=measure_objects(objs, context),
                    measure_seconds=round(time.time() - t0, 2))
    m = LAST["measured"]
    d = UP.diagnose_keep(m["objects"], m["textures"], prof_key, engine="blender")
    if headless_3dsc() is None:
        for r in d["improvements"]:
            if r["kind"] == "decimate":
                r.update(available=False, checked=False,
                         why="3D Survey Collection is not loaded in this Blender (its "
                             "headless make_lod_set bakes the normal map)")
    LAST["diagnosis"] = d
    return d


# ── Blender: the version ────────────────────────────────────────────────────

def _gltf_kwargs(**wanted):  # pragma: no cover — bpy
    bpy = _bpy()
    try:
        names = {p.identifier for p in bpy.ops.export_scene.gltf.get_rna_type().properties}
    except Exception:  # noqa: BLE001
        return wanted
    return {k: v for k, v in wanted.items() if k in names}


def _decimated_mesh(proto, triangles_to: int, side: int, workdir: str, say) -> Any:  # pragma: no cover — bpy
    """The mesh of ``proto`` brought to ``triangles_to`` with its colour and a
    normal map baked from the full mesh (3DSC ``make_lod_set``), read back
    from the glb it writes."""
    bpy = _bpy()
    hl = headless_3dsc()
    if hl is None:
        raise RuntimeError("3D Survey Collection is not loaded: no decimation with a normal map")
    tris = _tris(proto.data) or 1
    ratio = max(0.0005, min(1.0, float(triangles_to) / tris))
    out = os.path.join(workdir, "lod")
    res = hl.make_lod_set(proto, out, levels=[ratio], texture_px=int(side or 2048),
                          normal_map=True, stamp=False, emit=False, name=f"_em_dec_{len(os.listdir(workdir))}")
    path = res["outputs"][0]["path"]
    say(f"{proto.name}: {tris:,} → {res['outputs'][0]['triangles']:,} triangles, "
        f"normal map {res['outputs'][0]['texture_px']} px")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    mesh_obj = next(o for o in new if o.type == "MESH")
    mesh = mesh_obj.data
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    for img in mesh_images(mesh):
        img.pack()
    return mesh


def mesh_images(mesh):  # pragma: no cover — bpy
    out = []
    for mat in mesh.materials:
        if mat is not None and mat.node_tree is not None:
            for n in mat.node_tree.nodes:
                img = getattr(n, "image", None)
                if img is not None and img not in out:
                    out.append(img)
    return out


def apply(context, objs, diagnosis: Dict[str, Any], checked: Iterable[str], *, model: str,
          level: str, folder: str, replace: bool = False, container=None,
          graph=None, say=print) -> Dict[str, Any]:  # pragma: no cover — bpy
    """«Apply the ticks»: the version of ``objs`` for the diagnosis' profile,
    written at :func:`target_name`, stamped, registered in ``graph``.

    Everything happens on temporary objects, meshes, materials and images in a
    collection of their own, removed at the end (also on failure); the source
    objects are not changed. → ``{entry, files, bytes, measured, instanced,
    decimated, resized, warnings, registered}``."""
    bpy = _bpy()
    UP = use_profiles()
    prof = UP.profile(diagnosis["profile"])
    ch = UP.choices(diagnosis, list(checked))
    entry = target_name(folder, model, level, prof, ch["packaging"])
    there = target_files(entry)
    if there and not replace:
        shown = os.path.basename(os.path.dirname(entry) if entry.endswith(".gltf") else entry)
        raise FileExistsError(f"{shown} is already in {folder}: tick "
                              f"«Replace the version there» to make it again")
    warnings: List[str] = []
    before = {k: set(getattr(bpy.data, k)) for k in
              ("objects", "meshes", "materials", "images", "collections")}
    col = bpy.data.collections.new("_em_prepare_for_use")
    context.scene.collection.children.link(col)
    workdir = tempfile.mkdtemp(prefix="em_prepare_")
    layer = context.view_layer
    was_selected = [o for o in layer.objects if o.select_get()]
    was_active = layer.objects.active
    out: Dict[str, Any] = {"warnings": warnings, "instanced": 0, "decimated": 0, "resized": 0}
    try:
        deps = context.evaluated_depsgraph_get()
        key = tuple(sorted(o.name for o in objs))
        got = LAST["measured"] if LAST.get("key") == key else measure_objects(objs, context)
        measured = {o["name"]: o for o in got["objects"]}
        temps: Dict[str, Any] = {}
        meshes: Dict[str, Any] = {}           # source object → its temporary mesh
        for obj in sorted(objs, key=lambda o: o.name):
            if not (measured.get(obj.name) or {}).get("triangles"):
                warnings.append(f"{obj.name} has no faces (its linked library lost?): left out")
                continue
            mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(deps),
                                                    preserve_all_data_layers=True,
                                                    depsgraph=deps)
            mesh.name = f"_em_{obj.name}"
            t = bpy.data.objects.new(obj.name, mesh)
            t.matrix_world = obj.matrix_world.copy()
            col.objects.link(t)
            temps[obj.name], meshes[obj.name] = t, mesh
        # ── instances: one mesh per geometry, the copies placed by their similarity
        import numpy as np
        from mathutils import Matrix
        groups: Dict[str, List[str]] = {}
        for name, m in measured.items():
            if name in temps:
                groups.setdefault(m["geometry_key"], []).append(name)
        for key in ch["instanced"]:
            names = sorted(groups.get(key) or [])
            if len(names) < 2:
                continue
            proto = temps[names[0]]
            pm = proto.data
            a = np.empty(len(pm.vertices) * 3)
            pm.vertices.foreach_get("co", a)
            for name in names[1:]:
                t = temps[name]
                b = np.empty(len(t.data.vertices) * 3)
                t.data.vertices.foreach_get("co", b)
                m, why = similarity(a, b)
                if m is None:
                    warnings.append(f"{name} stays a copy: {why}")
                    continue
                old = t.data
                t.data = pm
                t.matrix_world = t.matrix_world @ Matrix(m)
                if old.users == 0:
                    bpy.data.meshes.remove(old)
                out["instanced"] += 1
        # ── decimation with a normal map, once per geometry (its copies share it)
        side = ch["tex_side"] or prof.get("max_texture_side") or 2048
        for key, to in sorted(ch["decimated"].items()):
            names = sorted(n for n in groups.get(key) or [] if n in temps)
            done = {}
            for name in names:
                t = temps[name]
                if t.data.name in done:
                    small = done[t.data.name]
                else:
                    small = _decimated_mesh(t, to, side, workdir, say)
                    done[t.data.name] = small
                    out["decimated"] += 1
                t.data = small
        # ── textures at the profile's side
        if ch["tex_side"]:
            copies: Dict[str, Any] = {}
            mats: Dict[str, Any] = {}
            for mesh in {t.data for t in temps.values()}:
                for i, mat in enumerate(list(mesh.materials)):
                    if mat is None or mat.node_tree is None:
                        continue
                    if mat.name not in mats:
                        cp = mat.copy()
                        for node in cp.node_tree.nodes:
                            img = getattr(node, "image", None)
                            if img is None or not img.size[0]:
                                continue
                            big = max(img.size[0], img.size[1])
                            if big <= ch["tex_side"]:
                                continue
                            if img.name not in copies:
                                small = img.copy()
                                k = ch["tex_side"] / float(big)
                                small.scale(max(1, int(img.size[0] * k)), max(1, int(img.size[1] * k)))
                                copies[img.name] = small
                                out["resized"] += 1
                            node.image = copies[img.name]
                        mats[mat.name] = cp
                    mesh.materials[i] = mats[mat.name]
        # ── one parent at the origin: what Blender's exporter needs to write
        #    EXT_mesh_gpu_instancing for the objects that share a mesh
        root = bpy.data.objects.new("_em_root", None)
        col.objects.link(root)
        for t in temps.values():
            mw = t.matrix_world.copy()
            t.parent = root
            t.matrix_world = mw
        for o in layer.objects:
            o.select_set(False)
        for t in list(temps.values()) + [root]:
            t.select_set(True)
        layer.objects.active = root
        # ── written: into a temporary place, then moved over the target
        gltf = ch["packaging"] == "gltf_separate"
        tmp_entry = os.path.join(workdir, "out", os.path.basename(entry))
        os.makedirs(os.path.dirname(tmp_entry), exist_ok=True)
        fmt = ch["tex_format"]
        kw = _gltf_kwargs(
            filepath=tmp_entry, use_selection=True, export_format="GLTF_SEPARATE" if gltf else "GLB",
            export_apply=False, export_yup=True, export_texcoords=True, export_normals=True,
            export_tangents=bool(out["decimated"]), export_materials="EXPORT",
            export_image_format="JPEG" if fmt == "jpeg" else "AUTO",
            export_jpeg_quality=90, export_image_quality=90,
            export_draco_mesh_compression_enable=ch["compression"] == "draco",
            export_gpu_instances=bool(ch["instanced"]), export_extras=False,
            export_animations=False, export_cameras=False, export_lights=False)
        say(f"writing {os.path.basename(entry)} ({len(temps)} objects)")
        r = bpy.ops.export_scene.gltf(**kw)
        if "FINISHED" not in r or not os.path.isfile(tmp_entry):
            raise RuntimeError("the glTF export failed")
        for p in there:
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        os.makedirs(folder, exist_ok=True)
        if gltf:
            shutil.move(os.path.dirname(tmp_entry), os.path.dirname(entry))
        else:
            shutil.move(tmp_entry, entry)
        m = UP.measure_gltf(entry)
        out.update(entry=entry, files=m["files"], bytes=m["bytes"], measured={
            "triangles": sum(o["triangles"] * o["instances"] for o in m["objects"]),
            "triangles_stored": sum(o["triangles"] for o in {o["mesh_id"]: o for o in m["objects"]}.values()),
            "nodes": len(m["objects"]), "instancing": m["instancing"],
            "textures": len(m["textures"]), "compression": m["compression"]})
        out["registered"] = register_version(context, graph, objs, entry, diagnosis, ch, model=model,
                                     level=level, container=container, warnings=warnings,
                                     measured=out["measured"])
    finally:
        for o in layer.objects:
            try:
                o.select_set(False)
            except Exception:  # noqa: BLE001
                pass
        for kind in ("objects", "meshes", "materials", "images", "collections"):
            coll = getattr(bpy.data, kind)
            for block in [b for b in coll if b not in before[kind]]:
                try:
                    coll.remove(block, do_unlink=True)
                except Exception:  # noqa: BLE001
                    pass
        for o in was_selected:
            try:
                o.select_set(True)
            except ReferenceError:
                pass
        if was_active is not None:
            layer.objects.active = was_active
        shutil.rmtree(workdir, ignore_errors=True)
    return out


def register_version(context, graph, objs, entry: str, diagnosis: Dict[str, Any], ch: Dict[str, Any], *,
             model: str, level: str, container, warnings: List[str],
             measured: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The version's stamp (derived from the objects' masters) and its place in
    the graph: a resource of its own (``tier: distribution``, its uses, the
    profile, ``represents`` the container or the objects) and ONE export step
    whose inputs are the objects' masters — the shape EMStudio gives a tileset
    of a survey's parts. Without a graph the file is stamped and said."""
    from .. import birth_stamp as BS
    from . import asset_versions as AV
    UP = use_profiles()
    prof = UP.profile(diagnosis["profile"])
    rid = str(uuid.uuid5(_NS, f"{model}|{level}|{prof['destination']}"))
    params = {"profile": prof["id"], "rows": ",".join(ch["rows"]),
              "instanced_geometries": len(ch["instanced"]),
              "decimated_geometries": len(ch["decimated"]),
              "texture_side": ch["tex_side"] or 0, "texture_format": ch["tex_format"] or "keep",
              "compression": ch["compression"] or "none", "packaging": ch["packaging"],
              "triangles": measured["triangles"], "objects": len(objs),
              "tool": "EM Tools · Prepare for a use (diagnosis)"}
    technique = "preparation for " + prof["label"]
    label = f"{model} {level} for {prof['label']}"
    stamped = BS.stamp_blender_export(entry, objects=list(objs), dtc_kind=BS.KIND_EXPORT,
                                      technique=technique, parameters=params,
                                      resource_id=rid, label=label,
                                      register_in_graph=False, context=context, force=True)
    out = {"stamp": stamped.get("state"), "stamp_path": stamped.get("stamp_path", ""),
           "resource_id": None, "inputs": [], "missing": []}
    if graph is None:
        warnings.append("no graph loaded: the version is written and stamped, not registered")
        return out
    from s3dgraphy import api
    from s3dgraphy.dtc.ingest import declare_derivation
    masters, missing = [], []
    for o in objs:
        a = AV.master_of(graph, o, context.scene)
        if a and a not in masters:
            masters.append(a)
        elif not a:
            missing.append(o.name)
    if graph.find_node_by_id(rid) is not None:
        drop_resource(graph, rid)
    files = AV.files_of_entry(entry)["files"]
    res = api.add_resource(
        graph, name=label, kind="3d_model", tier="distribution",
        packaging="file_set" if len(files) > 1 else None, files=files,
        residency="resident", resource_id=rid,
        primitives={"triangles": measured["triangles"]},
        data={k: v for k, v in {
            "use": list(prof["uses"]), "level": level, "purpose": prof["destination"],
            "profile": prof["id"], "represents": "container" if container is not None else "objects",
            "container": getattr(container, "group_node_id", "") or None,
            "estimate": {"download_bytes": diagnosis["after"]["download_bytes"],
                         "gpu_bytes": diagnosis["after"]["gpu_bytes"]}}.items() if v})
    if masters:
        declare_derivation(graph, res.node_id, masters, dtc_kind=BS.resolve_kind(BS.KIND_EXPORT),
                           technique=technique, parameters=params,
                           tool="EM Tools · Prepare for a use")
    if stamped.get("stamp"):
        try:
            from .. import version_stamp as VS
            VS.record(graph, res.node_id, stamped)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"stamp receipt: {exc}")
    if missing:
        warnings.append(f"{len(missing)} object(s) without a resource in the graph: "
                        + ", ".join(missing[:4]) + ("…" if len(missing) > 4 else ""))
    gid = str(getattr(graph, "graph_id", "") or "")
    AV.UNSAVED.setdefault(gid, []).append(label)
    out.update(resource_id=res.node_id, inputs=masters, missing=missing)
    return out


def drop_resource(graph, rid: str) -> List[str]:  # pragma: no cover — graph
    """A prepared version leaves the graph: its node and the export step that
    made it (when the step made nothing else). → the ids removed."""
    gone = []
    procs = [e.edge_source for e in graph.edges
             if e.edge_type == "dtc_had_output" and e.edge_target == rid]
    for p in procs:
        outs = [e for e in graph.edges if e.edge_type == "dtc_had_output" and e.edge_source == p]
        if len(outs) <= 1 and graph.find_node_by_id(p) is not None:
            graph.remove_node(p)
            gone.append(p)
    if graph.find_node_by_id(rid) is not None:
        graph.remove_node(rid)
        gone.append(rid)
    return gone


def nodes_for_files(graph, rows: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:  # pragma: no cover — graph
    """The resources of ``graph`` that name the files of each version on disk
    (by locator or by sha256). → ``{row name: [{id, name, version}]}``."""
    out: Dict[str, List[Dict[str, str]]] = {}
    if graph is None:
        return out
    from s3dgraphy.room_import.node import sha256_of_file
    by_digest: Dict[str, str] = {}
    by_base: Dict[str, str] = {}
    for r in rows:
        for f in r.get("files") or []:
            if os.path.isfile(f) and not f.endswith(".stamp.json"):
                by_base.setdefault(os.path.basename(f), r["name"])
        try:
            if os.path.isfile(r["entry"]):
                by_digest["sha256:" + str(sha256_of_file(r["entry"])).split(":")[-1]] = r["name"]
        except Exception:  # noqa: BLE001
            pass
    for n in graph.nodes:
        if getattr(n, "node_type", "") != "resource":
            continue
        d = getattr(n, "data", None) or {}
        hit = by_digest.get(str(d.get("checksum") or ""))
        url = str(d.get("url") or "")
        if not hit and url:
            hit = by_base.get(os.path.basename(url.replace("\\", "/")))
        if hit:
            out.setdefault(hit, []).append({"id": n.node_id, "name": str(n.name or n.node_id),
                                            "tier": str(d.get("tier") or "")})
    return out


# ── Blender: the dialog ─────────────────────────────────────────────────────

_CLASSES: tuple = ()


def _profile_items(self, context):  # pragma: no cover — bpy
    try:
        UP = use_profiles()
    except RuntimeError:
        return [("web", "Web", "")]
    return [(p["id"], p["label"], ", ".join(p["uses"])) for p in UP.profiles()]


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_PG_prepare_row(bpy.types.PropertyGroup):
        row_id: bpy.props.StringProperty()  # type: ignore
        kind: bpy.props.StringProperty()  # type: ignore
        problem: bpy.props.StringProperty()  # type: ignore
        action: bpy.props.StringProperty()  # type: ignore
        effect: bpy.props.StringProperty()  # type: ignore
        why: bpy.props.StringProperty()  # type: ignore
        available: bpy.props.BoolProperty(default=True)  # type: ignore
        checked: bpy.props.BoolProperty(name="", default=True)  # type: ignore

    def _fill(op, context, set_level=True):
        objs, model, _c = selection(context, op.scope)
        op.rows.clear()
        if not objs:
            return None
        d = diagnose_here(context, objs, op.profile)
        for r in d["improvements"]:
            row = op.rows.add()
            row.row_id, row.kind = r["id"], r["kind"]
            row.problem, row.action, row.why = r["problem"], r["action"], r.get("why", "")
            row.effect = effect_line(r["effect"])
            row.available, row.checked = bool(r.get("available", True)), bool(r.get("checked"))
        if not op.model:
            op.model = model
        if set_level:
            op.level = level_for(r["kind"] for r in d["improvements"]
                                 if r.get("checked") and r.get("available", True))
        return d

    def _on_profile(self, context):
        _fill(self, context)

    class EM_OT_prepare_diagnose(bpy.types.Operator):
        """Prepare the model for a use: what it costs for that use (triangles,
        draw calls, textures, download, GPU memory), what can be improved, and
        the version made with the improvements you tick — written in
        versions/ beside the .blend, stamped, registered in the graph. The
        .blend is not changed"""

        bl_idname = "em.prepare_diagnose"
        bl_label = "Prepare for a use: diagnosis…"
        bl_options = {"REGISTER"}

        profile: bpy.props.EnumProperty(  # type: ignore
            name="For", items=_profile_items, update=_on_profile,
            description="The profile of use (s3Dgraphy's table, the same as EMStudio's)")
        scope: bpy.props.EnumProperty(  # type: ignore
            name="What", default="CONTAINER", update=_on_profile,
            items=[("CONTAINER", "Its container", "The meshes of the active object's RM container"),
                   ("SELECTED", "The selection", "The selected meshes")])
        rows: bpy.props.CollectionProperty(type=EM_PG_prepare_row)  # type: ignore
        model: bpy.props.StringProperty(name="Model", default="", options={"SKIP_SAVE"})  # type: ignore
        level: bpy.props.StringProperty(name="Level", default="lod0", options={"SKIP_SAVE"})  # type: ignore
        replace: bpy.props.BoolProperty(  # type: ignore
            name="Replace the version there", default=False, options={"SKIP_SAVE"},
            description="A version with this name is already in versions/: write it again")
        checked_ids: bpy.props.StringProperty(  # type: ignore
            default="", options={"HIDDEN", "SKIP_SAVE"},
            description="Comma-separated row ids to apply (a script, EMStudio); empty: the ticks")
        folder: bpy.props.StringProperty(  # type: ignore
            default="", options={"HIDDEN", "SKIP_SAVE"},
            description="Where versions/ is (default: beside the .blend)")

        @classmethod
        def poll(cls, context):
            return context.active_object is not None or bool(context.selected_objects)

        def _folder(self):
            if self.folder:
                return self.folder
            path = bpy.data.filepath
            return use_profiles().versions_folder(path) if path else ""

        def invoke(self, context, event):
            try:
                use_profiles()
            except RuntimeError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            if context.active_object is not None and container_of(context.scene, context.active_object) is None:
                self.scope = "SELECTED"
            if _fill(self, context) is None:
                self.report({"ERROR"}, "select the model (or an object of its container)")
                return {"CANCELLED"}
            return context.window_manager.invoke_props_dialog(self, width=720,
                                                              title="Prepare for a use",
                                                              confirm_text="Apply the ticks")

        def draw(self, context):
            d = LAST.get("diagnosis")
            col = self.layout.column()
            row = col.row()
            row.prop(self, "profile")
            row.prop(self, "scope", expand=True)
            if not d:
                col.label(text="Nothing to diagnose", icon="INFO")
                return
            t, b = d["totals"], d["before"]
            box = col.box()
            box.label(text=f"{t['objects']} objects · {t['triangles']:,} triangles · "
                           f"{t['vertices']:,} vertices · {t['materials']} materials · "
                           f"{t['draw_calls']} draw calls · {t['textures']} textures "
                           f"(largest {t['texture_side_max']} px)", icon="MESH_DATA")
            for k, v in d["budget"].items():
                if v["limit"] is not None:
                    box.label(text=f"{k.replace('_', ' ')}: {v['value']:,} of {v['limit']:,}",
                              icon="CHECKMARK" if v["ok"] else "ERROR")
            if d["duplicates"]:
                n = sum(x["copies"] for x in d["duplicates"])
                box.label(text=f"{n} objects are copies of {len(d['duplicates'])} meshes "
                               f"(candidates for instances)", icon="DUPLICATE")
            if d["peaks"]:
                box.label(text="Over the budget per object: " + ", ".join(
                    f"{p['name']} {p['triangles']:,}" for p in d["peaks"][:4])
                    + ("…" if len(d["peaks"]) > 4 else ""), icon="ERROR")
            grid = col.box()
            grid.label(text="Improvements", icon="MODIFIER")
            checked = [r.row_id for r in self.rows if r.checked and r.available]
            for r in self.rows:
                line = grid.row(align=True)
                sub = line.row()
                sub.enabled = r.available
                sub.prop(r, "checked", text="")
                text = r.action if not r.problem else f"{r.problem} → {r.action}"
                line.label(text=text)
                line.label(text=r.effect if r.available else r.why)
            a = use_profiles().estimate(d, checked)
            col.label(text=f"Download {mb(b['download_bytes'])} → {mb(a['download_bytes'])} · "
                           f"GPU memory {mb(b['gpu_bytes'])} → {mb(a['gpu_bytes'])} · "
                           f"triangles {b['triangles']:,} → {a['triangles']:,} · "
                           f"draw calls {b['draw_calls']} → {a['draw_calls']}", icon="SORTTIME")
            row = col.row()
            row.prop(self, "model")
            row.prop(self, "level")
            folder = self._folder()
            if not folder:
                col.label(text="Save the .blend first: the versions go beside it", icon="ERROR")
                return
            try:
                ch = use_profiles().choices(d, checked)
                entry = target_name(folder, self.model or "model", self.level or "lod0",
                                    use_profiles().profile(d["profile"]), ch["packaging"])
            except Exception as exc:  # noqa: BLE001
                col.label(text=str(exc), icon="ERROR")
                return
            col.label(text=f"→ {os.path.relpath(entry, os.path.dirname(folder))}", icon="FILE_FOLDER")
            if target_files(entry):
                col.prop(self, "replace", text="Replace the version there (it is already in versions/)")

        def execute(self, context):
            try:
                use_profiles()
            except RuntimeError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            objs, model, cont = selection(context, self.scope)
            if not objs:
                self.report({"ERROR"}, "select the model (or an object of its container)")
                return {"CANCELLED"}
            if not len(self.rows):
                _fill(self, context, set_level=False)
            d = diagnose_here(context, objs, self.profile)
            ids = ([x for x in self.checked_ids.split(",") if x] if self.checked_ids
                   else [r.row_id for r in self.rows if r.checked and r.available])
            folder = self._folder()
            if not folder:
                self.report({"ERROR"}, "save the .blend first: the versions go beside it")
                return {"CANCELLED"}
            from . import asset_versions as AV
            graph = None
            try:
                from ..functions import is_graph_available
                ok, g = is_graph_available(context)
                graph = g if ok else None
            except Exception:  # noqa: BLE001
                graph = None
            t0 = time.time()
            try:
                out = apply(context, objs, d, ids, model=self.model or model,
                            level=self.level or "lod0", folder=folder, replace=self.replace,
                            container=cont, graph=graph,
                            say=lambda s: self.report({"INFO"}, s))
            except FileExistsError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            except Exception as exc:  # noqa: BLE001 — the reason is the user's
                import traceback
                traceback.print_exc()
                self.report({"ERROR"}, f"could not prepare the version: {exc}")
                return {"CANCELLED"}
            LAST["applied"] = dict(out, seconds=round(time.time() - t0, 1), rows=ids)
            for w in out["warnings"]:
                self.report({"WARNING"}, w)
            m = out["measured"]
            reg = out.get("registered") or {}
            self.report({"INFO"}, f"{os.path.basename(out['entry'])}: {m['triangles']:,} triangles "
                                  f"({m['triangles_stored']:,} stored), {mb(out['bytes'])}, "
                                  f"{out['instanced']} instance(s), {out['decimated']} decimated, "
                                  f"{out['resized']} texture(s) reduced · stamp {reg.get('stamp')}"
                                  + (" · in the graph: save it" if reg.get("resource_id") else ""))
            for area in context.screen.areas if context.screen else []:
                area.tag_redraw()
            return {"FINISHED"}

    return (EM_PG_prepare_row, EM_OT_prepare_diagnose)


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
