"""MICRO-BLEND-OFFICINA-1 · Blender as the workshop, EMStudio as the director
(E.D.'s decision of 30 Oct 2026).

The .blend is a workshop and a cache; the STAMPED files outside it are what
holds. This module is EM Tools' half of it:

* **the .blend as a folder** — :func:`collect` dumps what Blender sees
  (objects, collections, images, libraries — the linked ones followed
  recursively) as plain data; s3Dgraphy's ``resources.blend_folder.normalize``
  turns it into the inventory EMStudio's Archive shows. The EMStudio runner
  calls :func:`collect` in a headless Blender, the panel here calls it in the
  open one: ONE reading.
* **«Check against the graph»** — the same ``blend_folder.check`` EMStudio
  calls, here on the active graph; a list with the states (``✔ ↑ ↓ ✗ ○``), an
  action and a tick per row, and «Apply».
* **the gestures of who models** — «Register as a version…» / «as a new
  resource» (export, stamp with the step «manual work in Blender», register
  with the datamodel's edges, url relative to the em.json), «Restore from
  the master» (reimport a deleted or changed object from its stamped file),
  «Export as master» (glTF + external textures for SB, OBJ + textures for RB;
  packed textures written out) into ``<SB|RB>/<Container>/master/``.
* **the session's presence** (point 1, measured on Blender 5.2): Blender
  leaves no lock and holds no descriptor on a .blend it has open, and saves
  over a file changed under it without a word. So a Blender with its
  interface WRITES its presence (``~/.stratigraph/blender-sessions/``: pid,
  host, unsaved changes, time) every few seconds; a headless job reads it and
  follows ``blend_folder.save_rule``: never two sessions saving one file.
* **the status row of «Asset versions»** — the container's master stamped
  or not, its versions, the alignment, and «Prepare in EMStudio» (the
  optimisation window left EM Tools for EMStudio; its operators stay, headless).

The pure decisions are s3Dgraphy's (``blend_folder``); the few here
(:func:`status_line`, :func:`prepare_link`, :func:`session_record`) are
measured by ``tests/test_blend_officina.py``.
"""

# NOT `from __future__ import annotations`: the operators are built inside a
# function with `bpy` imported lazily (the same note as asset_versions).
import hashlib
import json
import os
import platform
import time
from typing import Any, Dict, List, Optional

#: the step a version made by hand in Blender is stamped with
MANUAL_STEP = "manual work in Blender"
MANUAL_TECHNIQUE = "manual_editing_blender"
#: how often the open Blender says it is there (seconds)
PRESENCE_EVERY_S = 10.0
#: the last check (session state, for the dialog and the panel)
LAST: Dict[str, Any] = {}

NEEDS_S3DGRAPHY = ("this Blender's s3dgraphy has no blend_folder (the .blend as a folder, "
                   "«Check against the graph»): it comes with s3dgraphy 1.6.0.dev77 — "
                   "the next bundle of EM Tools")


def bf():
    """s3Dgraphy's ``resources.blend_folder`` (the pure half)."""
    try:
        from s3dgraphy.resources import blend_folder
        return blend_folder
    except ImportError as exc:
        raise RuntimeError(NEEDS_S3DGRAPHY) from exc


# ── pure ─────────────────────────────────────────────────────────────────────

# The presence of a session: s3Dgraphy's (``blend_folder.session_file`` …);
# the copy below is used only while this Blender's bundled s3dgraphy predates
# it, and ``tests/test_blend_officina.py`` checks the two name the same file.

def sessions_dir(home: Optional[str] = None) -> str:
    try:
        return bf().sessions_dir(home)
    except RuntimeError:
        return os.path.join(home or os.path.expanduser("~"), ".stratigraph", "blender-sessions")


def session_file(blend: str, home: Optional[str] = None) -> str:
    try:
        return bf().session_file(blend, home)
    except RuntimeError:
        real = os.path.realpath(blend) if blend else ""
        return os.path.join(sessions_dir(home), hashlib.sha1(real.encode("utf-8")).hexdigest()[:16] + ".json")


def session_record(blend: str, *, dirty: bool, pid: int, host: str, now: float,
                   version: str = "", sidecar_port: int = 0) -> Dict[str, Any]:
    try:
        return bf().session_record(blend, dirty=dirty, pid=pid, host=host, now=now, version=version,
                                   sidecar_port=sidecar_port)
    except RuntimeError:
        return {"blend": os.path.realpath(blend) if blend else "", "dirty": bool(dirty), "pid": int(pid),
                "host": host, "at": now, "blender": version, "sidecar_port": int(sidecar_port or 0)}


def read_session(blend: str, home: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        with open(session_file(blend, home), "r", encoding="utf-8") as fh:
            got = json.load(fh)
        return got if isinstance(got, dict) else None
    except (OSError, ValueError):
        return None


def status_line(*, master_stamped: Optional[bool], versions: int,
                counts: Optional[Dict[str, int]] = None) -> str:
    """The status row of a container in «Asset versions»: the master, the
    versions, the alignment (the last check)."""
    master = {True: "master stamped", False: "master not stamped", None: "no master"}[master_stamped]
    parts = [master, f"{versions} version" + ("" if versions == 1 else "s")]
    if counts:
        signs = {"aligned": "✔", "changed_here": "↑", "newer_outside": "↓", "missing": "✗", "only_here": "○"}
        said = " ".join(f"{signs[k]}{counts[k]}" for k in signs if counts.get(k))
        if said:
            parts.append(said)
    return " · ".join(parts)


def prepare_link(*, sidecar_clients: int, room: Dict[str, Optional[str]], container: str,
                 em_json: str = "", blend: str = "") -> Dict[str, Any]:
    """How «Prepare in EMStudio» reaches EMStudio on a container: the sidecar
    (an ``open`` envelope, EMStudio connected), else the room's link
    (``stratigraph://open?…&node=<container>``), else it says how."""
    if sidecar_clients > 0:
        return {"way": "sidecar", "envelope": {"type": "open", "what": "prepare",
                                               "container": container, "em_json": em_json, "blend": blend}}
    if room.get("server") and room.get("room"):
        from urllib.parse import urlencode
        q = {"server": room["server"], "room": room["room"], "node": container, "tab": "prepare"}
        return {"way": "link", "url": "stratigraph://open?" + urlencode(q)}
    return {"way": None, "say": ("EMStudio is not connected: turn the Sidecar on (EM ▸ Where you work ▸ "
                                 "Work with EMStudio) and connect EMStudio to it, then press again; "
                                 "or open the em.json in EMStudio › Prepare.")}


# ── Blender: the .blend as a folder ──────────────────────────────────────────

def _bpy():  # pragma: no cover — bpy
    import bpy  # type: ignore
    return bpy


def _plain(v: Any) -> Any:  # pragma: no cover — bpy
    """An ID property as plain data (groups → dicts, arrays → lists)."""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if hasattr(v, "to_dict"):
        return {k: _plain(x) for k, x in v.to_dict().items()}
    if hasattr(v, "to_list"):
        return [_plain(x) for x in v.to_list()]
    if hasattr(v, "keys") and hasattr(v, "__getitem__"):
        return {k: _plain(v[k]) for k in v.keys()}
    try:
        return [_plain(x) for x in v]
    except TypeError:
        return str(v)


def _props(obj) -> Dict[str, Any]:  # pragma: no cover — bpy
    out: Dict[str, Any] = {}
    names = ("em_rm_node_id", "EM_ep_belong_ob", "em_belong_id", "em_doc_node_id", "USV",
             "em_asset_id", "em_version_id", "em_level", "em_asset_sha256", "em_resource_id",
             "em_mesh_fp", "em_only_here", "tileset_path")
    for k in obj.keys():
        if k in names or k.startswith("em_alternative_"):
            out[k] = _plain(obj[k])
    # Blender 5: a property registered by an add-on is not an ID property
    # any more — the epochs are read through the add-on's RNA when it is here
    eps = getattr(obj, "EM_ep_belong_ob", None)
    if eps is not None and "EM_ep_belong_ob" not in out:
        try:
            got = [{"epoch": e.epoch} for e in eps]
            if got:
                out["EM_ep_belong_ob"] = got
        except Exception:  # noqa: BLE001
            pass
    data = getattr(obj, "data", None)
    if data is not None:
        for k in ("em_asset_id", "em_version_id", "em_level", "em_asset_sha256"):
            if k not in out and k in data.keys():
                out[k] = _plain(data[k])
    return out


def collect(*, fingerprints: bool = True) -> Dict[str, Any]:  # pragma: no cover — bpy
    """The open .blend as plain data (``blend_folder.normalize``'s input).
    The fingerprint of a mesh is measured only where one was recorded (it is
    what ↑ compares), so a 200-object .blend is read in about a second."""
    bpy = _bpy()
    from .scene_sync import mesh_fingerprint
    t0 = time.time()
    path = bpy.data.filepath
    libs = []
    for lb in bpy.data.libraries:
        try:
            ab = bpy.path.abspath(lb.filepath, library=lb.parent) if lb.parent else bpy.path.abspath(lb.filepath)
        except TypeError:
            ab = bpy.path.abspath(lb.filepath)
        ab = os.path.normpath(ab)
        libs.append({"name": lb.name, "filepath": lb.filepath, "abspath": ab,
                     "exists": os.path.isfile(ab) and not getattr(lb, "is_missing", False),
                     "parent": lb.parent.name if lb.parent else None})
    objects = []
    for o in bpy.data.objects:
        data = o.data
        tris = verts = 0
        mesh = ""
        if o.type == "MESH" and data is not None:
            mesh = data.name
            try:
                tris = max(0, len(data.loops) - 2 * len(data.polygons))
                verts = len(data.vertices)
            except Exception:  # noqa: BLE001
                pass
        props = _props(o)
        fp = ""
        if fingerprints and props.get("em_mesh_fp") and o.type == "MESH":
            try:
                fp = mesh_fingerprint(o)
            except Exception:  # noqa: BLE001
                fp = ""
        objects.append({
            "name": o.name, "type": o.type, "collections": [c.name for c in o.users_collection],
            "props": props, "triangles": tris, "vertices": verts, "mesh": mesh, "fingerprint": fp,
            "library": o.library.name if o.library else None,
            "data_library": data.library.name if (data is not None and getattr(data, "library", None)) else None,
        })
    cols = [{"name": c.name, "children": [ch.name for ch in c.children],
             "objects": [ob.name for ob in c.objects], "library": c.library.name if c.library else None}
            for c in bpy.data.collections]
    images = []
    for im in bpy.data.images:
        ab = ""
        if im.filepath:
            try:
                ab = os.path.normpath(bpy.path.abspath(im.filepath, library=im.library))
            except Exception:  # noqa: BLE001
                ab = ""
        images.append({"name": im.name, "filepath": im.filepath, "abspath": ab, "source": im.source,
                       "packed": im.packed_file is not None, "exists": bool(ab) and os.path.isfile(ab),
                       "library": im.library.name if im.library else None})
    scene = bpy.context.scene
    return {"blend": path, "mtime": os.path.getmtime(path) if path and os.path.isfile(path) else None,
            "dirty": bool(bpy.data.is_dirty), "blender": bpy.app.version_string,
            "libraries": libs, "objects": objects, "collections": cols, "images": images,
            "scene_collection": [c.name for c in scene.collection.children],
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "seconds": round(time.time() - t0, 2)}


def inventory() -> Dict[str, Any]:  # pragma: no cover — bpy
    return bf().normalize(collect())


def active_graph_doc(context):  # pragma: no cover — bpy
    """(graph, em.json dict of its graph, the em.json's folder) or (None, None, "")."""
    from ..functions import check_active_graph
    ok, graph = check_active_graph(context, show_message=False)
    if not ok or graph is None:
        return None, None, ""
    from s3dgraphy import api
    doc = api.graph_to_emjson(graph)
    from .project_files import active_emjson
    em = active_emjson(context)
    return graph, doc, os.path.dirname(em) if em else ""


def disk_files(doc: Dict[str, Any], em_folder: str) -> Dict[str, Dict[str, Any]]:  # pragma: no cover
    return bf().disk_files(doc, em_folder)


def check_here(context, *, source: str = "disk") -> Dict[str, Any]:  # pragma: no cover — bpy
    """«Check against the graph» on the open .blend and the active graph."""
    graph, doc, em_folder = active_graph_doc(context)
    if doc is None:
        raise RuntimeError("no active graph: load an em.json first")
    inv = inventory()
    files = disk_files(doc, em_folder) if source == "disk" else {}
    offline, as_of = False, ""
    if source == "room":
        try:
            from . import file_states
            known = getattr(file_states, "LAST", None) or {}
            files = {r.get("id"): {"sha256": r.get("sha256"), "exists": r.get("state") != "missing"}
                     for r in (known.get("results") or []) if r.get("id")}
            offline = not bool(known.get("online", True))
            as_of = str(known.get("at") or "")
        except Exception:  # noqa: BLE001
            offline = True
    res = bf().check(inv, doc, files=files, source=source, offline=offline, as_of=as_of, em_folder=em_folder)
    LAST.clear()
    LAST.update({"result": res, "inventory_counts": inv["counts"], "at": time.strftime("%H:%M")})
    return res


# ── Blender: the presence of the open session (point 1) ─────────────────────

_PRESENCE: Dict[str, Any] = {"path": "", "dirty": None, "written": 0.0}


def _sidecar_port() -> int:  # pragma: no cover — bpy
    """The sidecar's port when it runs (EMStudio sends the changes there)."""
    try:
        from . import operators as sync
        if not sync.is_running():
            return 0
        return int(getattr(sync._server, "port", 0) or 0)
    except Exception:  # noqa: BLE001
        return 0


def write_presence() -> None:  # pragma: no cover — bpy
    bpy = _bpy()
    path = bpy.data.filepath
    if bpy.app.background:
        return
    if _PRESENCE["path"] and _PRESENCE["path"] != path:
        drop_presence(_PRESENCE["path"])
    if not path:
        _PRESENCE.update(path="", dirty=None)
        return
    dirty = bool(bpy.data.is_dirty)
    now = time.time()
    # written when something changed, and at least every 30 s (the reader
    # takes a presence older than 90 s for a Blender that ended)
    if _PRESENCE["path"] == path and _PRESENCE["dirty"] == dirty and now - _PRESENCE["written"] < 30:
        return
    rec = session_record(path, dirty=dirty, pid=os.getpid(), host=platform.node(), now=now,
                         version=bpy.app.version_string, sidecar_port=_sidecar_port())
    f = session_file(path)
    try:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        tmp = f + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        os.replace(tmp, f)
        _PRESENCE.update(path=path, dirty=dirty, written=now)
    except OSError as exc:
        print(f"[officina] presence not written: {exc}")


def drop_presence(path: str) -> None:
    f = session_file(path)
    try:
        got = read_session(path)
        if got and int(got.get("pid") or 0) == os.getpid():
            os.remove(f)
    except OSError:
        pass


def _presence_timer():  # pragma: no cover — bpy
    try:
        write_presence()
    except Exception as exc:  # noqa: BLE001 — a presence never breaks a session
        print(f"[officina] presence: {exc}")
    return PRESENCE_EVERY_S


def _on_load_pre(*_a):  # pragma: no cover — bpy
    if _PRESENCE["path"]:
        drop_presence(_PRESENCE["path"])
        _PRESENCE.update(path="", dirty=None, written=0.0)


def _on_after(*_a):  # pragma: no cover — bpy
    _PRESENCE["written"] = 0.0
    try:
        write_presence()
    except Exception:  # noqa: BLE001
        pass


def _at_exit():
    if _PRESENCE.get("path"):
        drop_presence(_PRESENCE["path"])


# ── Blender: the gestures of who models ─────────────────────────────────────

def project_root_for(context, em_json: str) -> str:  # pragma: no cover — bpy
    bpy = _bpy()
    root = ""
    try:
        from s3dgraphy.project_tree import find_project_root
        root = find_project_root(em_json or bpy.data.filepath) or ""
    except Exception:  # noqa: BLE001
        root = ""
    if not root and bpy.data.filepath:
        here = os.path.dirname(bpy.data.filepath)
        root = os.path.dirname(here) if os.path.basename(here).upper() in ("SB", "RB") else here
    return root


def container_of(context, graph, obj) -> str:  # pragma: no cover — bpy
    """The RM container that holds the object (its label), from the scene's
    containers, else from the graph (``is_in_representation_model_group``)."""
    from .project_files import container_label_of
    label = container_label_of(context.scene, obj.name)
    if label or graph is None:
        return label
    rm = str(obj.get("em_rm_node_id") or "")
    for e in getattr(graph, "edges", []) or []:
        if e.edge_source == rm and e.edge_type == "is_in_representation_model_group":
            n = graph.find_node_by_id(e.edge_target)
            return getattr(n, "name", "") or ""
    return ""


def master_target(context, graph, obj, em_json: str) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Where «Export as master» writes ``obj``: the folder, the format, the
    file (the default convention ``<SB|RB>/<Container>/master/``)."""
    bpy = _bpy()
    B = bf()
    root = project_root_for(context, em_json)
    src = obj.data.library.filepath if (obj.data is not None and obj.data.library) else bpy.data.filepath
    src = bpy.path.abspath(src)
    branch = B.branch_of(src, root)
    if obj.get("em_alternative_of") is None and any(c.name == "RB" for c in obj.users_collection):
        branch = "RB"
    cont = container_of(context, graph, obj) or ("Survey" if branch == "RB" else "Reconstruction")
    folder = B.master_folder(root, branch, cont)
    fmt = B.master_format(branch)
    from .asset_versions import safe
    return {"root": root, "branch": branch, "container": cont, "folder": folder, "format": fmt,
            "path": os.path.join(folder, safe(obj.name) + fmt["ext"])}


def _export_one(context, obj, path: str, fmt: Dict[str, Any]) -> None:  # pragma: no cover — bpy
    """The bytes of a master: glTF separate (its .bin and textures beside;
    a packed texture is written out by the exporter) or OBJ with its .mtl
    and the textures copied beside it."""
    bpy = _bpy()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    layer = context.view_layer
    was = [o for o in layer.objects if o.select_get()]
    act = layer.objects.active
    try:
        for o in layer.objects:
            o.select_set(o == obj)
        layer.objects.active = obj
        if fmt["format"] == "obj":
            bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, export_materials=True,
                                  path_mode="COPY", export_uv=True, export_normals=True,
                                  apply_modifiers=True, forward_axis="Y", up_axis="Z")
        else:
            bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format="GLTF_SEPARATE",
                                      export_image_format="AUTO", export_apply=True)
    finally:
        for o in layer.objects:
            o.select_set(o in was)
        layer.objects.active = act


def _stamp(context, obj, path: str, *, technique: str, label: str) -> Dict[str, Any]:  # pragma: no cover
    from .. import birth_stamp as BS
    return BS.stamp_blender_export(path, objects=[obj], dtc_kind=BS.KIND_EXPORT, technique=technique,
                                   parameters={"step": MANUAL_STEP if technique == MANUAL_TECHNIQUE else technique},
                                   label=label, register_in_graph=False, context=context, force=True)


def _files_of(path: str) -> List[Dict[str, Any]]:  # pragma: no cover — bpy
    from .asset_versions import files_of_entry
    return files_of_entry(path)["files"]


def _relative(files: List[Dict[str, Any]], em_folder: str) -> List[Dict[str, Any]]:
    """The urls of a file set relative to the em.json's folder (inside the
    project; a file outside keeps its absolute path)."""
    out = []
    for f in files:
        f = dict(f)
        url = f.get("url") or ""
        if em_folder and url and os.path.isabs(url):
            rel = os.path.relpath(url, em_folder).replace(os.sep, "/")
            if not rel.startswith("../../.."):
                f["url"] = rel
        out.append(f)
    return out


def _mark(obj, digest: str, version_id: str = "", asset_id: str = "") -> None:  # pragma: no cover
    from .scene_sync import record_fingerprint
    if digest:
        obj["em_asset_sha256"] = digest
    if version_id:
        obj["em_version_id"] = version_id
    if asset_id:
        obj["em_asset_id"] = asset_id
    record_fingerprint(obj)


def export_master(context, graph, obj, em_json: str) -> Dict[str, Any]:  # pragma: no cover — bpy
    """«Export as master»: the object's bytes as its branch wants them, in its
    container's master/ folder, stamped; the graph's master of its RM points
    at the file (url relative to the em.json), the datablock's locator kept as
    ``from_datablock``. → ``{path, digest, master_id, state}``."""
    t = master_target(context, graph, obj, em_json)
    if not t["root"]:
        raise RuntimeError("no project here: save the .blend or the em.json in a project first")
    if os.path.exists(t["path"]):
        raise RuntimeError(f"{os.path.relpath(t['path'], t['root'])} is there already: a master is never "
                           "written over — remove it or register this as a version")
    _export_one(context, obj, t["path"], t["format"])
    st = _stamp(context, obj, t["path"], technique="master_export", label=f"{obj.name} (master)")
    files = _files_of(t["path"])
    from ..resource_digest import members_digest
    digest = members_digest(files) if len(files) > 1 else str(files[0]["checksum"])
    em_folder = os.path.dirname(em_json) if em_json else t["root"]
    rel = os.path.relpath(t["path"], em_folder).replace(os.sep, "/")
    master_id = ""
    if graph is not None:
        from .asset_versions import master_of
        master_id = master_of(graph, obj, context.scene) or ""
        node = graph.find_node_by_id(master_id) if master_id else None
        if node is not None:
            old = str((node.data or {}).get("url") or "")
            node.data.update({"url": rel, "checksum": digest, "tier": "master",
                              "media_type": "model/gltf+json" if t["format"]["format"] == "gltf" else "model/obj",
                              "packaging": "file_set" if len(files) > 1 else None,
                              "residency": "resident"})
            if hasattr(node, "url"):
                node.url = rel
            if old.startswith("blend://"):
                # the datablock it was made from: the .blend still knows its
                # masters (``blend_folder.FROM_DATABLOCK``)
                node.data["from_datablock"] = old
    _mark(obj, digest, asset_id=master_id)
    return {"path": t["path"], "rel": rel, "digest": digest, "master_id": master_id,
            "state": st.get("state"), "folder": t["folder"]}


def register_version(context, graph, obj, em_json: str, *, as_resource: bool = False
                     ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """«Register as a version…» (of the object's master: a child resource,
    ``dtc_derived_from`` the master, its step «manual work in Blender») or
    «… as a new resource» (an object only in the .blend: a resource of its
    own, tied to the object's RM when it has one). Exported as a glb in the
    container's versions/ folder, stamped, url relative to the em.json."""
    from .asset_versions import add_version_from_mesh, _stamper, safe, write_version
    if graph is None:
        raise RuntimeError("no active graph")
    t = master_target(context, graph, obj, em_json)
    folder = os.path.join(os.path.dirname(t["folder"]), "versions")
    os.makedirs(folder, exist_ok=True)
    em_folder = os.path.dirname(em_json) if em_json else t["root"]
    base = f"{safe(obj.name)}@manual-{time.strftime('%Y%m%d-%H%M%S')}"
    recipe = {"format": "glb", "draco": False}
    if as_resource:
        made = write_version(obj, obj.data, recipe, folder, base)
        st = _stamp(context, obj, made["entry"], technique=MANUAL_TECHNIQUE, label=f"{obj.name} (manual)")
        files = _relative(made["files"], em_folder)
        from s3dgraphy import api
        node = api.add_resource(graph, name=obj.name, kind="3d_model", files=files, tier="master",
                                residency="resident", data={"dtc_kind": "manual_editing",
                                                            "step": MANUAL_STEP})
        rm = str(obj.get("em_rm_node_id") or "")
        if rm and graph.find_node_by_id(rm) is not None:
            graph.add_edge(edge_id=f"{rm}_has_linked_resource_{node.node_id}", edge_source=rm,
                           edge_target=node.node_id, edge_type="has_linked_resource")
        _mark(obj, files[0].get("checksum") or "", asset_id=node.node_id)
        return {"resource_id": node.node_id, "path": made["entry"], "state": st.get("state"), "as": "resource"}
    made = write_version(obj, obj.data, recipe, folder, base)
    files = _relative(made["files"], em_folder)
    stamp = _stamper(graph, obj, made["files"], MANUAL_TECHNIQUE, {"step": MANUAL_STEP},
                     label=f"{obj.name} (manual work in Blender)")
    # a version made by hand is not a level of the LOD chain (lodN counts
    # lod_generation steps): it is NAMED, by when it was registered
    out = add_version_from_mesh(graph, obj, obj.data.copy(), level="manual-" + time.strftime("%Y%m%d-%H%M%S"),
                                purpose="",
                                files=files, room=None, technique=MANUAL_TECHNIQUE,
                                parameters={"step": MANUAL_STEP}, stamp=stamp)
    _mark(obj, files[0].get("checksum") or "", version_id=out.get("version_id", ""))
    return {"version_id": out.get("version_id"), "path": made["entry"], "level": out.get("level"),
            "as": "version", "warnings": out.get("warnings") or []}


def _import_file(path: str):  # pragma: no cover — bpy
    """The meshes of a master file, imported (then joined into one mesh)."""
    bpy = _bpy()
    before = set(bpy.data.objects)
    low = path.lower()
    if low.endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=path)
    elif low.endswith(".obj"):
        bpy.ops.wm.obj_import(filepath=path, forward_axis="Y", up_axis="Z")
    elif low.endswith(".ply"):
        bpy.ops.wm.ply_import(filepath=path)
    else:
        raise RuntimeError(f"cannot read {os.path.basename(path)} as a master")
    return [o for o in bpy.data.objects if o not in before]


def restore_from_master(context, graph, obj_name: str, master_id: str, em_folder: str
                        ) -> Dict[str, Any]:  # pragma: no cover — bpy
    """«Restore from the master»: the object's mesh from its stamped master
    (a file: imported; a datablock of a .blend: appended from it). The object
    keeps its name, its place and its bindings; a deleted object is made
    again in the scene's collection."""
    bpy = _bpy()
    node = graph.find_node_by_id(master_id) if (graph is not None and master_id) else None
    if node is None:
        raise RuntimeError(f"{obj_name}: no master in the graph to restore it from")
    url = str((node.data or {}).get("url") or getattr(node, "url", "") or "")
    digest = str((node.data or {}).get("checksum") or "")
    mesh = None
    if url.startswith("blend://"):
        rel, _, frag = url[len("blend://"):].partition("#")
        path = rel if os.path.isabs(rel) else os.path.normpath(os.path.join(em_folder, rel))
        kind, _, name = frag.partition("/")
        if os.path.realpath(path) == os.path.realpath(bpy.data.filepath):
            raise RuntimeError(f"{obj_name}: its master is a datablock of THIS .blend — export it as a "
                               "master first, then it can be restored")
        with bpy.data.libraries.load(path, link=False) as (src, dst):
            if kind == "Mesh":
                dst.meshes = [name] if name in src.meshes else []
            else:
                dst.objects = [name] if name in src.objects else []
        got = (dst.meshes or []) if kind == "Mesh" else [o.data for o in (dst.objects or []) if o]
        mesh = got[0] if got else None
    else:
        path = url if os.path.isabs(url) else os.path.normpath(os.path.join(em_folder, url))
        if not os.path.isfile(path):
            raise RuntimeError(f"{obj_name}: its master file is not there ({url})")
        new = _import_file(path)
        meshes = [o for o in new if o.type == "MESH"]
        if not meshes:
            raise RuntimeError(f"{obj_name}: no mesh in {os.path.basename(path)}")
        if len(meshes) > 1:
            with context.temp_override(selected_editable_objects=meshes, active_object=meshes[0],
                                       selected_objects=meshes):
                bpy.ops.object.join()
        mesh = meshes[0].data
        for o in new:
            if o.name in bpy.data.objects:
                bpy.data.objects.remove(o, do_unlink=True)
    if mesh is None:
        raise RuntimeError(f"{obj_name}: the master gave no mesh")
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        obj = bpy.data.objects.new(obj_name, mesh)
        context.scene.collection.objects.link(obj)
    else:
        old = obj.data
        obj.data = mesh
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    _mark(obj, digest, asset_id=master_id)
    return {"object": obj.name, "from": url}


def take_epochs(graph, obj, epochs: List[str]) -> None:  # pragma: no cover — bpy
    eps = getattr(obj, "EM_ep_belong_ob", None)
    if eps is None:
        return
    eps.clear()
    for name in epochs:
        eps.add().epoch = name


def relink_in(folder: str, name: str) -> str:
    """A file called ``name`` under ``folder`` (the first found), or ""."""
    for dirpath, _dirs, files in os.walk(folder):
        if name in files:
            return os.path.join(dirpath, name)
    return ""


def apply_rows(context, graph, rows: List[Dict[str, Any]], em_json: str, *, em_folder: str = ""
               ) -> Dict[str, Any]:  # pragma: no cover
    """«Apply»: each ticked row's action. → ``{done, failed}`` (lines).
    ``em_folder``: where the graph's relative urls start, when the em.json
    read is a copy elsewhere (EMStudio's background job)."""
    bpy = _bpy()
    em_folder = em_folder or (os.path.dirname(em_json) if em_json else "")
    done, failed = [], []
    for r in rows:
        act = r.get("action")
        name = r.get("name") or ""
        try:
            if act in (None, "", "leave"):
                continue
            obj = bpy.data.objects.get(r.get("object") or "") if r.get("object") else None
            if act == "restore_from_master":
                restore_from_master(context, graph, r.get("object") or name, r.get("master") or "", em_folder)
            elif act == "register_version":
                register_version(context, graph, obj, em_json)
            elif act == "register_resource":
                register_version(context, graph, obj, em_json, as_resource=True)
            elif act == "export_master":
                export_master(context, graph, obj, em_json)
            elif act == "take_epochs_from_graph":
                take_epochs(graph, obj, list(r.get("epochs_graph") or []))
            elif act == "unpack_texture":
                im = bpy.data.images.get(name)
                if im is not None and im.packed_file is not None:
                    im.unpack(method="WRITE_LOCAL")
            elif act == "relink_texture":
                im = bpy.data.images.get(name)
                hit = relink_in(os.path.dirname(bpy.data.filepath), os.path.basename(im.filepath)) if im else ""
                if not hit:
                    raise RuntimeError("not found beside the .blend")
                im.filepath = bpy.path.relpath(hit)
                im.reload()
            elif act == "relink_library":
                lb = bpy.data.libraries.get(name)
                hit = relink_in(os.path.dirname(os.path.dirname(bpy.data.filepath)),
                                os.path.basename(lb.filepath)) if lb else ""
                if not hit:
                    raise RuntimeError("not found in the project")
                lb.filepath = bpy.path.relpath(hit)
                lb.reload()
            else:
                raise RuntimeError(f"unknown action {act}")
            done.append(f"{name}: {act}")
        except Exception as exc:  # noqa: BLE001 — one row never stops the others
            failed.append(f"{name}: {act} — {exc}")
    return {"done": done, "failed": failed}


def command_blend_apply(target: str, params: Dict[str, Any], context, graph) -> Dict[str, Any]:  # pragma: no cover
    """The sidecar's command ``blend_apply`` (EMStudio's «Apply» while this
    Blender has the .blend open — the one session that may save it): the
    ticked rows, applied HERE; the .blend is left unsaved for the person to
    save (it is their session)."""
    bpy = _bpy()
    if os.path.realpath(target or "") != os.path.realpath(bpy.data.filepath or ""):
        return {"ok": False, "error": f"this Blender has {os.path.basename(bpy.data.filepath) or 'no file'} open, "
                                      f"not {os.path.basename(target or '')}"}
    from .project_files import active_emjson
    rows = [r for r in (params.get("rows") or []) if isinstance(r, dict)]
    out = apply_rows(context, graph, rows, active_emjson(context))
    return {"ok": not out["failed"] or bool(out["done"]), "info": out,
            "error": "; ".join(out["failed"]) if out["failed"] and not out["done"] else None}


# ── Blender: operators, panel ────────────────────────────────────────────────

def _operator_classes():  # pragma: no cover — bpy
    bpy = _bpy()
    from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty

    ACTIONS = [("leave", "Leave", "do nothing"),
               ("restore_from_master", "Restore from the master", "reimport its mesh from the stamped master"),
               ("register_version", "Register as a version", "export, stamp, a version of its master"),
               ("register_resource", "Register as a new resource", "export, stamp, a resource of its own"),
               ("export_master", "Export as master", "the master as a stamped file outside the .blend"),
               ("take_epochs_from_graph", "Take the graph's epochs", "the object's epochs as the graph says"),
               ("relink_texture", "Find the texture", "look for it beside the .blend"),
               ("unpack_texture", "Unpack the texture", "write it beside the .blend"),
               ("relink_library", "Find the library", "look for the .blend in the project")]

    class EM_PG_check_row(bpy.types.PropertyGroup):
        key: StringProperty()  # type: ignore
        label: StringProperty()  # type: ignore
        sign: StringProperty()  # type: ignore
        why: StringProperty()  # type: ignore
        tick: BoolProperty(name="", default=False)  # type: ignore
        action: EnumProperty(name="", items=ACTIONS, default="leave")  # type: ignore
        allowed: StringProperty()  # type: ignore

    class EM_UL_check_rows(bpy.types.UIList):
        def draw_item(self, context, layout, data, item, icon, active_data, active_prop, index=0):
            row = layout.row(align=True)
            row.prop(item, "tick", text="")
            row.label(text=f"{item.sign} {item.label}")
            sub = row.row()
            sub.enabled = item.tick
            sub.prop(item, "action", text="")

    class EM_OT_blend_check_graph(bpy.types.Operator):
        """Check this .blend against the graph: what is aligned, changed here, newer outside, missing,
        only in the .blend — with an action to tick for each"""
        bl_idname = "em.blend_check_graph"
        bl_label = "Check against the graph"
        bl_options = {"REGISTER"}

        source: EnumProperty(name="Source", items=[("disk", "Disk", "the stamps and fingerprints on disk"),
                                                   ("room", "Room", "the server's fingerprints (or the last known)")],
                             default="disk")  # type: ignore
        index: IntProperty(default=0)  # type: ignore

        def invoke(self, context, event):
            try:
                res = check_here(context, source=self.source)
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            rows = context.window_manager.em_check_rows
            rows.clear()
            for r in res["rows"]:
                if r["state"] == "aligned" and not r.get("actions"):
                    continue
                it = rows.add()
                it.key = r["key"]
                it.label = f"{r['name']}" + (f" — {r['why']}" if r.get("why") else "")
                it.sign = r["sign"]
                it.why = "; ".join(r.get("notes") or [])
                allowed = [a for a in (r.get("actions") or []) if a in {x[0] for x in ACTIONS}]
                it.allowed = ",".join(allowed)
                it.action = r.get("action") if r.get("action") in allowed else "leave"
                it.tick = bool(r.get("tick"))
            return context.window_manager.invoke_props_dialog(self, width=640)

        def draw(self, context):
            res = LAST.get("result") or {}
            col = self.layout.column()
            col.label(text=res.get("sentence") or "", icon="CHECKMARK")
            if res.get("offline"):
                col.label(text=f"The room was not reached: the last state known ({res.get('as_of') or '?'})",
                          icon="INFO")
            col.template_list("EM_UL_check_rows", "", context.window_manager, "em_check_rows", self, "index",
                              rows=10)
            col.label(text="Ticked rows are applied with OK («Apply»); nothing overwrites a change made here.")

        def execute(self, context):
            res = LAST.get("result") or {}
            by_key = {r["key"]: r for r in res.get("rows") or []}
            todo = []
            for it in context.window_manager.em_check_rows:
                if not it.tick or it.action == "leave":
                    continue
                r = dict(by_key.get(it.key) or {})
                if it.action not in (it.allowed or "").split(","):
                    continue
                r["action"] = it.action
                todo.append(r)
            if not todo:
                self.report({"INFO"}, "Nothing ticked")
                return {"FINISHED"}
            graph, _doc, _f = active_graph_doc(context)
            from .project_files import active_emjson
            out = apply_rows(context, graph, todo, active_emjson(context))
            for line in out["failed"]:
                self.report({"WARNING"}, line)
            self.report({"INFO"}, f"Applied {len(out['done'])}, failed {len(out['failed'])}")
            return {"FINISHED"}

    class _OnSelection:
        def _objs(self, context):
            return [o for o in context.selected_objects if o.type == "MESH"]

    class EM_OT_blend_register_version(bpy.types.Operator, _OnSelection):
        """Export the selected objects, stamp them with the step «manual work in Blender»
        and register each as a version of its master (url relative to the em.json)"""
        bl_idname = "em.blend_register_version"
        bl_label = "Register as a version…"
        bl_options = {"REGISTER", "UNDO"}
        as_resource: BoolProperty(name="As a new resource", default=False)  # type: ignore

        def invoke(self, context, event):
            return context.window_manager.invoke_confirm(self, event)

        def execute(self, context):
            graph, _d, _f = active_graph_doc(context)
            from .project_files import active_emjson
            em = active_emjson(context)
            ok = 0
            for o in self._objs(context):
                try:
                    register_version(context, graph, o, em, as_resource=self.as_resource)
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    self.report({"WARNING"}, f"{o.name}: {exc}")
            self.report({"INFO"}, f"Registered {ok}")
            return {"FINISHED"}

    class EM_OT_blend_restore_master(bpy.types.Operator, _OnSelection):
        """Reimport the selected objects' meshes from their stamped master"""
        bl_idname = "em.blend_restore_master"
        bl_label = "Restore from the master"
        bl_options = {"REGISTER", "UNDO"}

        def invoke(self, context, event):
            return context.window_manager.invoke_confirm(self, event)

        def execute(self, context):
            graph, _d, em_folder = active_graph_doc(context)
            from .asset_versions import master_of
            ok = 0
            for o in self._objs(context):
                try:
                    restore_from_master(context, graph, o.name, master_of(graph, o, context.scene) or "",
                                        em_folder)
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    self.report({"WARNING"}, str(exc))
            self.report({"INFO"}, f"Restored {ok}")
            return {"FINISHED"}

    class EM_OT_blend_export_master(bpy.types.Operator, _OnSelection):
        """Export the selected objects as masters: glTF + external textures (SB), OBJ + textures (RB),
        in <SB|RB>/<Container>/master/, stamped, the graph's master pointing at the file"""
        bl_idname = "em.blend_export_master"
        bl_label = "Export as master"
        bl_options = {"REGISTER", "UNDO"}

        def invoke(self, context, event):
            return context.window_manager.invoke_confirm(self, event)

        def execute(self, context):
            graph, _d, _f = active_graph_doc(context)
            from .project_files import active_emjson
            em = active_emjson(context)
            ok = 0
            for o in self._objs(context):
                try:
                    export_master(context, graph, o, em)
                    ok += 1
                except Exception as exc:  # noqa: BLE001
                    self.report({"WARNING"}, f"{o.name}: {exc}")
            self.report({"INFO"}, f"Exported {ok} master(s)")
            return {"FINISHED"}

    class EM_OT_prepare_in_emstudio(bpy.types.Operator):
        """Open EMStudio on this container to prepare it for a use (the optimisation
        window lives in EMStudio now)"""
        bl_idname = "em.prepare_in_emstudio"
        bl_label = "Prepare in EMStudio"
        container: StringProperty(default="")  # type: ignore

        def execute(self, context):
            from .project_files import active_emjson
            from . import operators as sync
            clients = sync.client_count() if sync.is_running() else 0
            room_info: Dict[str, Optional[str]] = {}
            try:
                from . import room as _room
                r = _room.room() or {}
                room_info = {"server": r.get("server"), "room": r.get("room") or r.get("room_id")}
            except Exception:  # noqa: BLE001
                pass
            plan = prepare_link(sidecar_clients=clients, room=room_info, container=self.container,
                                em_json=active_emjson(context), blend=bpy.data.filepath)
            if plan["way"] == "sidecar":
                try:
                    env = dict(plan["envelope"])
                    sync._server.broadcast(json.dumps(sync.envelope(env.pop("type"), env, source=sync._SOURCE)))
                    self.report({"INFO"}, "Asked EMStudio to open Prepare on " + (self.container or "the graph"))
                    return {"FINISHED"}
                except Exception as exc:  # noqa: BLE001
                    plan = {"way": None, "say": f"the Sidecar did not take it: {exc}"}
            if plan["way"] == "link":
                import webbrowser
                webbrowser.open(plan["url"])
                return {"FINISHED"}
            self.report({"WARNING"}, plan["say"])
            return {"CANCELLED"}

    return (EM_PG_check_row, EM_UL_check_rows, EM_OT_blend_check_graph, EM_OT_blend_register_version,
            EM_OT_blend_restore_master, EM_OT_blend_export_master, EM_OT_prepare_in_emstudio)


def draw_check(layout, context) -> None:  # pragma: no cover — bpy
    """The graph panel's row: «Check against the graph» and its last line."""
    row = layout.row(align=True)
    op = row.operator("em.blend_check_graph", icon="CHECKMARK", text="Check against the graph")
    op.source = "disk"
    res = LAST.get("result")
    if res:
        layout.label(text=f"{res.get('sentence')} · {LAST.get('at')}", icon="BLANK1")


def draw_modeller(layout, context) -> None:  # pragma: no cover — bpy
    """The gestures of who models, on the selection."""
    n = len([o for o in context.selected_objects if o.type == "MESH"])
    on = f" ({n})" if n > 1 else ""
    col = layout.column(align=True)
    col.enabled = n > 0
    col.operator("em.blend_register_version", icon="FILE_TICK", text="Register as a version…" + on)
    op = col.operator("em.blend_register_version", icon="ADD", text="Register as a new resource…" + on)
    op.as_resource = True
    col.operator("em.blend_restore_master", icon="LOOP_BACK", text="Restore from the master" + on)
    col.operator("em.blend_export_master", icon="EXPORT", text="Export as master" + on)


def draw_status(layout, context, obj) -> None:  # pragma: no cover — bpy
    """«Asset versions»: the status row of the active object's container, and
    «Prepare in EMStudio»."""
    master_stamped: Optional[bool] = None
    versions = 0
    cont = ""
    try:
        from ..functions import check_active_graph
        ok, graph = check_active_graph(context, show_message=False)
        if ok and graph is not None and obj is not None:
            from .asset_versions import master_of
            from s3dgraphy import api
            mid = master_of(graph, obj, context.scene)
            node = graph.find_node_by_id(mid) if mid else None
            if node is not None:
                url = str((node.data or {}).get("url") or "")
                master_stamped = bool(url) and not url.startswith("blend://")
                versions = max(0, len(api.versions_of(graph, mid)) - 1)
            cont = container_of(context, graph, obj)
    except Exception:  # noqa: BLE001
        pass
    res = LAST.get("result") or {}
    counts = None
    if obj is not None and res:
        st = (res.get("objects") or {}).get(obj.name)
        counts = {st: 1} if st else None
    box = layout.box()
    box.label(text=(cont or "—") + " · " + status_line(master_stamped=master_stamped, versions=versions,
                                                        counts=counts), icon="OUTLINER_COLLECTION")
    op = box.operator("em.prepare_in_emstudio", icon="URL", text="Prepare in EMStudio")
    op.container = cont


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    bpy = _bpy()
    import atexit
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.em_check_rows = bpy.props.CollectionProperty(type=_CLASSES[0])
    if not bpy.app.background and not bpy.app.timers.is_registered(_presence_timer):
        bpy.app.timers.register(_presence_timer, first_interval=2.0, persistent=True)
    from bpy.app.handlers import persistent
    for h, fn in ((bpy.app.handlers.load_pre, _on_load_pre), (bpy.app.handlers.load_post, _on_after),
                  (bpy.app.handlers.save_post, _on_after)):
        if fn not in h:
            h.append(persistent(fn))
    atexit.register(_at_exit)


def unregister():  # pragma: no cover — bpy
    bpy = _bpy()
    for h, fn in ((bpy.app.handlers.load_pre, _on_load_pre), (bpy.app.handlers.load_post, _on_after),
                  (bpy.app.handlers.save_post, _on_after)):
        if fn in h:
            h.remove(fn)
    if bpy.app.timers.is_registered(_presence_timer):
        bpy.app.timers.unregister(_presence_timer)
    _at_exit()
    if hasattr(bpy.types.WindowManager, "em_check_rows"):
        del bpy.types.WindowManager.em_check_rows
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
