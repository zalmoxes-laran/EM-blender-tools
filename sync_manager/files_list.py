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
import os

KINDS = (("all", "All kinds", "Every row"),
         ("master", "Masters", "The assets: the surveyed or authored source"),
         ("version", "Versions", "LODs and other versions derived from a master"),
         ("file", "Files of a set", "One file of a resource that is a set"),
         ("link", "Links", "A resource a document or a model points to"))

def build_rows(graph, results: List[Dict[str, Any]],
               described: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """The rows of the list: ``s3dgraphy.api.storage_rows`` (the same grouping
    EMStudio draws), with the lists written as text for the Blender properties.
    ``described`` is no longer needed: the library names the file and its document."""
    from s3dgraphy import api
    rows = api.storage_rows(graph, results)
    for x in rows:
        x["use"] = ",".join(x["use"])
        x["rm"] = ", ".join(x["rm"])
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
            from . import file_states
            b = (file_states.ULTIMI.get("bucket") or {}).get(item.id)
            if b:
                row.label(text=BUCKET_SIGN.get(b["state"], ("?", ""))[0])
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

    class EM_OT_files_find_moved(bpy.types.Operator):
        """Find moved files: look for the files that are not here any more in a
        folder (by their sha256, then by name and size). It only proposes."""
        bl_idname = "em.files_find_moved"
        bl_label = "Find moved files…"
        directory: bpy.props.StringProperty(subtype="DIR_PATH")  # type: ignore

        def invoke(self, context, event):
            from . import file_states
            self.directory = file_states.project_root(context) or (
                os.path.dirname(bpy.data.filepath) if bpy.data.filepath else "")
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}

        def execute(self, context):
            from s3dgraphy import api
            from . import file_states
            from ..functions import is_graph_available
            from .asset_upload import sha256_of_file
            ok, graph = is_graph_available(context)
            if not ok or graph is None or not file_states.ULTIMI.get("results"):
                self.report({"ERROR"}, "«Check files» first: the search is for the ones it found missing")
                return {"CANCELLED"}
            folders = [bpy.path.abspath(self.directory)] if self.directory else []
            folders += [d for d in (file_states.project_root(context),) if d]
            found = api.find_moved_files(graph, file_states.ULTIMI["results"], list(dict.fromkeys(folders)),
                                         hasher=sha256_of_file, max_hash_bytes=1 << 30)
            file_states.ULTIMI["moved"] = found
            lost = sum(1 for r in file_states.ULTIMI["results"] if r["state"] in ("missing", "empty_copy"))
            self.report({"INFO"}, f"{len(found)} of {lost} missing files have a candidate")
            return {"FINISHED"}

    class EM_OT_files_relink_moved(bpy.types.Operator):
        """Point this file at where it was found (one file, or every sure one)"""
        bl_idname = "em.files_relink_moved"
        bl_label = "Relink"
        resource_id: bpy.props.StringProperty(default="")  # type: ignore
        path: bpy.props.StringProperty(default="")  # type: ignore

        def execute(self, context):
            from . import file_states
            from ..functions import is_graph_available
            ok, graph = is_graph_available(context)
            if not ok or graph is None:
                return {"CANCELLED"}
            done = 0
            for item in list(file_states.ULTIMI.get("moved") or []):
                if self.resource_id and item["id"] != self.resource_id:
                    continue
                best = item["matches"][0]
                path = self.path if self.resource_id else best["path"]
                if not self.resource_id and best["how"] not in ("exact", "exact_renamed"):
                    continue                       # «all» relinks only the sure ones
                file_states.relink(graph, item["id"], path)
                done += 1
            sure = ("exact", "exact_renamed")
            file_states.ULTIMI["moved"] = [
                x for x in file_states.ULTIMI.get("moved") or []
                if (x["id"] != self.resource_id if self.resource_id else x["matches"][0]["how"] not in sure)]
            file_states.resolve_active(context, graph)
            self.report({"INFO"}, f"relinked {done} file(s)")
            return {"FINISHED"}

    def _store_or_report(op):
        """The object store the S3_* environment names, or the reason it is not
        there — said where the person looks."""
        from s3dgraphy import api
        from s3dgraphy.resources.object_store import StoreError
        try:
            return api.open_object_store()
        except StoreError as exc:
            op.report({"ERROR"}, f"Object store: {exc}")
        except Exception as exc:  # noqa: BLE001
            op.report({"ERROR"}, f"Object store: {exc}")
        return None

    def _needs_config(op) -> bool:
        if not os.environ.get("S3_ENDPOINT") or not os.environ.get("S3_BUCKET"):
            op.report({"ERROR"}, "No bucket configured: Blender's environment has no S3_ENDPOINT / "
                      "S3_BUCKET / S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY (the same variables "
                      "Heriverse uses). Start Blender from a terminal with them set.")
            return True
        return False

    class EM_OT_files_bucket_check(bpy.types.Operator):
        """Compare each file's disk copy with its bucket copy: quick (existence and
        size) or «Verify bytes» (the bucket's bytes are read and their sha256 compared)"""
        bl_idname = "em.files_bucket_check"
        bl_label = "Check the bucket"
        deep: bpy.props.BoolProperty(default=False)  # type: ignore

        def execute(self, context):
            from s3dgraphy import api
            from . import file_states
            from .asset_upload import sha256_of_file
            from ..functions import is_graph_available
            ok, graph = is_graph_available(context)
            if not ok or graph is None or not file_states.ULTIMI.get("results"):
                self.report({"ERROR"}, "«Check files» first")
                return {"CANCELLED"}
            if _needs_config(self):
                return {"CANCELLED"}
            store = _store_or_report(self)
            if store is None:
                return {"CANCELLED"}
            try:
                rows = api.bucket_alignment(graph, file_states.ULTIMI["results"], store,
                                            deep=self.deep, hasher=sha256_of_file)
            except Exception as exc:  # noqa: BLE001 — the reason is the person's
                self.report({"ERROR"}, f"Bucket: {exc}")
                return {"CANCELLED"}
            file_states.ULTIMI["bucket"] = {r["id"]: r for r in rows}
            tally: Dict[str, int] = {}
            for r in rows:
                tally[r["state"]] = tally.get(r["state"], 0) + 1
            self.report({"INFO"}, "Bucket: " + (", ".join(f"{n} {k.replace('_', ' ')}"
                                                           for k, n in tally.items()) or "nothing to compare"))
            return {"FINISHED"}

    class EM_OT_files_bucket_promote(bpy.types.Operator):
        """Upload this file to the bucket, read it back and compare: only a verified
        copy is recorded (the bucket becomes the main address; the disk path stays as
        another address)"""
        bl_idname = "em.files_bucket_promote"
        bl_label = "Upload to the bucket"
        resource_id: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            from s3dgraphy import api
            from . import file_states
            from .asset_upload import sha256_of_file
            from ..functions import is_graph_available
            ok, graph = is_graph_available(context)
            row = next((r for r in file_states.ULTIMI.get("results") or [] if r["id"] == self.resource_id), None)
            if not ok or graph is None or not row or not row.get("path"):
                self.report({"ERROR"}, "no file on the disk to upload")
                return {"CANCELLED"}
            if _needs_config(self):
                return {"CANCELLED"}
            store = _store_or_report(self)
            if store is None:
                return {"CANCELLED"}
            try:
                out = api.promote_to_bucket(graph, self.resource_id, row["path"], store,
                                            hasher=sha256_of_file)
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, f"Upload refused: {exc}")
                return {"CANCELLED"}
            self.report({"INFO"}, f"in the bucket, bytes verified: {out['bucket']}")
            file_states.resolve_active(context, graph)
            return {"FINISHED"}

    class EM_OT_files_free_local(bpy.types.Operator):
        """Free the disk copy of files the bucket holds, byte for byte"""
        bl_idname = "em.files_free_local"
        bl_label = "Free local copies…"
        confirm_masters: bpy.props.BoolProperty(
            name="Also masters and originals", default=False,
            description="Masters and original documents cannot be remade")  # type: ignore
        permanent: bpy.props.BoolProperty(
            name="Delete permanently", default=False,
            description="Off: the files are moved to a .em_freed folder, where you can take them back")  # type: ignore

        def _plan(self, context):
            from s3dgraphy import api
            from . import file_states
            from ..functions import is_graph_available
            ok, graph = is_graph_available(context)
            rows = list((file_states.ULTIMI.get("bucket") or {}).values())
            root = file_states.project_root(context)
            protect = [os.path.join(root, ".em_cache")] if root else []
            return api.plan_free_local(graph, rows, protect=protect) if ok and graph else []

        def invoke(self, context, event):
            self.plan = self._plan(context)
            if not self.plan:
                self.report({"WARNING"}, "Nothing to free: run «Verify bytes» first — only files "
                            "proved identical in the bucket can be freed")
                return {"CANCELLED"}
            return context.window_manager.invoke_props_dialog(self, width=560)

        def draw(self, context):
            plan = getattr(self, "plan", None) or self._plan(context)
            safe = [p for p in plan if p["level"] == "safe"]
            conf = [p for p in plan if p["level"] == "confirm"]
            mb = lambda items: sum(p["size"] for p in items) / 1e6   # noqa: E731
            col = self.layout.column()
            box = col.box()
            box.alert = True
            box.label(text="WARNING — this removes files from your disk.", icon="ERROR")
            for line in ("The bucket's bytes are compared with each file again just before it goes.",
                         "Derived versions (LODs, GLBs) can be remade from their master.",
                         "A master or an original cannot be remade by anyone:",
                         "keep at least one other independent copy of it (another disk, a backup)."):
                box.label(text=line)
            col.label(text=f"Derived versions: {len(safe)} ({mb(safe):.0f} MB)", icon="CHECKMARK")
            col.label(text=f"Masters and originals: {len(conf)} ({mb(conf):.0f} MB)", icon="ERROR")
            col.prop(self, "confirm_masters")
            col.prop(self, "permanent")
            if self.permanent:
                w = col.box()
                w.alert = True
                w.label(text="Permanent: the files are NOT moved anywhere; there is no way back.", icon="CANCEL")
            if self.confirm_masters and any(p["copies"] == 0 for p in conf):
                w = col.box()
                w.alert = True
                w.label(text=f"{sum(1 for p in conf if p['copies'] == 0)} of them have no copy "
                             "but the bucket's.", icon="ERROR")

        def execute(self, context):
            import time
            from s3dgraphy import api
            from . import file_states
            from .asset_upload import sha256_of_file
            from ..functions import is_graph_available
            plan = getattr(self, "plan", None) or self._plan(context)
            if _needs_config(self):
                return {"CANCELLED"}
            store = _store_or_report(self)
            if store is None:
                return {"CANCELLED"}
            root = file_states.project_root(context) or (
                os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.expanduser("~"))
            quarantine = os.path.join(root, ".em_freed", time.strftime("%Y-%m-%d_%H%M%S"))
            report = api.free_local_copies(plan, store, confirm_masters=self.confirm_masters,
                                           permanent=self.permanent, quarantine=quarantine,
                                           hasher=sha256_of_file)
            n = {k: sum(1 for r in report if r["action"] == k)
                 for k in ("freed", "quarantined", "refused", "skipped")}
            mb = sum(r["bytes"] for r in report) / 1e6
            self.report({"WARNING" if n["refused"] else "INFO"},
                        f"{n['freed'] + n['quarantined']} freed ({mb:.0f} MB)"
                        + (f", moved to {quarantine}" if n["quarantined"] else "")
                        + (f"; {n['refused']} refused (see the log)" if n["refused"] else "")
                        + (f"; {n['skipped']} left (masters)" if n["skipped"] else ""))
            for r in report:
                if r["action"] == "refused":
                    print(f"[free local] refused {r['path']}: {r['reason']}")
            ok, graph = is_graph_available(context)
            if ok and graph:
                file_states.resolve_active(context, graph)
            file_states.ULTIMI["bucket"] = {}
            return {"FINISHED"}

    return (EMFileRow, EM_UL_files, EM_OT_files_select, EM_OT_files_find_moved,
            EM_OT_files_relink_moved, EM_OT_files_bucket_check, EM_OT_files_bucket_promote,
            EM_OT_files_free_local)


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
            if k in it.bl_rna.properties:
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
    draw_moved(layout, context)
    draw_bucket(layout, context)
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
    b = (file_states.ULTIMI.get("bucket") or {}).get(it.id)
    if b:
        sg = BUCKET_SIGN.get(b["state"], ("?", b["state"]))
        col.label(text=f"Bucket: {sg[0]} {sg[1]}" + (f" — {b['note']}" if b.get("note") else ""),
                  icon="WORLD")
        if b.get("bucket"):
            col.label(text=b["bucket"], icon="BLANK1")
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
    if it.state in ("on_disk", "both") and not (b and b["state"] in ("aligned", "same_size")):
        acts.operator("em.files_bucket_promote", text="To the bucket", icon="EXPORT").resource_id = it.id
    if it.state == "on_node":
        acts.operator("em.files_keep", text="Keep here", icon="IMPORT").resource_id = it.id
    if res and res.get("path"):
        acts.operator("em.files_open_where", text="Open where it is",
                      icon="FILEBROWSER").path = res["path"]


def draw_moved(layout, context) -> None:  # pragma: no cover — bpy
    """«Find moved files…», and what it found: the candidate of each, how it was
    recognised, and the gesture to relink it."""
    from . import file_states
    lost = [r for r in file_states.ULTIMI.get("results") or []
            if r["state"] in ("missing", "empty_copy")]
    moved = file_states.ULTIMI.get("moved") or []
    if not lost and not moved:
        return
    box = layout.box()
    head = box.row(align=True)
    head.label(text=f"Not here: {len(lost)}", icon="ERROR")
    head.operator("em.files_find_moved", text="Find moved files…", icon="VIEWZOOM")
    if not moved:
        return
    sure = sum(1 for x in moved if x["matches"][0]["how"] in ("exact", "exact_renamed"))
    if sure:
        box.operator("em.files_relink_moved", text=f"Relink the {sure} sure ones",
                     icon="LINKED").resource_id = ""
    said = {"exact": "same bytes", "exact_renamed": "same bytes, other name",
            "probable": "same name and size", "possible": "same name only"}
    for x in moved[:12]:
        m = x["matches"][0]
        col = box.column(align=True)
        row = col.row(align=True)
        row.label(text=x.get("name") or x["id"][:8], icon="FILE")
        op = row.operator("em.files_relink_moved", text="Relink", icon="LINKED")
        op.resource_id, op.path = x["id"], m["path"]
        sub = col.row()
        sub.active = False
        sub.label(text=f"{said.get(m['how'], m['how'])}: {m['path']}"
                  + (f"  (+{len(x['matches']) - 1})" if len(x["matches"]) > 1 else ""))
    if len(moved) > 12:
        box.label(text=f"… and {len(moved) - 12} more")


#: the sign beside a file for how its disk and bucket copies stand
BUCKET_SIGN = {"aligned": ("✓", "same bytes on the disk and in the bucket (verified)"),
               "same_size": ("≈", "in the bucket, same size — bytes not compared yet"),
               "differ": ("≠", "the disk and the bucket DIFFER"),
               "disk_only": ("⌂", "on the disk only: the bucket has no copy"),
               "bucket_only": ("☁", "in the bucket only: no copy on this computer"),
               "neither": ("✕", "recorded in the bucket, but not there and not on the disk"),
               "unknown": ("?", "could not compare")}


def draw_bucket(layout, context) -> None:  # pragma: no cover — bpy
    """The bucket box: check it (quick, or byte for byte), how many stand in
    each way, and the gesture that frees the disk copies the bucket proves."""
    from . import file_states
    box = layout.box()
    head = box.row(align=True)
    head.label(text="Bucket", icon="WORLD")
    head.operator("em.files_bucket_check", text="Check", icon="FILE_REFRESH").deep = False
    head.operator("em.files_bucket_check", text="Verify bytes", icon="CHECKMARK").deep = True
    rows = file_states.ULTIMI.get("bucket") or {}
    if not rows:
        box.label(text="Not checked: it compares each file's disk copy with its bucket copy.", icon="INFO")
        return
    tally: Dict[str, int] = {}
    for r in rows.values():
        tally[r["state"]] = tally.get(r["state"], 0) + 1
    grid = box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
    for k in ("aligned", "same_size", "differ", "disk_only", "bucket_only", "neither", "unknown"):
        if tally.get(k):
            g = grid.row()
            g.alert = k in ("differ", "neither")
            g.label(text=f"{BUCKET_SIGN[k][0]} {tally[k]} {k.replace('_', ' ')}")
    if tally.get("aligned"):
        box.operator("em.files_free_local", text=f"Free the disk copy of {tally['aligned']} verified files…",
                     icon="TRASH")


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
