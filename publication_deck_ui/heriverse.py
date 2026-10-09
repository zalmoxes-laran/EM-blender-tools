"""H4 · Heriverse as a DESTINATION of the Publication Deck: two roads.

E.D., 5 Oct 2026: nothing is re-exported from Blender for Heriverse. Heriverse
reads the study and picks, for each representation model, the version to load
with the rule of s3dgraphy (heriverse, aton, web, realtime, in that order).
The Deck says what it will pick, and leads there by one of two roads:

* **On the node** — em.json and assets in the room: the list says, per
  published model, the version the rule picks and whether its bytes are on the
  node, and which models have none («Prepare for a use…» beside them).
* **On disk** — the desktop without a node: a folder with the em.json and the
  versions it names (``versions/…``, relative paths, sha256 checked), which
  Heriverse opens offline (its server reads ``project.json`` from the zip) and
  so does an ATON app. A model without a version for a viewer gets one with
  «Make the missing versions»: «Prepare for a use…» with the use
  ``heriverse``/``aton``, as the model is (Q5) — a version like any other,
  in the graph, in the asset's library.

The decisions are in ``publication_heriverse.py`` (no bpy, tested headless);
here the scene, the folders and the operators. The re-export engine is in
``_dead_code/export_operators/heriverse/``; what of it the version uses (the
glTF writing, the dissemination filter) is in ``export_operators/heriverse/``.
"""

import os
from typing import Any, Dict, List, Tuple

import bpy  # type: ignore

from .. import publication_heriverse as PH

#: the last plan and the last package (session state, for the popup)
LAST: Dict[str, Any] = {}

ROADS = [("NODE", "On the node", "The em.json and the assets in the room: Heriverse "
                                 "fetches each version by its sha256"),
         ("DISK", "On disk", "A folder with the em.json and its versions, which "
                             "Heriverse or an ATON app opens offline")]


def publishable_graphs(context) -> List[Tuple[str, Any]]:
    """``[(graph_id, graph)]``: the active graph first, then the other
    publishable ones (``em_tools.graphml_files``, ``is_publishable``)."""
    from s3dgraphy import get_graph
    em_tools = context.scene.em_tools
    out, seen = [], set()
    order = list(range(len(em_tools.graphml_files)))
    if 0 <= em_tools.active_file_index < len(order):
        order.remove(em_tools.active_file_index)
        order.insert(0, em_tools.active_file_index)
    for i in order:
        item = em_tools.graphml_files[i]
        if not item.is_publishable:
            continue
        graph = get_graph(item.name)
        gid = str(getattr(graph, "graph_id", "") or item.name) if graph is not None else ""
        if graph is not None and gid not in seen:
            seen.add(gid)
            out.append((gid, graph))
    return out


def published_rms(context, graph) -> List[Tuple[str, str]]:
    """``[(rm_id, object_name)]``: the RM list's publishable rows whose model is
    in ``graph`` — what the Heriverse exporter published."""
    from ..rm_manager.containers import resolve_rm_node_id
    scene = context.scene
    out = []
    for item in scene.rm_list:
        if not item.is_publishable:
            continue
        obj = bpy.data.objects.get(item.name)
        rm_id = resolve_rm_node_id(graph, obj, scene=scene, migra=False) if obj else None
        if not rm_id and graph.find_node_by_id(f"{item.name}_model") is not None:
            rm_id = f"{item.name}_model"
        if rm_id:
            out.append((rm_id, item.name))
    return out


def published_rmdocs(context, graph) -> List[Tuple[str, str, str]]:
    """``[(rmdoc_id, object_name, "rmdoc")]``: the documents placed in space —
    the quads that carry ``em_doc_node_id`` (the Document Manager's), and the
    old convention the Heriverse exporter read, a mesh named as a document,
    extractor or combiner of the graph. The old exporter published them all."""
    out, seen = [], set()
    by_name = {}
    for kind in ("document", "extractor", "combiner"):
        for n in graph.indices.nodes_by_type.get(kind, []):
            by_name.setdefault(n.name, n.node_id)
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        doc_id = str(obj.get("em_doc_node_id", "") or "") or by_name.get(obj.name, "")
        if not doc_id or graph.find_node_by_id(doc_id) is None:
            continue
        rid = f"{doc_id}_rm_doc"
        if rid not in seen:
            seen.add(rid)
            out.append((rid, obj.name, "rmdoc"))
    return out


def published_rmsfs(context, graph) -> List[Tuple[str, str, str]]:
    """``[(rmsf_id, object_name, "rmsf")]``: the anastylosis list's publishable
    rows, as the old exporter read them."""
    out = []
    for item in context.scene.em_tools.anastylosis.list:
        if not item.is_publishable or bpy.data.objects.get(item.name) is None:
            continue
        out.append((item.node_id or f"{item.name}_rmsf", item.name, "rmsf"))
    return out


def published(context, graph, *, rm=True, rmdoc=True, rmsf=True) -> List[Tuple[str, str, str]]:
    """Every published model of ``graph`` with its category."""
    out = [(rid, name, "rm") for rid, name in published_rms(context, graph)] if rm else []
    if rmdoc:
        out += published_rmdocs(context, graph)
    if rmsf:
        out += published_rmsfs(context, graph)
    return out


def unpublished(context, graph) -> List[str]:
    """The ids of the representation models NOT published: every RM and RMSF
    of the graph that is not a publishable row of the RM list or of the
    anastylosis list — the old exporter published those rows only (RM nodes
    of models not in this scene, the tiles of another .blend, are not
    published from here either). The RMDocs all go, as before."""
    published_ids = {rid for rid, _name in published_rms(context, graph)}
    published_ids |= {rid for rid, _name, _c in published_rmsfs(context, graph)}
    return [n.node_id for n in graph.nodes
            if getattr(n, "node_type", "") in ("representation_model", "representation_model_sf")
            and n.node_id not in published_ids]


def _states(graph) -> Dict[str, str]:
    """The last «Check files» of this graph, ``{resource_id: state}`` (R1)."""
    try:
        from ..sync_manager.file_states import ULTIMI
    except Exception:  # noqa: BLE001
        return {}
    if ULTIMI.get("graph_id") != str(getattr(graph, "graph_id", "")):
        return {}
    return {r["id"]: r.get("state") for r in ULTIMI.get("results") or [] if r.get("id")}


def make_plan(context, *, rm=True, rmdoc=True, rmsf=True) -> Dict[str, Any]:
    """The rule's answer for every published model of every publishable graph,
    one plan (rows carry ``graph_id`` and the model's category)."""
    total: Dict[str, Any] = {"available": True, "note": "", "ready": [], "missing": [],
                             "removed": 0, "absent": [], "uses": list(PH.USES),
                             "graphs": []}
    for gid, graph in publishable_graphs(context):
        plan = PH.plan_for(graph, published(context, graph, rm=rm, rmdoc=rmdoc, rmsf=rmsf),
                           states=_states(graph))
        if not plan["available"]:
            return plan
        for key in ("ready", "missing"):
            total[key] += [dict(r, graph_id=gid) for r in plan[key]]
        total["removed"] += plan["removed"]
        total["absent"] += plan["absent"]
        total["graphs"].append(gid)
    return total


def _roots_and_caches(context) -> Tuple[List[str], List[str]]:
    from ..sync_manager.asset_versions import CACHE_DIR, cache_folder
    from ..sync_manager.bring import base_dirs
    from ..sync_manager.file_states import project_root
    roots = [d for d in base_dirs(context) if d]
    if bpy.data.filepath:
        roots.append(os.path.dirname(bpy.data.filepath))
    root = project_root(context)
    if root:
        roots.append(root)
    caches = [os.path.join(cache_folder(), CACHE_DIR)]
    if root:
        caches.append(os.path.join(root, ".em_cache"))
    return roots, caches


def make_disk_plan(context, plan: Dict[str, Any]) -> Dict[str, Any]:
    roots, caches = _roots_and_caches(context)
    return PH.disk_plan(plan, finder=lambda row: PH.local_bytes(row, roots=roots,
                                                                caches=caches))


def package_folder(context) -> str:
    """Where the package goes: the folder of the Heriverse settings that
    stayed (``scene.heriverse_export_path``), else beside the .blend; inside
    it ``<project>_heriverse``."""
    scene = context.scene
    base = bpy.path.abspath(getattr(scene, "heriverse_export_path", "") or "//")
    if not base or base == "//":
        base = os.path.dirname(bpy.data.filepath) or bpy.app.tempdir
    name = (getattr(scene, "heriverse_project_name", "")
            or os.path.splitext(os.path.basename(bpy.data.filepath))[0] or "study")
    return os.path.join(base, f"{PH._safe(name)}_heriverse")


class EM_OT_deck_heriverse(bpy.types.Operator):
    """What Heriverse will find for each published model, on the node or in a
    folder on disk, and the gestures that complete it"""

    bl_idname = "em.deck_heriverse"
    bl_label = "Heriverse"

    road: bpy.props.EnumProperty(name="Road", items=ROADS, default="NODE")  # type: ignore

    def invoke(self, context, event):
        LAST["plan"] = make_plan(context)
        LAST["disk"] = make_disk_plan(context, LAST["plan"]) if LAST["plan"].get("available") else {}
        LAST["folder"] = package_folder(context)
        return context.window_manager.invoke_popup(self, width=560)

    def draw(self, context):
        layout = self.layout
        plan = LAST.get("plan") or {}
        layout.row().prop(self, "road", expand=True)
        layout.label(text=PH.summary(plan) if plan else "no plan", icon="WORLD_DATA")
        if not plan.get("available", True):
            return
        disk = LAST.get("disk") or {}
        by_rm = {(r.get("graph_id"), r["rm_id"]): r for r in disk.get("rows") or []}
        col = layout.column(align=True)
        rows = (plan.get("ready") or []) + (plan.get("missing") or [])
        for row in rows[:16]:
            line = col.row(align=True)
            ready = row["reason"] in PH.READY
            if self.road == "NODE":
                tail = f" · {row['on_node_said']}" if ready and row.get("on_node_said") else ""
            else:
                d = by_rm.get((row.get("graph_id"), row["rm_id"])) or {}
                tail = f" · {d.get('local_said', '')}" if d else ""
            line.label(text=PH.row_line(row) + tail,
                       icon="CHECKMARK" if ready else "ERROR")
            if not ready and row.get("object"):
                op = line.operator("em.deck_heriverse_prepare", text="", icon="MOD_DECIM")
                op.object_name = row["object"]
        if len(rows) > 16:
            col.label(text=f"… and {len(rows) - 16} more")
        layout.separator()
        missing = [r for r in plan.get("missing") or [] if r.get("object")]
        if missing:
            layout.operator("em.deck_heriverse_make_missing",
                            text=f"Make the missing versions ({len(missing)}) — as they are",
                            icon="MOD_DECIM")
        if self.road == "NODE":
            layout.label(text="Publishing = the em.json and these assets on the node "
                              "(Push the study, Upload)", icon="INFO")
        else:
            layout.label(text=LAST.get("folder", ""), icon="FILE_FOLDER")
            layout.operator("em.deck_heriverse_write_disk", text="Write the package on disk",
                            icon="EXPORT")
            last = LAST.get("package")
            if last:
                layout.label(text=PH.package_sentence(last), icon="INFO")

    def execute(self, context):
        return {"FINISHED"}


def _select_only(context, obj) -> None:
    for o in context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


class EM_OT_deck_heriverse_prepare(bpy.types.Operator):
    """«Prepare for a use…» on this model, for Heriverse"""

    bl_idname = "em.deck_heriverse_prepare"
    bl_label = "Prepare for Heriverse…"

    object_name: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        obj = bpy.data.objects.get(self.object_name)
        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, f"{self.object_name}: no mesh object in this scene")
            return {"CANCELLED"}
        _select_only(context, obj)
        #: the recipe is the object's category's (`version_recipe`): a glTF
        #: with its textures, as the old exporter wrote it
        return bpy.ops.em.asset_prepare_for_use("INVOKE_DEFAULT", use=set(PH.PACKAGE_USES))


class EM_OT_deck_heriverse_make_missing(bpy.types.Operator):
    """For each published model (RM, RMDoc, RMSF) without a version for a
    viewer: «Prepare for a use…» with the use heriverse/aton and the recipe of
    its category (`version_recipe`): a glTF with its textures, the model as it
    is (no decimation, no Draco — Q5), an RMDoc at the origin with its
    placement on its node and its textures capped and re-encoded as the old
    exporter did. Each is a version in the graph and in the asset's library,
    with its sha256 and its stamp"""

    bl_idname = "em.deck_heriverse_make_missing"
    bl_label = "Make the missing versions"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        plan = make_plan(context)
        made, failed = [], []
        active = context.view_layer.objects.active
        for row in plan.get("missing") or []:
            obj = bpy.data.objects.get(row.get("object") or "")
            if obj is None or obj.type != "MESH":
                failed.append(f"{row['rm_name']}: no mesh object")
                continue
            _select_only(context, obj)
            try:
                res = bpy.ops.em.asset_prepare_for_use(
                    "EXEC_DEFAULT", use=set(PH.PACKAGE_USES))
            except RuntimeError as exc:
                failed.append(f"{row['rm_name']}: {exc}")
                continue
            (made if "FINISHED" in res else failed).append(row["rm_name"])
        if active is not None:
            try:
                context.view_layer.objects.active = active
            except Exception:  # noqa: BLE001
                pass
        LAST["plan"] = make_plan(context)
        LAST["disk"] = make_disk_plan(context, LAST["plan"])
        LAST["made"] = {"made": made, "failed": failed}
        if failed:
            self.report({"WARNING"}, "not made: " + "; ".join(str(f) for f in failed[:4]))
        self.report({"INFO"}, f"{len(made)} version(s) for Heriverse made: "
                              + ", ".join(made[:6]))
        return {"FINISHED"} if made or not failed else {"CANCELLED"}


def _addon_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def extras_for(context, graphs: Dict[str, Any], *, proxies=True, dosco=True,
               panorama=True) -> Dict[str, Any]:
    """What the package carries beside the models, as the old exporter did:
    the proxies' glb, the DosCo folder, the default sky and the epochs' HDRs —
    found on this disk (`publication_heriverse.write_extras`'s keywords)."""
    roots, _caches = _roots_and_caches(context)
    out: Dict[str, Any] = {}

    def on_disk(url: str) -> str:
        for c in PH._candidates(url, roots):
            if os.path.isfile(c):
                return os.path.normpath(c)
        return ""

    if proxies:
        rows = []
        for graph in graphs.values():
            for n in graph.nodes:
                d = getattr(n, "data", None) or {}
                if getattr(n, "node_type", "") != "resource" or d.get("url_type") != "proxy_model":
                    continue
                if PH.is_removed(n):
                    continue
                rows.append({"id": n.node_id, "name": n.name, "path": on_disk(str(d.get("url") or "")),
                             "checksum": d.get("checksum") or ""})
        out["proxies"] = rows
    if dosco:
        from ..sync_manager.file_states import project_root
        folder = ""
        for item in context.scene.em_tools.graphml_files:
            if getattr(item, "dosco_dir", ""):
                folder = bpy.path.abspath(item.dosco_dir)
                break
        if not folder:
            #: the EM standard tree: `DosCo/` beside the em.json
            for root in [project_root(context)] + roots:
                cand = os.path.join(root or "", "DosCo") if root else ""
                if cand and os.path.isdir(cand):
                    folder = cand
                    break
        if folder and os.path.isdir(folder):
            res = {}
            for graph in graphs.values():
                for n in graph.nodes:
                    d = getattr(n, "data", None) or {}
                    path = on_disk(str(d.get("url") or "")) if d.get("url") else ""
                    if path:
                        res[n.node_id] = path
            out["dosco"] = {"folder": folder, "resources": res}
    if panorama:
        sky = os.path.join(_addon_root(), "resources", "panorama", PH.DEFAULT_PANORAMA)
        out["panorama"] = sky if os.path.isfile(sky) else ""
        lights = {}
        for epoch in context.scene.em_tools.epochs.list:
            if getattr(epoch, "epoch_lighting_enabled", False) and getattr(epoch, "epoch_hdr_path", ""):
                lights[epoch.name] = {"path": bpy.path.abspath(epoch.epoch_hdr_path),
                                      "rotation": epoch.epoch_hdr_rotation,
                                      "intensity": epoch.epoch_hdr_intensity}
        out["epoch_panoramas"] = lights
    return out


def stamp_package(dest: str, report: Dict[str, Any]) -> Dict[str, Any]:
    """R4 · the package is stamped too: a tree, made from the versions it
    carries (by id and digest) — `birth_stamp.stamp_export`."""
    from .. import birth_stamp as BS
    parents = [{"resource_id": w["version_id"], "digest": f"sha256:{w['sha']}",
                "label": w["rm_name"]} for w in report.get("written") or [] if w.get("sha")]
    return BS.stamp_export(dest, parents=parents,
                           how={"dtc_kind": BS.resolve_kind(BS.KIND_PACKING),
                                "technique": "heriverse_package",
                                "software": BS.blender_software()},
                           operator=BS.current_operator(),
                           label=f"Heriverse package {os.path.basename(dest)}")


class EM_OT_deck_heriverse_write_disk(bpy.types.Operator):
    """Write the package for Heriverse on disk: the em.json (the study as the
    heriverse surface shows it) and the bytes of the version the rule picks
    for each published model (RM, RMDoc, RMSF), checked against their sha256 —
    a glTF with its textures in a folder of its own, a tileset's tree in
    tilesets/ —, the proxies, the DosCo and the panorama as the old exporter
    wrote them, the package stamped, and also as a zip, the file Heriverse's
    upload takes"""

    bl_idname = "em.deck_heriverse_write_disk"
    bl_label = "Write the package on disk"

    folder: bpy.props.StringProperty(name="Folder", subtype="DIR_PATH")  # type: ignore
    make_zip: bpy.props.BoolProperty(name="Also as a zip", default=True)  # type: ignore
    from_node: bpy.props.BoolProperty(  # type: ignore
        name="Fetch from the node what is not on this disk", default=True)
    export_rm: bpy.props.BoolProperty(name="RM", default=True)  # type: ignore
    export_rmdoc: bpy.props.BoolProperty(name="RMDoc", default=True)  # type: ignore
    export_rmsf: bpy.props.BoolProperty(name="RMSF", default=True)  # type: ignore
    export_proxies: bpy.props.BoolProperty(name="Proxies", default=True)  # type: ignore
    export_dosco: bpy.props.BoolProperty(name="DosCo", default=True)  # type: ignore
    export_panorama: bpy.props.BoolProperty(name="Panorama", default=True)  # type: ignore
    skip_extracted_tilesets: bpy.props.BoolProperty(  # type: ignore
        name="Keep tilesets already there", default=True,
        description="A tileset's tree already in the folder with the same content "
                    "is not copied again (the old «Skip Previously Extracted Tilesets»)")

    def _scene_defaults(self, context):
        """The package settings the old exporter kept in the scene and the
        window manager (`scene.heriverse_export_panorama`, `export_vars`):
        what was chosen for this .blend is the default here too."""
        scene, ev = context.scene, getattr(context.window_manager, "export_vars", None)
        pairs = [("export_panorama", scene, "heriverse_export_panorama")]
        if ev is not None:
            pairs += [("export_proxies", ev, "heriverse_export_proxies"),
                      ("export_dosco", ev, "heriverse_export_dosco"),
                      ("export_rm", ev, "heriverse_export_rm"),
                      ("export_rmdoc", ev, "heriverse_export_rmdoc"),
                      ("export_rmsf", ev, "heriverse_export_rmsf"),
                      ("make_zip", ev, "heriverse_create_zip"),
                      ("skip_extracted_tilesets", ev, "heriverse_skip_extracted_tilesets")]
        for mine, owner, theirs in pairs:
            if hasattr(owner, theirs) and not self.properties.is_property_set(mine):
                setattr(self, mine, bool(getattr(owner, theirs)))

    def invoke(self, context, event):
        self._scene_defaults(context)
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "folder")
        row = col.row(align=True)
        for name in ("export_rm", "export_rmdoc", "export_rmsf"):
            row.prop(self, name, toggle=True)
        row = col.row(align=True)
        for name in ("export_proxies", "export_dosco", "export_panorama"):
            row.prop(self, name, toggle=True)
        col.prop(self, "skip_extracted_tilesets")
        col.prop(self, "make_zip")
        col.prop(self, "from_node")

    def execute(self, context):
        self._scene_defaults(context)
        plan = make_plan(context, rm=self.export_rm, rmdoc=self.export_rmdoc,
                         rmsf=self.export_rmsf)
        if not plan.get("available"):
            self.report({"ERROR"}, plan.get("note") or PH.NO_VERSION_FOR)
            return {"CANCELLED"}
        disk = make_disk_plan(context, plan)
        graphs = dict(publishable_graphs(context))
        if not graphs:
            self.report({"ERROR"}, "no publishable graph")
            return {"CANCELLED"}
        dest = bpy.path.abspath(self.folder) if self.folder else package_folder(context)
        fetch = None
        if self.from_node:
            try:
                from ..sync_manager.materialise import _default_fetch
                from ..sync_manager import room
                fetch = _default_fetch if room.is_configured() else None
            except Exception:  # noqa: BLE001 — no room: the disk only
                fetch = None
        drop = [x for g in graphs.values() for x in unpublished(context, g)]
        #: the georeferencing travels as the study holds it (its GeoPositionNode).
        #: The old JSON writer first pushed the scene's `em_georef` onto it
        #: (DP-56): measured on Templu Mare v2 that would write shift 0, 0, 0
        #: over the em.json's 327300, 448370, 500 — not carried over
        doc = PH.heriverse_document(graphs, active=next(iter(graphs)), unpublished=drop)
        extras = extras_for(context, graphs, proxies=self.export_proxies,
                            dosco=self.export_dosco, panorama=self.export_panorama)
        report = PH.write_package(dest, doc, disk["rows"], fetch=fetch,
                                  make_zip=self.make_zip, extras=extras,
                                  skip_extracted_tilesets=self.skip_extracted_tilesets)
        stamped = stamp_package(dest, report)
        report["stamp"] = {"state": stamped.get("state"), "path": stamped.get("stamp_path"),
                           "line": stamped.get("line")}
        if stamped.get("state") not in ("stamped", "revised", "unchanged"):
            self.report({"WARNING"}, f"the package is not stamped: {stamped.get('line')}")
        LAST["package"] = report
        for f in report["failed"]:
            self.report({"WARNING"}, f"{f['rm_name']}: {f['why']}")
        for row in disk["missing_version"]:
            if not row.get("rel"):
                self.report({"WARNING"}, PH.row_line(row) + f" · {row.get('local_said', '')}")
        self.report({"INFO"}, PH.package_sentence(report))
        return {"FINISHED"}


CLASSES = (EM_OT_deck_heriverse, EM_OT_deck_heriverse_prepare,
           EM_OT_deck_heriverse_make_missing, EM_OT_deck_heriverse_write_disk)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
