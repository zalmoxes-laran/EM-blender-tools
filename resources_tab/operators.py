"""Operators for the EM Scene tab.

Scan the DosCo / library folder into the R1 FS-index backend (stable IDs), set the
DosCo folder via a folder picker, "hat" a Shelf orphan into a Master Document that
ADOPTS the FS stable ID as its node_id, and "Promote to MinIO" a local resource
(in-process s3dgraphy, preserving the stable ID). All graph writes go through the
s3dgraphy graph (em.json = truth) and persist through the existing GraphML
round-trip. Nothing here is a 3D object.
"""

from __future__ import annotations

import os

import bpy
from bpy.types import Operator

from . import properties, resource_backend

# Session cache: folder → scanned FSIndexBackend. The manifest on disk keeps IDs
# stable across sessions; this cache keeps the SAME backend instance between
# "scan" and "hat" within a session so a listed orphan's stable ID matches the
# id adopted on hatting.
_BACKENDS: dict = {}


def get_cached_backend(folder: str):
    return _BACKENDS.get(os.path.abspath(folder)) if folder else None


def _active_graphml_item(context):
    """The active GraphMLFileItem, or None."""
    try:
        em_tools = context.scene.em_tools
        return em_tools.graphml_files[em_tools.active_file_index]
    except Exception:
        return None


def _active(context):
    """(ok, graph, folder, graph_code). Reports nothing; UI/ops decide.
    Resolves the DosCo folder via the shared resolver (legacy dosco_dir AND the
    newer auxiliary-files system)."""
    from ..functions import check_active_graph
    ok, graph = check_active_graph(context, show_message=False)
    if not ok or graph is None:
        return False, None, "", None
    folder = ""
    item = _active_graphml_item(context)
    if item is not None:
        try:
            from ..em_setup.resource_utils import resolve_dosco_dir
            folder = resolve_dosco_dir(item) or ""
        except Exception:
            folder = bpy.path.abspath(item.dosco_dir) if getattr(item, "dosco_dir", "") else ""
    graph_code = None
    attrs = getattr(graph, "attributes", None) or {}
    if isinstance(attrs, dict):
        graph_code = attrs.get("graph_code")
    return True, graph, folder, graph_code


class EM_OT_resources_scan(Operator):
    bl_idname = "em.resources_scan"
    bl_label = "Scan resources folder"
    bl_description = ("Scan the DosCo / library folder into the resource index "
                      "(stable IDs). Orphans appear in the Shelf.")
    bl_options = {'REGISTER'}

    def execute(self, context):
        p = context.scene.em_resources
        if not resource_backend.resources_supported():
            self.report({'ERROR'},
                        "Resource layer unavailable: the active s3dgraphy is stale — "
                        "activate the dev/updated s3dgraphy (./em.sh s3d), then reopen.")
            return {'CANCELLED'}
        ok, _graph, folder, _gc = _active(context)
        if not ok:
            self.report({'WARNING'}, "No active graph selected.")
            return {'CANCELLED'}
        if not folder or not os.path.isdir(folder):
            self.report({'WARNING'},
                        "No valid DosCo/library folder set for the active GraphML.")
            return {'CANCELLED'}
        try:
            backend = resource_backend.get_backend(folder)
        except Exception as exc:
            self.report({'ERROR'}, f"Scan failed: {exc}")
            return {'CANCELLED'}
        _BACKENDS[os.path.abspath(folder)] = backend
        n = len(backend.entries(present_only=True))
        p.scanned_folder = folder
        p.status = f"Indexed {n} file(s)"
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_resources_hat_document(Operator):
    bl_idname = "em.resources_hat_document"
    bl_label = "Create Document from resource"
    bl_description = ("Promote this Shelf resource to a Master Document. The "
                      "document adopts the resource's stable ID as its node id.")
    bl_options = {'REGISTER', 'UNDO'}

    resource_id: bpy.props.StringProperty()  # type: ignore
    key_id: bpy.props.StringProperty()  # type: ignore
    new_name: bpy.props.StringProperty(name="Name")  # type: ignore
    new_description: bpy.props.StringProperty(name="Description", default="")  # type: ignore

    def invoke(self, context, event):
        if not self.new_name:
            self.new_name = self.key_id or "Document"
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "new_name")
        col.prop(self, "new_description")
        col.label(text=f"Adopts stable ID: {self.resource_id[:8]}…", icon='LINKED')
        col.label(text="Anchor it to an epoch later in the EM tree.", icon='INFO')

    def execute(self, context):
        if not resource_backend.resources_supported():
            self.report({'ERROR'}, "Resource layer unavailable (stale s3dgraphy).")
            return {'CANCELLED'}
        ok, graph, _folder, _gc = _active(context)
        if not ok:
            self.report({'WARNING'}, "No active graph.")
            return {'CANCELLED'}
        if not self.resource_id:
            return {'CANCELLED'}
        try:
            node = resource_backend.hat_orphan_as_document(
                graph, self.resource_id,
                name=self.new_name or self.key_id or "Document",
                description=self.new_description.strip())
        except Exception as exc:
            self.report({'ERROR'}, f"Create document failed: {exc}")
            return {'CANCELLED'}
        # Refresh EMTools document lists so it shows up immediately.
        try:
            from ..canonical_document_helpers import refresh_document_lists
            refresh_document_lists(context, node, graph)
        except Exception:
            pass
        context.scene.em_resources.status = f"Hatted {self.key_id or self.resource_id[:8]} → Document"
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_resources_set_dosco_folder(Operator):
    bl_idname = "em.resources_set_dosco_folder"
    bl_label = "Set DosCo folder"
    bl_description = ("Choose the DosCo / library folder for the active GraphML "
                      "(opens a folder browser)")
    bl_options = {'REGISTER'}

    # a directory-only file browser (subtype DIR_PATH, no filename field)
    directory: bpy.props.StringProperty(subtype='DIR_PATH')  # type: ignore

    def invoke(self, context, event):
        if _active_graphml_item(context) is None:
            self.report({'WARNING'}, "No active GraphML — select one in EM Setup.")
            return {'CANCELLED'}
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        item = _active_graphml_item(context)
        if item is None:
            self.report({'WARNING'}, "No active GraphML.")
            return {'CANCELLED'}
        item.dosco_dir = self.directory
        self.report({'INFO'}, f"DosCo folder set: {self.directory}")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_resources_promote_minio(Operator):
    bl_idname = "em.resources_promote_minio"
    bl_label = "Promote to MinIO"
    bl_description = ("Upload this local resource into the shared MinIO object "
                      "store (keeps its stable ID) and repoint its locator")
    bl_options = {'REGISTER', 'UNDO'}

    resource_id: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        if not resource_backend.minio_supported():
            self.report({'ERROR'},
                        "MinIO unavailable: needs the dev s3dgraphy (./em.sh s3d) "
                        "AND the 'minio' extra (pip install s3dgraphy[minio]).")
            return {'CANCELLED'}
        ok, graph, _folder, _gc = _active(context)
        if not ok:
            self.report({'WARNING'}, "No active graph.")
            return {'CANCELLED'}
        if not self.resource_id:
            return {'CANCELLED'}
        try:
            res = resource_backend.promote_resource_to_minio(graph, self.resource_id)
        except Exception as exc:
            self.report({'ERROR'}, f"Promote failed: {exc}")
            return {'CANCELLED'}
        context.scene.em_resources.status = f"Promoted → {res['s3_uri']}"
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_publish_distribution(Operator):
    """R6 · IL GESTO CHE MANCAVA: una distribution diventa PUBBLICATA.

    Il modello ha tre stati e solo due erano raggiungibili — il master nasce
    alla promozione, la distribution al bake, e la pubblicata non la produceva
    nessuno: l'export scrive un url relativo e si ferma.

    Qui non si costruisce niente di nuovo. I byte li carica la promozione a
    MinIO che c'era già; locator, checksum ed evento D7 li scrive
    `s3Dgraphy/publication.py::promote_resource`, che sa già farlo. Questo
    operatore è la cucitura fra i due, e l'unica cosa che decide è **quando
    rifiutare**, che è la parte che `publication_gesture` tiene fuori da
    Blender perché si possa provare.

    L'ordine conta e non è negoziabile: **prima i byte, poi il grafo**. Se il
    caricamento fallisce il documento non viene toccato, quindi non resta a
    dichiarare pubblicata una risorsa che nello store non c'è.
    """

    bl_idname = "em.publish_distribution"
    bl_label = "Publish this distribution"
    bl_description = ("Upload this distribution into the object store and "
                      "record its address, its checksum and the event that "
                      "says where it came from")
    bl_options = {'REGISTER', 'UNDO'}

    resource_id: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        import os
        from .. import publication_gesture as pg
        from .. import resource_levels as rl

        ok, graph, _folder, _gc = _active(context)
        if not ok:
            self.report({'WARNING'}, "No active graph.")
            return {'CANCELLED'}
        nodo = graph.find_node_by_id(self.resource_id) if self.resource_id else None
        if nodo is None:
            self.report({'WARNING'}, f"{self.resource_id!r}: not in this graph")
            return {'CANCELLED'}

        # D5 · le basi contro cui un locator relativo si risolve. Con
        # `os.path.isfile` nudo — la forma di prima — un documento DosCo
        # risultava sempre «the bytes are not where the locator says», perché
        # il suo url è relativo alla cartella DosCo e non alla cartella da cui
        # Blender è stato lanciato.
        from ..rm_manager.containers import basi_dei_locator
        basi = basi_dei_locator(context)
        esito = pg.stato_di_pubblicazione(nodo, esiste=pg.esistenza(basi))
        if not esito["si"]:
            # la ragione viaggia col rifiuto: «no» da solo è indistinguibile
            # da un guasto
            self.report({'WARNING'}, f"{self.resource_id}: {esito['perche']}")
            return {'CANCELLED'}
        if not resource_backend.minio_supported():
            self.report({'ERROR'},
                        "The object store is unavailable: needs the dev "
                        "s3dgraphy (./em.sh s3d) AND the 'minio' extra.")
            return {'CANCELLED'}

        dati = getattr(nodo, "data", None) or {}
        #: MICRO risorsa-file · una risorsa di PIÙ file (un glTF separato, un
        #: albero) si carica membro per membro, e questo bottone carica un file
        #: solo: caricarne la porta e dirla pubblicata lascerebbe nello store
        #: un `.gltf` che chiama `.bin` e texture che non ci sono.
        if dati.get("packaging") in ("file_set", "directory"):
            self.report({'WARNING'},
                        f"{self.resource_id}: a {dati.get('packaging')} is several "
                        f"files, and publishing them one by one is not done yet — "
                        f"publish its archive form, if it has one")
            return {'CANCELLED'}
        locator = str(dati.get("url") or "")
        percorso = pg.risolvi(locator, basi) or locator
        digest = rl.sha256_del_file(percorso)
        if not digest:
            self.report({'ERROR'},
                        f"{percorso}: nothing to digest — a reference without "
                        f"a checksum is a promise, not a fact")
            return {'CANCELLED'}
        #: SOSTITUIRE, NON SOVRASCRIVERE: se il file al locator non è più quello
        #: registrato (riesportato dopo), si pubblica una REVISIONE, e la
        #: risorsa vecchia resta col suo digest. Stessi byte → stessa risorsa:
        #: passare da un percorso locale all'indirizzo dello store è un cambio
        #: di locator, non di contenuto.
        registrato = str(dati.get("checksum") or "")
        if registrato and registrato != digest:
            from .. import resource_revisions as rr
            esito = rr.revise_files(graph, self.resource_id, [{
                "path": os.path.basename(locator), "url": locator,
                "checksum": digest, "size_bytes": os.path.getsize(percorso)}])
            if esito["new_resource_id"]:
                citanti, _ = rr.split_pointers(esito["pointing_at_old"])
                self.report({'INFO'},
                            f"{self.resource_id}: the file changed since it was "
                            f"recorded — publishing a revision; {len(citanti)} "
                            f"citations stay on the old one (Resources → Revisions)")
                self.resource_id = esito["new_resource_id"]
        try:
            caricato = resource_backend.promote_resource_to_minio(
                graph, self.resource_id, percorso=percorso)
        except Exception as exc:                       # noqa: BLE001
            self.report({'ERROR'}, f"Upload failed: {exc}")
            return {'CANCELLED'}

        try:
            from s3dgraphy.publication import promote_resource
        except ImportError as exc:
            # decisione 14: si dice cosa manca, non si ingoia
            self.report({'ERROR'},
                        f"publication.promote_resource unavailable ({exc}): "
                        f"the bytes are in the store but the event is not "
                        f"written")
            return {'CANCELLED'}
        try:
            promote_resource(
                graph, self.resource_id,
                url=caricato["s3_uri"], sha256=digest,
                #: `resident`: lo store è quello dello studio, i byte ci sono
                residency="resident",
                #: e resta ciò che era — pubblicare non cambia il tier, cambia
                #: lo stato
                tier=None,
                size_bytes=os.path.getsize(percorso))
        except Exception as exc:                       # noqa: BLE001
            self.report({'ERROR'}, f"Published, but the event failed: {exc}")
            return {'CANCELLED'}

        context.scene.em_resources.status = (
            f"Published → {caricato['s3_uri']}")
        self.report({'INFO'}, f"{self.resource_id} → {caricato['s3_uri']}")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_move_citations(Operator):
    """Move the citations of an old revision to its newest one.

    MICRO risorsa-file, parte 2 — the question `replace_file` leaves to the
    caller, asked the way EMStudio asks it: every citation (an RM, a document,
    a property) is listed with «all» as the proposal; the DTC chain of the old
    bytes (`dtc_had_output`…) is shown as staying, and never moves."""

    bl_idname = "em.move_citations"
    bl_label = "Move citations to the new revision"
    bl_options = {'REGISTER', 'UNDO'}

    old_id: bpy.props.StringProperty()  # type: ignore
    new_id: bpy.props.StringProperty()  # type: ignore
    choices: bpy.props.CollectionProperty(type=properties.EM_CitationChoice)  # type: ignore
    staying: bpy.props.StringProperty()  # type: ignore

    def invoke(self, context, event):
        from .. import resource_revisions as rr
        ok, graph, _f, _g = _active(context)
        if not ok:
            return {'CANCELLED'}
        citing, staying = rr.split_pointers(rr.pointing_at(graph, self.old_id))
        self.choices.clear()
        for ptr in citing:
            src = graph.find_node_by_id(ptr["source"])
            item = self.choices.add()
            item.edge_id = ptr["edge_id"]
            item.label = (f"{getattr(src, 'name', ptr['source'])} "
                          f"─{ptr['edge_type']}→")
            item.move = True
        self.staying = ", ".join(sorted({p["edge_type"] for p in staying}))
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text=f"{self.old_id} → {self.new_id}", icon='FILE_REFRESH')
        for item in self.choices:
            col.prop(item, "move", text=item.label)
        if self.staying:
            col.separator()
            col.label(text=f"Stays with the old bytes: {self.staying}", icon='LINKED')

    def execute(self, context):
        from .. import resource_revisions as rr
        ok, graph, _f, _g = _active(context)
        if not ok:
            return {'CANCELLED'}
        if len(self.choices):
            chosen = [c.edge_id for c in self.choices if c.move]
        else:   # called without the dialog: «all» is the proposal
            chosen = [p["edge_id"] for p in rr.split_pointers(
                rr.pointing_at(graph, self.old_id))[0]]
        moved = rr.move_citations(graph, self.old_id, self.new_id, chosen)
        self.report({'INFO'}, f"{moved} citation(s) moved to {self.new_id}")
        for area in context.screen.areas:
            area.tag_redraw()
        return {'FINISHED'}


def _entry_point(graph, resource_id):
    try:
        from s3dgraphy import api
        files = api.resource_files(graph, resource_id)
    except Exception:                              # noqa: BLE001 — older wheel
        return ""
    door = next((f for f in files if f.get("role") == "entry_point"), None)
    return str((door or {}).get("path") or "")


def stamped_resources(context, graph):
    """``[(resource, path, seal)]`` for the local resources with a ``.stamp.json``
    beside them (``resource_seal.seal_of``). The locator is resolved against the
    same bases as the publication (D5), so a DosCo-relative one is found."""
    from .. import publication_gesture as pg
    from .. import resource_seal
    from ..rm_manager.containers import basi_dei_locator
    basi = basi_dei_locator(context)
    out = []
    for r in resource_backend.list_link_resources(graph):
        locator = r["locator"]
        if not locator:
            #: a file set keeps no url of its own: its door is the entry_point
            #: among its files (has_file), and the stamp sits beside the door
            locator = _entry_point(graph, r["id"])
        if not locator or resource_backend._locator_kind(locator) != "local_path":
            continue
        path = pg.risolvi(locator, basi) or locator
        seal = resource_seal.seal_of(path)
        if seal is not None:
            out.append((r, path, seal))
    #: VLONG-DEV27/D4 · the seal opened from a Shelf row (not a graph resource)
    p = getattr(getattr(context, "scene", None), "em_resources", None)
    extra = getattr(p, "seal_extra_path", "") if p is not None else ""
    if extra and not any(r["id"] == p.seal_extra_id for r, _x, _y in out):
        seal = resource_seal.seal_of(extra)
        if seal is not None:
            out.append(({"id": p.seal_extra_id, "name": p.seal_extra_name,
                         "locator": extra, "kind": "local_path"}, extra, seal))
    return out


def stamp_path_of_resource(context, graph, resource_id, url, *, basi=None):
    """The ``.stamp.json`` beside a graph resource's file, or ``""`` — for the
    small seal on a row (VLONG-DEV27/D4). Only an ``isfile``: the check (which
    hashes) is the Seals card's, once it is opened."""
    from .. import publication_gesture as pg
    from .. import resource_seal
    from ..rm_manager.containers import basi_dei_locator
    locator = url or _entry_point(graph, resource_id)
    if not locator or resource_backend._locator_kind(locator) != "local_path":
        return ""
    if basi is None:
        basi = basi_dei_locator(context)
    path = pg.risolvi(locator, basi) or locator
    return resource_seal.find_stamp(path) or ""


def draw_seal_button(layout, resource_id, *, path="", name=""):
    """The small seal beside a stamped resource: a click opens its card in
    Resources & Shelf ▸ Seals (the panel of ``cfd0df7``)."""
    from ..icons_manager import get_custom_icon
    icon = get_custom_icon("seal")
    kw = {"icon_value": icon} if icon else {"icon": 'KEYTYPE_KEYFRAME_VEC'}
    op = layout.operator("em.seal_show", text="", emboss=False, **kw)
    op.resource_id = resource_id
    op.path = path
    op.name = name


class EM_OT_seal_show(Operator):
    """This resource is stamped: open its seal in Resources & Shelf ▸ Seals"""
    bl_idname = "em.seal_show"
    bl_label = "Show the seal"
    bl_options = {'INTERNAL'}

    resource_id: bpy.props.StringProperty()  # type: ignore
    #: the file beside which the stamp sits, for a Shelf entry
    path: bpy.props.StringProperty()  # type: ignore
    name: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        p = context.scene.em_resources
        p.show_seals = True
        p.active_seal = self.resource_id
        if self.path:
            p.seal_extra_id = self.resource_id
            p.seal_extra_name = self.name
            p.seal_extra_path = self.path
        for area in context.screen.areas if context.screen else ():
            area.tag_redraw()
        return {'FINISHED'}


class EM_OT_seal_open(Operator):
    """Open (or close) the seal of this resource"""
    bl_idname = "em.seal_open"
    bl_label = "Seal"
    bl_options = {'INTERNAL'}

    resource_id: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        p = context.scene.em_resources
        p.active_seal = "" if p.active_seal == self.resource_id else self.resource_id
        return {'FINISHED'}


class EM_OT_seal_copy_json(Operator):
    """Copy this resource's .stamp.json to the clipboard, as it is on disk"""
    bl_idname = "em.seal_copy_json"
    bl_label = "Copy JSON"
    bl_options = {'INTERNAL'}

    resource_id: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        ok, graph, _folder, _gc = _active(context)
        if not ok:
            return {'CANCELLED'}
        for r, _path, seal in stamped_resources(context, graph):
            if r["id"] == self.resource_id and seal.get("raw"):
                context.window_manager.clipboard = seal["raw"]
                self.report({'INFO'}, f"Copied {os.path.basename(seal['stamp_path'])}")
                return {'FINISHED'}
        self.report({'WARNING'}, f"{self.resource_id}: no readable stamp")
        return {'CANCELLED'}


class EM_OT_seal_verify_again(Operator):
    """Check the bytes against the stamps again (results are kept until a file changes)"""
    bl_idname = "em.seal_verify_again"
    bl_label = "Verify again"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        from .. import resource_seal
        resource_seal.forget()
        for area in context.screen.areas if context.screen else ():
            area.tag_redraw()
        return {'FINISHED'}


classes = (
    EM_OT_seal_open,
    EM_OT_seal_show,
    EM_OT_seal_copy_json,
    EM_OT_seal_verify_again,
    EM_OT_move_citations,
    EM_OT_resources_scan,
    EM_OT_resources_set_dosco_folder,
    EM_OT_resources_hat_document,
    EM_OT_resources_promote_minio,
    EM_OT_publish_distribution,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
