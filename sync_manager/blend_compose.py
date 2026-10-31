"""MICRO-BLEND-OFFICINA-2 · a working .blend composed for a profile (point 2).

The plan is s3Dgraphy's (``resources.blend_room.compose_plan`` on the
inventory of a .blend: link or append, only what the profile needs or
everything, each object from the FILE that holds it — the last library of its
chain —, or a version's file imported). :func:`compose` carries it out in a
Blender: a new, empty file, one collection per source, saved with RELATIVE
paths. It changes the session it runs in (it starts from an empty file), so:

* EMStudio's runner calls it in its headless Blender (op ``compose``);
* the operator in Blender (``em.compose_working_blend``) runs it in a
  SEPARATE background Blender (this file as a script: no add-on needed), so
  the open .blend is never touched; the composed file is opened only if asked.

The source .blend is read as SAVED (the rule of round 1): with unsaved
changes the operator says so.

MICRO-BLEND-OFFICINA-3 · «Compose a .blend from the graph…»
(``em.compose_from_graph``): NO .blend to start from — the open study (the
active graph's em.json), a WORKING profile (modelling, offline rendering, 3D
printing, archive; the publication ones go to «Consolidate for…»), the
containers / epochs chosen, link or append. The plan is s3Dgraphy's
(``resources.graph_compose.compose_from_graph``): for each model the version
the profile's uses pick (the master when none), from the DISK (a file
imported; a ``blend://`` master linked or appended) or from the ROOM (fetched
by sha256 into ``<project>/em_cache/files/<hh>/<hex><ext>`` IN THE OPEN
SESSION — it has the room's token — before the background Blender runs).
:func:`compose_graph` carries it out in a separate background Blender: one
object per model, named as the model, its meshes joined and placed as the
file places them; a container's tileset enters as the LIGHT SET of the detail
on request (``blend_detail``); every object carries the graph's TAGS
(:func:`write_tags`, ``graph_compose.graph_tags``; ``EM_ep_belong_ob`` as EM
Tools writes it, the add-on's collection of ``{epoch}``).
"""

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional


def _bpy():  # pragma: no cover — bpy
    import bpy
    return bpy


def free_path(path: str) -> str:
    """``path``, or ``<stem>-2.blend``, ``-3``… — a composed file is never
    written over another."""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f"{stem}-{n}{ext}"):
        n += 1
    return f"{stem}-{n}{ext}"


def default_out(blend: str, profile: str) -> str:
    stem = os.path.splitext(os.path.basename(blend))[0]
    return free_path(os.path.join(os.path.dirname(blend), f"{stem}__{profile}.blend"))


def _import_file(path: str) -> List[Any]:  # pragma: no cover — bpy
    bpy = _bpy()
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise RuntimeError(f"cannot import {path}")
    return [o for o in bpy.data.objects if o not in before]


def compose(plan: Dict[str, Any], out_path: str, *, save: bool = True) -> Dict[str, Any]:  # pragma: no cover
    """Carry out a ``compose_plan`` into a NEW .blend at ``out_path`` (never
    over an existing file). → ``{ok, path, objects, libraries, sources,
    missing, seconds}``."""
    bpy = _bpy()
    t0 = time.time()
    out_path = free_path(os.path.abspath(out_path))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.wm.read_homefile(use_empty=True)
    # saved first, empty: so the libraries are loaded with paths relative to it
    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    scene = bpy.context.scene
    missing: List[str] = []
    done: List[Dict[str, Any]] = []
    for src in plan.get("sources") or []:
        f = src["file"]
        how = src.get("how") or plan.get("how") or "link"
        col = bpy.data.collections.new(os.path.splitext(os.path.basename(f))[0] + f" ({how})")
        scene.collection.children.link(col)
        got: List[Any] = []
        if not os.path.exists(f):
            missing += list(src.get("objects") or [])
            continue
        if how == "import":
            got = _import_file(f)
            for o in got:
                for c in list(o.users_collection):
                    c.objects.unlink(o)
        else:
            want = list(src.get("objects") or [])
            with bpy.data.libraries.load(f, link=(how == "link"), relative=True) as (data_from, data_to):
                have = set(data_from.objects)
                data_to.objects = [n for n in want if n in have]
                missing += [n for n in want if n not in have]
            got = [o for o in data_to.objects if o is not None]
        for o in got:
            col.objects.link(o)
        done.append({"file": f, "how": how, "objects": [o.name for o in got]})
    libs = [{"name": lb.name, "filepath": lb.filepath} for lb in bpy.data.libraries]
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=out_path, relative_remap=True)
    return {"ok": True, "path": out_path, "profile": plan.get("profile"), "how": plan.get("how"),
            "objects": sum(len(d["objects"]) for d in done), "sources": done, "libraries": libs,
            "missing": missing, "seconds": round(time.time() - t0, 2)}


# ── MICRO-BLEND-OFFICINA-3 · compose from the graph ─────────────────────────

NEEDS_DEV80 = ("«Compose a .blend from the graph» needs s3dgraphy ≥ 1.6.0.dev80 (the next bundle of "
               "EM Tools): this s3dgraphy has no resources.graph_compose")

#: the graph's tags of a composed object (``graph_compose.TAG_KEYS``)
TAG_KEYS = ("em_rm_node_id", "em_belong_id", "EM_ep_belong_ob", "em_asset_id", "em_version_id",
            "em_resource_id", "em_level", "em_asset_sha256")

#: the working profiles (``graph_compose.WORK_PROFILES``), with their words
WORK_PROFILES = (("modelling", "Modelling", "a light model to model the proxies on (realtime, else "
                                            "the viewer's version)"),
                 ("render_offline", "Offline rendering", "the render version, else the master"),
                 ("print_3d", "3D printing", "the print version, else the master"),
                 ("archive", "Archive", "the master, always"))


def gc():
    """s3Dgraphy's ``resources.graph_compose`` (≥ 1.6.0.dev80)."""
    try:
        from s3dgraphy.resources import graph_compose
        return graph_compose
    except ImportError as exc:
        raise RuntimeError(NEEDS_DEV80) from exc


def sha_hex(checksum: Any) -> str:
    s = str(checksum or "").strip().lower()
    s = s.split(":", 1)[1] if ":" in s else s
    return s if len(s) == 64 and all(c in "0123456789abcdef" for c in s) else ""


def _file_sha(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetch_files(fetch: List[Dict[str, Any]], get) -> Dict[str, Any]:
    """The files of a plan that come from the ROOM: ``[{sha256, to}]``, each
    asked by its sha256 (``get("sha256:<hex>") → (bytes, media)``, the room
    client's ``get_asset``, which checks the digest) and written at ``to``
    (the project's ``em_cache/files/…``). A file already there with the same
    sha256 is not asked again. → ``{fetched, kept, failed: [lines]}``."""
    fetched = kept = 0
    failed: List[str] = []
    seen = set()
    for f in fetch or []:
        to, hexd = f.get("to") or "", sha_hex(f.get("sha256"))
        if not to or to in seen:
            continue
        seen.add(to)
        if not hexd:
            failed.append(f"{os.path.basename(to)}: no sha256")
            continue
        if os.path.isfile(to) and _file_sha(to) == hexd:
            kept += 1
            continue
        try:
            data, _media = get(f"sha256:{hexd}")
        except Exception as exc:  # noqa: BLE001 — the room's sentence is the reason
            failed.append(f"{os.path.basename(to)}: {exc}")
            continue
        import hashlib
        if hashlib.sha256(data).hexdigest() != hexd:
            failed.append(f"{os.path.basename(to)}: the bytes are not the graph's")
            continue
        os.makedirs(os.path.dirname(to), exist_ok=True)
        tmp = to + ".part"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, to)
        fetched += 1
    return {"fetched": fetched, "kept": kept, "failed": failed}


def graph_out(em_json: str, profile: str) -> str:
    """Where a .blend composed from the graph goes: beside the em.json,
    ``<study>__<profile>.blend`` (never over a file)."""
    base = os.path.basename(em_json or "study")
    for ext in (".em.json", ".json", ".graphml"):
        if base.lower().endswith(ext):
            base = base[: -len(ext)]
            break
    return free_path(os.path.join(os.path.dirname(em_json) or ".", f"{base}__{profile}.blend"))


def decorate_plan(graph, plan: Dict[str, Any], *, em_folder: str, project_folder: str,
                  em_json: str = "") -> Dict[str, Any]:
    """What the background Blender needs beside s3Dgraphy's plan: each item's
    container NAME (one collection per container) and, for a tileset, the
    document its detail's recipe cites (``graph_compose.document_of_resource``)."""
    G = gc()
    names: Dict[str, str] = {}
    for it in plan.get("items") or []:
        cid = it.get("container") or ""
        if cid and cid not in names:
            n = graph.find_node_by_id(cid)
            names[cid] = str(getattr(n, "name", "") or cid)
        it["container_name"] = names.get(cid, "") if cid else ""
        if it.get("kind") == "tileset":
            rid = (it.get("entry") or {}).get("id") or ""
            it["detail"] = {"document": G.document_of_resource(graph, rid) or "", "resource": rid}
    plan["em_folder"] = em_folder
    plan["project_folder"] = project_folder
    plan["em_json"] = em_json
    return plan


def ensure_epoch_rna():  # pragma: no cover — bpy
    """``Object.EM_ep_belong_ob`` as EM Tools registers it (a collection of
    ``{epoch}``): in a background Blender without the add-on the same
    definition is registered here, so the composed file carries the epochs
    where EM Tools reads them (Blender stores them by name, the definition only
    reads them)."""
    bpy = _bpy()
    if "EM_ep_belong_ob" in bpy.types.Object.bl_rna.properties:
        return
    from bpy.props import CollectionProperty, StringProperty

    class EM_epochs_belonging_ob(bpy.types.PropertyGroup):
        epoch: StringProperty(name="Epoch", default="Untitled")  # type: ignore

    bpy.utils.register_class(EM_epochs_belonging_ob)
    bpy.types.Object.EM_ep_belong_ob = CollectionProperty(type=EM_epochs_belonging_ob)


def write_tags(obj, tags: Dict[str, Any]) -> List[str]:  # pragma: no cover — bpy
    """The graph's tags on ``obj``: the ``em_*`` ID properties (an empty one
    is removed: a master has no ``em_version_id``) and the epochs in the
    add-on's ``EM_ep_belong_ob``. → the keys written."""
    out = []
    for k in TAG_KEYS:
        if k == "EM_ep_belong_ob":
            continue
        v = tags.get(k)
        if v:
            obj[k] = str(v)
            out.append(k)
        elif k in obj.keys():
            del obj[k]
    eps = getattr(obj, "EM_ep_belong_ob", None)
    names = [str(n) for n in (tags.get("EM_ep_belong_ob") or []) if n]
    if eps is not None:
        eps.clear()
        for n in names:
            eps.add().epoch = n
        if names:
            out.append("EM_ep_belong_ob")
    return out


def import_joined(path: str, name: str):  # pragma: no cover — bpy
    """A file imported as ONE mesh object called ``name``: its meshes joined,
    placed as the file places them (the transforms baked into the mesh, the
    object at the origin), the importer's empties removed. → the object
    (linked to no collection)."""
    bpy = _bpy()
    from mathutils import Matrix
    low = path.lower()
    before = set(bpy.data.objects)
    if low.endswith(".obj"):
        # as «Restore from the master» reads a master OBJ (round 1)
        bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z")
        new = [o for o in bpy.data.objects if o not in before]
    else:
        new = _import_file(path)
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        for o in new:
            bpy.data.objects.remove(o, do_unlink=True)
        raise RuntimeError(f"no mesh in {os.path.basename(path)}")
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    if len(meshes) > 1:
        with bpy.context.temp_override(selected_editable_objects=meshes, active_object=meshes[0],
                                       selected_objects=meshes, object=meshes[0]):
            bpy.ops.object.join()
    obj = meshes[0]
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    for o in new:
        if o is not obj and o.name in bpy.data.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    obj.name = name
    obj.data.name = name
    return obj


def load_block(path: str, block: str, block_type: str, *, link: bool):  # pragma: no cover — bpy
    """A datablock of a .blend (a ``blend://`` master): its MESH, linked or
    appended (an Object block gives its mesh). → the mesh, or None."""
    bpy = _bpy()
    kind = (block_type or "Mesh").lower()
    with bpy.data.libraries.load(path, link=link, relative=True) as (src, dst):
        if kind.startswith("mesh"):
            dst.meshes = [block] if block in src.meshes else []
        else:
            dst.objects = [block] if block in src.objects else []
    if kind.startswith("mesh"):
        got = [m for m in (dst.meshes or []) if m is not None]
        return got[0] if got else None
    got = [o for o in (dst.objects or []) if o is not None]
    return got[0].data if got else None


def _graph_collection(scene, name: str):  # pragma: no cover — bpy
    bpy = _bpy()
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        scene.collection.children.link(col)
    return col


def compose_graph(plan: Dict[str, Any], out_path: str, *, save: bool = True) -> Dict[str, Any]:  # pragma: no cover
    """Carry out ``graph_compose.compose_from_graph``'s plan (decorated by
    :func:`decorate_plan`) into a NEW .blend at ``out_path``. Files must be
    on this disk already (the room's are fetched before, in the session that
    has the room). → ``{ok, path, objects, tagged, tiles, missing,
    libraries, seconds}``."""
    bpy = _bpy()
    t0 = time.time()
    out_path = free_path(os.path.abspath(out_path))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    ensure_epoch_rna()
    scene = bpy.context.scene
    how = plan.get("how") or "link"
    made: List[str] = []
    missing: List[str] = [f"{m.get('name')}: {m.get('say_it')}" for m in plan.get("missing") or []]
    tiles = 0
    tagged = 0
    for it in plan.get("items") or []:
        src = it.get("source") or {}
        f = src.get("file") or ""
        try:
            if it.get("kind") == "tileset":
                tiles += _light_set(plan, it, f)
                continue
            if not f or not os.path.exists(f):
                raise RuntimeError(f"not on this disk ({os.path.basename(f) or 'no file'})")
            col = _graph_collection(scene, it.get("container_name") or "(no container)")
            if src.get("how") in ("import", "fetch"):
                obj = import_joined(f, it.get("name") or it.get("model_id") or "model")
            elif src.get("how") in ("link", "append"):
                mesh = load_block(f, src.get("block") or "", src.get("block_type") or "Mesh",
                                  link=(src.get("how") == "link"))
                if mesh is None:
                    raise RuntimeError(f"{src.get('block')} is not in {os.path.basename(f)}")
                obj = bpy.data.objects.new(it.get("name") or "model", mesh)
            else:
                raise RuntimeError(src.get("say_it") or "nothing to bring")
            col.objects.link(obj)
            if write_tags(obj, it.get("tags") or {}):
                tagged += 1
            made.append(obj.name)
        except Exception as exc:  # noqa: BLE001 — one model never stops the others
            missing.append(f"{it.get('name')}: {exc}")
    libs = [{"name": lb.name, "filepath": lb.filepath} for lb in bpy.data.libraries]
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=out_path, relative_remap=True)
    return {"ok": True, "path": out_path, "profile": plan.get("profile"), "how": how,
            "objects": len(made), "names": made, "tagged": tagged, "tiles": tiles,
            "missing": missing, "libraries": libs, "seconds": round(time.time() - t0, 2)}


def _light_set(plan: Dict[str, Any], it: Dict[str, Any], path: str) -> int:  # pragma: no cover — bpy
    """A container's tileset: its LIGHT SET (the coarsest level) as the
    detail on request loads it — tiles in ``em_cache/local/detail/<key>/``,
    the scene's ``em_detail_state`` ready for «More detail here»."""
    bpy = _bpy()
    import importlib
    BD = sys.modules.get(__package__ + ".blend_detail") if __package__ else None
    if BD is None:  # run as a script (the background Blender): the file beside this one
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        BD = importlib.import_module("blend_detail")
    D = BD.dt()
    em = plan.get("em_folder") or os.path.dirname(path)
    tree, _rb = BD.open_tileset(path)
    cut = D.light_set(tree, None)
    root = tree["nodes"][tree["root"]]
    det = it.get("detail") or {}
    src = os.path.relpath(path, em).replace(os.sep, "/") if em else path
    r = D.recipe(document=det.get("document") or "", resource=det.get("resource") or "", source=src,
                 area=root["aabb"] or [0, 0, 0, 0, 0, 0], level=0)
    ctx = bpy.context
    BD.load_tiles(ctx, path, cut, D.cache_folder(em, r), recipe=r["key"], document=r["document"])
    st = BD.empty_state()
    st.update(kind="tileset", source=path, document=r["document"], resource=r["resource"], cut=cut,
              level=None, recipes=[r])
    ctx.scene[BD.STATE_PROP] = json.dumps(st)
    ctx.scene["em_detail_last_source"] = path
    return len(cut)


def graph_plan(context, profile: str, how: str = "link", *, containers=None, epochs=None, models=None,
               in_room: bool = False) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The plan of «Compose a .blend from the graph» for the ACTIVE graph:
    s3Dgraphy's ``compose_from_graph`` with the last «Check files» of this
    graph (``file_states.ULTIMI``: the states and paths of the resolver)."""
    G = gc()
    from ..functions import check_active_graph
    from .project_files import active_emjson
    from . import file_states
    ok, graph = check_active_graph(context, show_message=False)
    if not ok or graph is None:
        raise RuntimeError("no active graph: load an em.json first")
    em = active_emjson(context) or ""
    em_folder = os.path.dirname(em) if em else ""
    if not em_folder:
        raise RuntimeError("the active graph has no em.json on this computer")
    project = file_states.project_root(context) or os.path.dirname(em_folder)
    known = file_states.ULTIMI if file_states.ULTIMI.get("graph_id") == str(getattr(graph, "graph_id", "")) else {}
    plan = G.compose_from_graph(graph, profile, em_folder=em_folder, project_folder=project,
                                containers=containers or None, epochs=epochs or None, models=models,
                                how=how, resolved=known.get("results") or None, in_room=in_room)
    return decorate_plan(graph, plan, em_folder=em_folder, project_folder=project, em_json=em)


def plan_for(context, profile: str, how: str, only_needed: bool) -> Dict[str, Any]:  # pragma: no cover
    """The plan for the OPEN .blend (its inventory as saved)."""
    from .blend_officina import bf, inventory
    try:
        from s3dgraphy.resources import blend_room
    except ImportError as exc:
        from .blend_officina import NEEDS_DEV79
        raise RuntimeError(NEEDS_DEV79) from exc
    inv = inventory()
    bf()  # the same s3dgraphy says the inventory
    return blend_room.compose_plan(inv, profile, how=how, only_needed=only_needed)


def run_detached(plan: Dict[str, Any], out_path: str, *, wait: bool = True, timeout: float = 600,
                 mode: str = "blend") -> Dict[str, Any]:  # pragma: no cover — bpy
    """:func:`compose` (``mode`` ``blend``) or :func:`compose_graph`
    (``graph``) in a separate background Blender (the open session is never
    touched): this file run as a script, the plan in a JSON file. The
    session's ``sys.path`` travels (``PYTHONPATH``): the s3dgraphy EM Tools
    uses is the one the light set of a tileset needs there."""
    import subprocess
    import tempfile
    bpy = _bpy()
    tmp = tempfile.NamedTemporaryFile("w", suffix=".compose.json", delete=False)
    json.dump(plan, tmp)
    tmp.close()
    env = dict(os.environ)
    paths = [p for p in sys.path if p and os.path.isdir(p)]
    env["PYTHONPATH"] = os.pathsep.join(paths)
    cmd = [bpy.app.binary_path, "-b", "--factory-startup", "--python-use-system-env",
           "--python-exit-code", "1",
           "--python", os.path.abspath(__file__), "--", tmp.name, out_path, mode]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    for line in (p.stdout or "").splitlines():
        if line.startswith("EM-COMPOSE "):
            return json.loads(line[len("EM-COMPOSE "):])
    raise RuntimeError("the background Blender did not compose: " + (p.stderr or p.stdout or "")[-600:])


def _operator_classes():  # pragma: no cover — bpy
    bpy = _bpy()
    from bpy.props import BoolProperty, EnumProperty, StringProperty

    def _profiles(self, context):
        try:
            from s3dgraphy.resources import blend_room
            keys = list(blend_room.PROFILE_KINDS)
        except ImportError:
            keys = ["modelling"]
        return [(k, k.replace("_", " "), "") for k in keys]

    class EM_OT_compose_working_blend(bpy.types.Operator):
        """Compose a working .blend for a profile from this .blend (as saved): link or append,
        only what the profile needs or all, each object from the file that holds it"""
        bl_idname = "em.compose_working_blend"
        bl_label = "Compose a working .blend for…"
        profile: EnumProperty(name="Profile", items=_profiles)  # type: ignore
        how: EnumProperty(name="How", items=[("link", "Link", "linked: light, follows the sources"),
                                             ("append", "Append", "copied: on its own")],
                          default="link")  # type: ignore
        only_needed: BoolProperty(name="Only what the profile needs", default=True)  # type: ignore
        open_after: BoolProperty(name="Open it after", default=False)  # type: ignore
        filepath: StringProperty(name="Into", subtype="FILE_PATH", default="")  # type: ignore

        def invoke(self, context, event):
            if not bpy.data.filepath:
                self.report({"WARNING"}, "Save the .blend first")
                return {"CANCELLED"}
            return context.window_manager.invoke_props_dialog(self, width=480)

        def draw(self, context):
            col = self.layout.column()
            for p in ("profile", "how", "only_needed", "open_after", "filepath"):
                col.prop(self, p)
            if bpy.data.is_dirty:
                col.label(text="Unsaved changes: the composition reads the SAVED file", icon="ERROR")
            try:
                plan = plan_for(context, self.profile, self.how, self.only_needed)
                col.label(text=plan["say"], icon="INFO")
            except Exception as exc:  # noqa: BLE001
                col.label(text=str(exc), icon="ERROR")

        def execute(self, context):
            try:
                plan = plan_for(context, self.profile, self.how, self.only_needed)
                out = bpy.path.abspath(self.filepath) if self.filepath else default_out(bpy.data.filepath,
                                                                                        self.profile)
                got = run_detached(plan, out)
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            self.report({"INFO"}, f"Composed {got['objects']} object(s) into {os.path.basename(got['path'])}"
                        + (f", {len(got['missing'])} missing" if got.get("missing") else ""))
            if self.open_after:
                bpy.ops.wm.open_mainfile(filepath=got["path"])
            return {"FINISHED"}

    # ── MICRO-BLEND-OFFICINA-3 · «Compose a .blend from the graph…» ──────────

    class EM_PG_compose_scope(bpy.types.PropertyGroup):
        kind: StringProperty()  # type: ignore  # container | epoch
        node_id: StringProperty()  # type: ignore
        label: StringProperty()  # type: ignore
        tick: BoolProperty(name="", default=False)  # type: ignore

    def _in_room() -> bool:
        try:
            from . import room as room_cfg
            return bool((room_cfg.room() or {}).get("room_id"))
        except Exception:  # noqa: BLE001
            return False

    def _sources(self, context):
        out = [("disk", "This computer", "the files on this disk (import, link or append)")]
        if _in_room():
            out.append(("room", "The room", "what is not on this disk is fetched from the room's "
                                            "bucket by its sha256 into em_cache/files"))
        return out

    _PLAN_CACHE: Dict[str, Any] = {}

    class EM_OT_compose_from_graph(bpy.types.Operator):
        """Compose a working .blend from the open study (the em.json), with no .blend to start
        from: a working profile, the containers and epochs chosen, each model's version from this
        disk or from the room, every object with the graph's tags (in a separate Blender)"""
        bl_idname = "em.compose_from_graph"
        bl_label = "Compose a .blend from the graph…"
        profile: EnumProperty(name="Profile", items=list(WORK_PROFILES), default="modelling")  # type: ignore
        how: EnumProperty(name="A .blend master", items=[
            ("link", "Link", "linked: light, follows the source"),
            ("append", "Append", "copied: on its own")], default="link")  # type: ignore
        source: EnumProperty(name="From", items=_sources)  # type: ignore
        only_selected: BoolProperty(name="Only the models of the selected objects",
                                    default=False)  # type: ignore
        open_after: BoolProperty(name="Open it after", default=False)  # type: ignore
        filepath: StringProperty(name="Into", subtype="FILE_PATH", default="")  # type: ignore

        def _scope(self, context):
            rows = context.window_manager.em_compose_scope
            cont = [r.node_id for r in rows if r.kind == "container" and r.tick]
            eps = [r.node_id for r in rows if r.kind == "epoch" and r.tick]
            models = None
            if self.only_selected:
                models = sorted({str(o.get("em_rm_node_id")) for o in context.selected_objects
                                 if o.get("em_rm_node_id")} |
                                {f"{o.name}_model" for o in context.selected_objects})
            return cont, eps, models

        def _plan(self, context):
            cont, eps, models = self._scope(context)
            key = json.dumps([self.profile, self.how, self.source, cont, eps, models])
            if _PLAN_CACHE.get("key") != key:
                _PLAN_CACHE.clear()
                try:
                    _PLAN_CACHE.update(key=key, plan=graph_plan(
                        context, self.profile, self.how, containers=cont, epochs=eps, models=models,
                        in_room=(self.source == "room")), error="")
                except Exception as exc:  # noqa: BLE001
                    _PLAN_CACHE.update(key=key, plan=None, error=str(exc))
            return _PLAN_CACHE.get("plan"), _PLAN_CACHE.get("error")

        def invoke(self, context, event):
            try:
                gc()
                from ..functions import check_active_graph
                ok, graph = check_active_graph(context, show_message=False)
                if not ok or graph is None:
                    raise RuntimeError("no active graph: load an em.json first")
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            rows = context.window_manager.em_compose_scope
            rows.clear()
            hats = gc()._hats()
            for n in sorted(graph.nodes, key=lambda n: str(getattr(n, "name", "") or "")):
                nt = str(getattr(n, "node_type", "") or "")
                kind = "container" if nt in hats["container"] else "epoch" if "epoch" in nt.lower() else ""
                if kind:
                    r = rows.add()
                    r.kind, r.node_id, r.label = kind, n.node_id, str(getattr(n, "name", "") or n.node_id)
            _PLAN_CACHE.clear()
            return context.window_manager.invoke_props_dialog(self, width=560)

        def draw(self, context):
            col = self.layout.column()
            for p in ("profile", "source", "how", "only_selected", "open_after", "filepath"):
                col.prop(self, p)
            rows = context.window_manager.em_compose_scope
            split = col.split(factor=0.5)
            for kind, title, side in (("container", "Containers (none: all)", split.column(align=True)),
                                      ("epoch", "Epochs (none: all)", split.column(align=True))):
                side.label(text=title)
                for r in rows:
                    if r.kind == kind:
                        side.prop(r, "tick", text=r.label)
            plan, error = self._plan(context)
            if error:
                col.label(text=error, icon="ERROR")
            elif plan is not None:
                col.label(text=plan.get("say_it") or "", icon="INFO" if plan.get("ok") else "ERROR")
                for m in (plan.get("missing") or [])[:4]:
                    col.label(text=f"{m.get('name')}: {m.get('say_it')}", icon="BLANK1")
                tiles = [i for i in plan.get("items") or [] if i.get("kind") == "tileset"]
                for i in tiles:
                    col.label(text=f"{i['name']}: tileset, its light set (detail on request)",
                              icon="MOD_MULTIRES")

        def execute(self, context):
            _PLAN_CACHE.clear()
            plan, error = self._plan(context)
            if error or plan is None:
                self.report({"ERROR"}, error or "no plan")
                return {"CANCELLED"}
            if not plan.get("ok"):
                self.report({"WARNING"}, plan.get("say_it") or "not a working profile")
                return {"CANCELLED"}
            if plan.get("fetch"):
                from . import room as room_cfg
                got = fetch_files(plan["fetch"], room_cfg.get_asset)
                for line in got["failed"][:6]:
                    self.report({"WARNING"}, line)
                self.report({"INFO"}, f"From the room: {got['fetched']} fetched, {got['kept']} already here")
            out = bpy.path.abspath(self.filepath) if self.filepath else graph_out(plan.get("em_json") or "",
                                                                                  self.profile)
            try:
                got = run_detached(plan, out, mode="graph")
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            for line in (got.get("missing") or [])[:6]:
                self.report({"WARNING"}, line)
            self.report({"INFO"}, f"Composed {got['objects']} object(s) ({got.get('tiles', 0)} tiles) into "
                                  f"{os.path.basename(got['path'])} in {got.get('seconds')} s")
            if self.open_after:
                bpy.ops.wm.open_mainfile(filepath=got["path"])
            return {"FINISHED"}

    return (EM_OT_compose_working_blend, EM_PG_compose_scope, EM_OT_compose_from_graph)


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    bpy = _bpy()
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    scope = next(c for c in _CLASSES if c.__name__ == "EM_PG_compose_scope")
    bpy.types.WindowManager.em_compose_scope = bpy.props.CollectionProperty(type=scope)


def unregister():  # pragma: no cover — bpy
    bpy = _bpy()
    if hasattr(bpy.types.WindowManager, "em_compose_scope"):
        del bpy.types.WindowManager.em_compose_scope
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":  # pragma: no cover — run by run_detached
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    with open(argv[0], "r", encoding="utf-8") as fh:
        _plan = json.load(fh)
    _mode = argv[2] if len(argv) > 2 else "blend"
    _got = compose_graph(_plan, argv[1]) if _mode == "graph" else compose(_plan, argv[1])
    sys.stdout.write("EM-COMPOSE " + json.dumps(_got) + "\n")
    sys.stdout.flush()
