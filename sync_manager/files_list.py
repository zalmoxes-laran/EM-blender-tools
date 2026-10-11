"""Storage · the files of the graph as a LIST you can select and filter.

The «Files» section used to be a column of rows drawn one by one: nothing to
select, nothing to filter but the six state chips. A resource here has more
lives than a file: an ASSET (the master) has VERSIONS (LOD0, LOD1 … made by a
`lod_generation` process, `dtc_derived_from` the master), each version has a
TIER (master | distribution) and a list of USES (analysis, realtime, web …),
and a resource that is a SET holds FILES (`has_file`). A representation model
(RM) links the resource it shows (`has_linked_resource`); the RM CONTAINER is
only Blender's wrapper of several meshes under one document and holds no file.

So a row says WHAT it is (master / version / file of a set / link of a
document), its LEVEL and USES, its state (the sign of the common list) and the
RM that use it; the card under the list says where it is and lists its sibling
versions. The list is rebuilt by «Check files», from the same results.

``build_rows`` is plain Python over the graph (testable without Blender); the
classes below are the Blender face of it.
"""


from typing import Any, Dict, List, Optional

KINDS = (("all", "All kinds", "Every row"),
         ("master", "Masters", "The assets: the surveyed or authored source"),
         ("version", "Versions", "LODs and other versions derived from a master"),
         ("file", "Files of a set", "One file of a resource that is a set"),
         ("link", "Links", "A resource a document or a model points to"))

_RANK = {"master": 0, "version": 1, "file": 2, "link": 3}
_RM_TYPES = ("representation_model", "representation_model_doc", "representation_model_sf")


def _live_edges(graph) -> List[Any]:
    return [e for e in (getattr(graph, "edges", None) or [])
            if not ((getattr(e, "attributes", None) or {}).get("removed"))]


def _data(node) -> Dict[str, Any]:
    d = getattr(node, "data", None)
    return d if isinstance(d, dict) else {}


def _level_key(level: str) -> int:
    digits = "".join(c for c in str(level or "") if c.isdigit())
    return int(digits) if digits else 99


def build_rows(graph, results: List[Dict[str, Any]],
               described: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """One row per resolved resource, grouped by asset: the master, its versions
    by level, the files of each set under it. Every row is a dict of strings
    (what the UIList shows and filters), never a node."""
    from s3dgraphy.resources import versions as V
    described = described or {}
    nodes = {n.node_id: n for n in getattr(graph, "nodes", [])}
    edges = _live_edges(graph)
    set_of = {e.edge_target: e.edge_source for e in edges if e.edge_type == "has_file"}
    used_by: Dict[str, List[str]] = {}
    for e in edges:
        if e.edge_type == "has_linked_resource":
            src = nodes.get(e.edge_source)
            if src is not None and str(getattr(src, "node_type", "")) in _RM_TYPES:
                used_by.setdefault(e.edge_target, []).append(str(src.name))

    rows: List[Dict[str, Any]] = []
    for r in results:
        rid = r["id"]
        node = nodes.get(rid)
        d = _data(node)
        is_file = str(r.get("node_type") or getattr(node, "node_type", "")) == "resource_file"
        owner_id = set_of.get(rid) if is_file else None
        owner = nodes.get(owner_id) if owner_id else None
        owner_d = _data(owner)
        tier = str(d.get("tier") or owner_d.get("tier") or "")
        kind = ("file" if is_file else
                "master" if tier == "master" else
                "version" if tier == "distribution" else "link")
        subject = owner_id or rid
        try:
            asset_id = V.asset_of(graph, subject)
        except Exception:  # noqa: BLE001 — a resource outside any chain is its own asset
            asset_id = subject
        asset = nodes.get(asset_id)
        try:
            level = V.lod_level_of(graph, subject) or ""
        except Exception:  # noqa: BLE001
            level = ""
        raw_use = d.get("use") if d.get("use") is not None else owner_d.get("use")
        uses = [str(u) for u in (raw_use or [])] if isinstance(raw_use, (list, tuple)) \
            else ([str(raw_use)] if raw_use else [])
        said = described.get(rid) or {}
        file = said.get("file") or r.get("name") or rid[:8]
        if file.lower().endswith(".blend") and getattr(node, "name", ""):
            file = str(node.name)       # an object of a .blend: the name of the object says more
        rms = used_by.get(rid, []) + (used_by.get(owner_id, []) if owner_id else [])
        where = r.get("path") or ""
        if not where:
            where = str(d.get("url") or "") or next(
                (str(a.get("locator")) for a in (d.get("addresses") or [])
                 if isinstance(a, dict) and a.get("locator")), "")
        tag = {"master": "master",
               "version": (level or "version") + (" · " + ", ".join(uses) if uses else ""),
               "file": "file of a set", "link": "link"}[kind]
        asset_name = str(getattr(asset, "name", "") or asset_id)
        rows.append({
            "id": rid, "file": file, "doc": said.get("doc") or "", "asset": asset_name,
            "kind": kind, "tier": tier, "level": level, "use": ",".join(uses),
            "state": r.get("state") or "", "where": where, "tag": tag,
            "rm": ", ".join(dict.fromkeys(rms)),
            "search": " ".join([file, said.get("doc") or "", asset_name, tier, level,
                                " ".join(uses), " ".join(rms), kind]).lower(),
            "_order": (asset_name.lower(), asset_id, _RANK[kind], _level_key(level), file.lower()),
        })
    rows.sort(key=lambda x: x["_order"])
    for x in rows:
        del x["_order"]
    return rows


def siblings(rows: List[Dict[str, Any]], row: Dict[str, Any]) -> List[int]:
    """Indexes of the other rows of the same asset (its master, versions, files)."""
    return [i for i, x in enumerate(rows) if x["asset"] == row["asset"] and x["id"] != row["id"]]


# ── the Blender face ────────────────────────────────────────────────────────

_CLASSES: tuple = ()


def _classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EMFileRow(bpy.types.PropertyGroup):
        id: bpy.props.StringProperty()  # type: ignore
        file: bpy.props.StringProperty()  # type: ignore
        doc: bpy.props.StringProperty()  # type: ignore
        asset: bpy.props.StringProperty()  # type: ignore
        kind: bpy.props.StringProperty()  # type: ignore
        tier: bpy.props.StringProperty()  # type: ignore
        level: bpy.props.StringProperty()  # type: ignore
        use: bpy.props.StringProperty()  # type: ignore
        state: bpy.props.StringProperty()  # type: ignore
        where: bpy.props.StringProperty()  # type: ignore
        tag: bpy.props.StringProperty()  # type: ignore
        rm: bpy.props.StringProperty()  # type: ignore
        search: bpy.props.StringProperty()  # type: ignore

    class EM_UL_files(bpy.types.UIList):
        def draw_item(self, context, layout, data, item, icon, active_data, active_prop, index):
            from ..state_symbols import sign
            ic, _text, _meaning = sign("file." + item.state)
            row = layout.row(align=True)
            row.alert = item.state in ("missing", "empty_copy")
            if item.kind in ("version", "file"):
                row.label(text="", icon="BLANK1")          # a version hangs under its asset
            row.label(text=item.file, icon=ic)
            sub = row.row(align=True)
            sub.active = item.kind != "link"
            sub.alignment = "RIGHT"
            sub.label(text=item.tag)

        def draw_filter(self, context, layout):
            layout.label(text="Filters are above the list.", icon="INFO")

        def filter_items(self, context, data, propname):
            from . import file_states
            wm = context.window_manager
            items = getattr(data, propname)
            state = file_states.ULTIMI.get("filter") or ""
            kind = getattr(wm, "em_files_kind", "all")
            kind = "" if kind == "all" else kind
            use = getattr(wm, "em_files_use", "all")
            use = "" if use == "all" else use
            words = (getattr(wm, "em_files_query", "") or "").lower().split()
            flags = [self.bitflag_filter_item] * len(items)
            for i, it in enumerate(items):
                ok = ((not state or it.state == state) and (not kind or it.kind == kind)
                      and (not use or use in it.use.split(","))
                      and all(w in it.search for w in words))
                if not ok:
                    flags[i] = 0
            return flags, []

    class EM_OT_files_select(bpy.types.Operator):
        """Select this row of the list"""
        bl_idname = "em.files_select"
        bl_label = "Select"
        bl_options = {"INTERNAL"}
        index: bpy.props.IntProperty()  # type: ignore

        def execute(self, context):
            context.window_manager.em_files_index = self.index
            return {"FINISHED"}

    return (EMFileRow, EM_UL_files, EM_OT_files_select)


def fill(context, rows: List[Dict[str, Any]]) -> None:  # pragma: no cover — bpy
    """Rebuild the list (keeping the selected row when it is still there)."""
    wm = context.window_manager
    keep = ""
    try:
        keep = wm.em_files[wm.em_files_index].id
    except (IndexError, AttributeError):
        pass
    wm.em_files.clear()
    for x in rows:
        it = wm.em_files.add()
        for k, v in x.items():
            setattr(it, k, str(v))
    wm.em_files_index = next((i for i, x in enumerate(rows) if x["id"] == keep), 0)


def _use_items(_self, _context):  # pragma: no cover — bpy
    try:
        from s3dgraphy.resources.versions import USES
    except Exception:  # noqa: BLE001
        USES = ()
    return [("all", "All uses", "Every use")] + [(u, u.replace("_", " "), "") for u in USES]


def _picked(self, context):  # pragma: no cover — bpy
    """Selecting a row shows its «Where it comes from» card, as the button did."""
    try:
        self.em_provenance_resource = self.em_files[self.em_files_index].id
    except (IndexError, AttributeError):
        pass


def draw(layout, context, results) -> None:  # pragma: no cover — bpy
    """The list, its filters, and the card of the selected row."""
    import bpy  # type: ignore
    from . import file_states
    from . import room as room_cfg
    from ..state_symbols import sign
    wm = context.window_manager
    q = layout.row(align=True)
    q.prop(wm, "em_files_query", text="", icon="VIEWZOOM")
    f = layout.row(align=True)
    f.prop(wm, "em_files_kind", text="")
    f.prop(wm, "em_files_use", text="")
    layout.template_list("EM_UL_files", "", wm, "em_files", wm, "em_files_index", rows=8)
    try:
        it = wm.em_files[wm.em_files_index]
    except IndexError:
        return
    card = layout.box()
    icon, text, meaning = sign("file." + it.state)
    card.label(text=it.file, icon=icon)
    col = card.column(align=True)
    col.scale_y = 0.9
    col.label(text=f"{text} — {meaning}" if meaning else text)
    if it.doc:
        col.label(text="Document: " + it.doc, icon="DOCUMENTS")
    what = {"master": "Master (asset)", "version": "Version of " + it.asset,
            "file": "File of a set of " + it.asset, "link": "Link"}.get(it.kind, it.kind)
    col.label(text=what + (f" · {it.level}" if it.level else "")
              + (f" · tier {it.tier}" if it.tier else ""), icon="OUTLINER_OB_GROUP_INSTANCE")
    if it.use:
        col.label(text="Used for: " + it.use.replace(",", ", ").replace("_", " "), icon="SHADERFX")
    if it.rm:
        col.label(text="Shown by: " + it.rm, icon="MESH_CUBE")
    res = next((r for r in file_states.ULTIMI.get("results") or [] if r["id"] == it.id), None)
    for p in (res or {}).get("positions") or []:
        mark = {True: "✓", False: "✗"}.get(p.get("ok"), "?")
        col.label(text=f"{mark} {p.get('kind')}: {p.get('where') or '—'}", icon="BLANK1")
    if not (res or {}).get("positions") and it.where:
        col.label(text=it.where, icon="URL")
    near = [i for i, x in enumerate(wm.em_files) if x.asset == it.asset and x.id != it.id]
    if near:
        col.separator()
        col.label(text=f"Same asset · {len(near)}:", icon="LINKED")
        for i in near[:8]:
            x = wm.em_files[i]
            row = col.row(align=True)
            row.operator("em.files_select", text=f"{x.file}  ({x.tag})",
                         icon=sign("file." + x.state)[0], emboss=False).index = i
        if len(near) > 8:
            col.label(text=f"… and {len(near) - 8} more (filter by name)")
    acts = card.row(align=True)
    if it.state in ("missing", "empty_copy"):
        acts.operator("em.files_find_here", text="Find here…", icon="VIEWZOOM").resource_id = it.id
    if it.state == "on_disk" and room_cfg.room().get("room_id"):
        acts.operator("em.files_upload", text="Upload", icon="EXPORT").resource_id = it.id
    if it.state == "on_node":
        acts.operator("em.files_keep", text="Keep here", icon="IMPORT").resource_id = it.id
    if res and res.get("path"):
        acts.operator("em.files_open_where", text="Open where it is",
                      icon="FILEBROWSER").path = res["path"]


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    wm = bpy.types.WindowManager
    wm.em_files = bpy.props.CollectionProperty(type=_CLASSES[0])
    wm.em_files_index = bpy.props.IntProperty(update=_picked)
    wm.em_files_query = bpy.props.StringProperty(
        name="Search", description="Words of the file, document, asset, level, use or model")
    wm.em_files_kind = bpy.props.EnumProperty(name="Kind", items=KINDS)
    wm.em_files_use = bpy.props.EnumProperty(name="Use", items=_use_items)


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    wm = bpy.types.WindowManager
    for name in ("em_files", "em_files_index", "em_files_query", "em_files_kind", "em_files_use"):
        if hasattr(wm, name):
            delattr(wm, name)
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
