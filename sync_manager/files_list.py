"""Files (was Storage) · the files of the graph as a LIST you can select and filter.

MICRO tre pannelli (13 Oct 2026): each thing said once, each gesture where it
serves. The head is one sentence that keeps itself up to date («8 files · 2
only on the node», Download, ↻); one search with its menu (kind, where,
Withdrawn); a row is a sign, a name, «v3/3» when its versions have different
bytes, ✕; the card says the state, the versions, only the gestures possible
now, and the Details — codes and where it comes from — closed. The bucket and
the project folder are Project storage's (`resources_tab/ui.py`).

What follows is how the list was born:

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
versions. The list is rebuilt with every check of the files (by itself, or ↻).

``build_rows`` is plain Python over the graph (testable without Blender); the
classes below are the Blender face of it.
"""


from typing import Any, Dict, List, Optional
import os
import re

#: the filter menu beside the search (MICRO tre pannelli, 13 Oct 2026: three
#: filters for five rows became one search and one menu) — what a resource is…
KINDS = (("all", "Every kind", "Every resource"),
         ("proxy", "Proxies", "The proxy of a unit"),
         ("rm", "Models (RM)", "The model of a representation model"),
         ("document", "Documents", "The file of a document"),
         ("other", "Other files", "Everything else"))

#: …and where its bytes are; «Withdrawn» shows what the room keeps to undo
STATES = (("all", "Anywhere", "Every resource"),
          ("here", "On this computer", "Its bytes are on this computer"),
          ("on_node", "Only on the node", "On the node, not on this computer yet"),
          ("missing", "Missing", "Neither here nor on the node"),
          ("withdrawn", "Withdrawn", "Withdrawn from the room: Undo brings them back"))

#: a state of the menu → the states of the one resolver it gathers
STATE_OF_FILTER = {"here": ("on_disk", "both"), "on_node": ("on_node",),
                   "missing": ("missing", "empty_copy"), "withdrawn": ("withdrawn",)}

#: where the bytes are, said in one short sentence
STATE_SENTENCE = {"on_disk": "On this computer, not on the node.",
                  "on_node": "On the node; not on this computer yet.",
                  "both": "Here and on the node.",
                  "missing": "Not found: neither here nor on the node.",
                  "empty_copy": "Not found: the copy here is empty.",
                  "reference_only": "Kept elsewhere: this study points at it.",
                  "withdrawn": "Withdrawn from the room."}


def _gov():
    try:
        from .. import resource_governance as governance
    except ImportError:              # loaded by path, outside the package (the suite)
        import resource_governance as governance
    return governance


def shown(state: str, kind: str, item_state: str, item_kind: str) -> bool:
    """Does the menu let this row through? A withdrawn row only under
    «Withdrawn», and «Withdrawn» shows only them."""
    if (item_state == "withdrawn") != (state == "withdrawn"):
        return False
    if state not in ("", "all") and item_state not in STATE_OF_FILTER.get(state, (state,)):
        return False
    return kind in ("", "all") or item_kind == kind


def summary_line(c: Dict[str, int], in_room: bool = False) -> str:
    """The head of Files, one sentence that keeps itself up to date: «8 files
    · 2 only on the node» — counted on the one resolver's results, as «Check
    files» counted them. Nothing to say → the count alone."""
    total = sum(int(n or 0) for n in c.values())
    if not total:
        return "No files in this study"
    bits = [f"{total} file{'s' if total != 1 else ''}"]
    if c.get("on_node"):
        bits.append(f"{c['on_node']} only on the node")
    lost = int(c.get("missing") or 0) + int(c.get("empty_copy") or 0)
    if lost:
        bits.append(f"{lost} missing")
    if in_room and c.get("on_disk"):
        bits.append(f"{c['on_disk']} only here")
    return " · ".join(bits)


def row_counts(rows) -> Dict[str, int]:
    """The head counts what the list shows (MICRO una verità, 13 Oct 2026:
    «11 files» over 4 rows — the resolver counted versions and parts): one
    per row, by state; withdrawn rows are not files of the study."""
    out: Dict[str, int] = {}
    for x in rows or []:
        state = x.get("state") if isinstance(x, dict) else getattr(x, "state", "")
        if state and state != "withdrawn":
            out[state] = out.get(state, 0) + 1
    return out


def build_rows(graph, results: List[Dict[str, Any]],
               described: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """The rows of the list: ``s3dgraphy.api.storage_rows`` (the same grouping
    EMStudio draws), said for a person (MICRO lo storage parla come una
    persona, 13 Oct 2026; MICRO tre pannelli, the same day):

    * **one row per resource**: its versions are not rows — the row is the
      version IN USE (the cited one), with ``versions`` «v3/4» when there are
      more, counted by their BYTES (two versions with the same bytes are one);
    * **names, never codes**: ``file`` is what the resource is for («US 2 —
      proxy», «Epoch 1 — RM», a document's title), never a digest or a UUID;
    * the files of a resource are not rows («Unnamed part» twice, measured).
    * ``what`` is what it is for the filter (proxy, rm, document, other)."""
    from s3dgraphy import api
    gov = _gov()
    rows = [x for x in api.storage_rows(graph, results) if x["kind"] != "file"]
    revs = _revisions(graph, [x["id"] for x in rows])
    kept: List[Optional[Dict[str, Any]]] = []
    chains: Dict[str, int] = {}
    for x in rows:
        r = revs.get(x["id"])
        key = r["chain"][-1] if r else x["id"]
        if key in chains:
            if r and x["id"] == r["in_use"]:     # the version in use takes the row
                kept[chains[key]] = None
                chains[key] = len(kept)
                kept.append(x)
            continue
        chains[key] = len(kept)
        kept.append(x)
    out = []
    for x in kept:
        if x is None:
            continue
        r = revs.get(x["id"])
        chain = r["chain"] if r else [x["id"]]
        if r and r["in_use"] in chain:
            x["id"] = r["in_use"]
        x["file"] = gov.readable(gov.display_name(graph, x["id"]))
        x["head"] = chain[-1]
        groups = (gov.distinct_versions(gov.versions(graph, x["id"]))
                  if len(chain) > 1 else [])
        n = next((g["n"] for g in groups if g.get("in_use")), len(groups))
        x["revs"] = max(1, len(groups))
        x["versions"] = f"v{n}/{len(groups)}" if len(groups) > 1 else ""
        x["later"] = "1" if any(g["later"] for g in groups) else ""
        x["doc"] = "" if gov.looks_like_code(x.get("doc")) else x.get("doc") or ""
        x["use"] = ",".join(x["use"])
        x["rm"] = ", ".join(x["rm"])
        x["tag"] = ""
        x["what"] = _kind(graph, x["id"])
        x["withdraw"] = "1" if gov.withdrawable(graph, x["id"]) else ""
        x["search"] = " ".join([x["file"].lower(), x["search"]])
        out.append(x)
    return out


def _kind(graph, rid):
    try:
        return _gov().kind_of(graph, rid)
    except Exception:  # noqa: BLE001 — a row is never lost to its kind
        return "other"


def withdrawn_rows(graph, records: List[Dict[str, Any]],
                   names: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """The resources withdrawn that the room keeps, as rows of the list (shown
    under «Withdrawn», in grey, with Undo where the ✕ was): ``where`` says by
    whom and when."""
    out = []
    for r in sorted(records or [], key=lambda r: r.get("at") or "", reverse=True):
        if graph is not None and graph.find_node_by_id(r.get("id") or "") is not None:
            continue                            # back in the graph: not withdrawn
        name = r.get("name") or withdrawn_name(graph, r)
        who = who_is(r.get("by") or "", names, graph)
        out.append({"id": r.get("id") or "", "file": name, "state": "withdrawn",
                    "kind": "withdrawn", "what": "", "asset": "", "doc": "", "use": "",
                    "rm": "", "tag": "", "head": "", "revs": 1, "versions": "", "later": "",
                    "where": " · ".join(b for b in (f"by {who}" if who else "",
                                                    when(r.get("at") or "")) if b),
                    "search": name.lower()})
    return out


def _revisions(graph, ids):
    try:
        return _gov().revision_info(graph, ids)
    except Exception:  # noqa: BLE001 — a list never fails on a revision it cannot read
        return {}


def when(stamp: str, today: Optional[str] = None) -> str:
    """``2026-10-13T09:24:05Z`` → «11:24» in this computer's time (Rome, +2 in
    October), «12 Oct 11:24» when it is not today. Empty for no stamp."""
    import datetime as dt
    text = str(stamp or "").strip()
    if not text:
        return ""
    try:
        at = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text[:16]
    if at.tzinfo is None:
        at = at.replace(tzinfo=dt.timezone.utc)
    local = at.astimezone()
    day = today or dt.datetime.now().astimezone().strftime("%Y-%m-%d")
    clock = local.strftime("%H:%M")
    return clock if local.strftime("%Y-%m-%d") == day else f"{local.day} {local.strftime('%b')} {clock}"


def version_line(v: Dict[str, Any], today: Optional[str] = None) -> str:
    """One version, one line: «v2 · 11:24 · Editor Due · in use»."""
    bits = [f"v{v['n']}", when(v.get("at") or "", today), v.get("by") or ""]
    if v.get("in_use"):
        bits.append("in use")
    elif v.get("later"):
        bits.append("later")
    return " · ".join(b for b in bits if b)


_ORCID = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")


def looks_like_orcid(text: Any) -> bool:
    return bool(_ORCID.search(str(text or "")))


def people(members: List[Dict[str, Any]]) -> Dict[str, str]:
    """The people of the room: their id (the ORCID the room stamps, the
    username) → the name they go by (``display``, the token's ``name``)."""
    out: Dict[str, str] = {}
    for m in members or []:
        if not isinstance(m, dict):
            continue
        name = str(m.get("display") or m.get("name") or m.get("display_name")
                   or m.get("label") or "")
        if not name or looks_like_orcid(name):
            continue
        for key in ("author", "user", "sub", "orcid", "id"):
            if m.get(key):
                out[str(m[key])] = name
    return out


def who_is(by: str, names: Optional[Dict[str, str]] = None, graph=None) -> str:
    """Who did a thing, by name: the people of the room and this Blender's
    token, then the graph's authors (their ORCID → name and surname). An ORCID
    with no name is «someone» — the code is for the Details."""
    by = str(by or "")
    if not by:
        return ""
    names = names or {}
    if names.get(by):
        return names[by]
    if graph is not None:
        for node in getattr(graph, "nodes", None) or []:
            if getattr(node, "node_type", "") not in ("author", "author_ai"):
                continue
            data = getattr(node, "data", None) or {}
            if isinstance(data, dict) and data.get("orcid") == by:
                full = " ".join(p for p in (str(data.get("name") or ""),
                                            str(data.get("surname") or ""))
                                if p and p not in ("author", "nosurname"))
                if full:
                    return full
    return "someone" if looks_like_orcid(by) or _gov().looks_like_code(by) else by


def withdrawn_name(graph, record: Dict[str, Any]) -> str:
    """What a withdrawn resource was, by what cited it (still in the graph),
    or by its own name — never its id."""
    gov = _gov()
    for src in record.get("cited_by") or []:
        said = gov.citer_name(graph, src) if graph is not None else ""
        if said:
            return said
    for node in record.get("nodes") or []:
        if node.get("id") == record.get("id"):
            return gov.readable(node.get("name"), "A resource")
    return "A resource"


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
        head: bpy.props.StringProperty()  # type: ignore
        revs: bpy.props.StringProperty()  # type: ignore
        versions: bpy.props.StringProperty()  # type: ignore
        later: bpy.props.StringProperty()  # type: ignore
        what: bpy.props.StringProperty()  # type: ignore
        withdraw: bpy.props.StringProperty()  # type: ignore

    class EM_UL_files(bpy.types.UIList):
        """One row per resource: where it is (here, on the node, both), its
        name, which version is in use of how many, and ✕ to withdraw it — or,
        withdrawn, its name in grey and Undo."""

        def draw_item(self, context, layout, data, item, icon, active_data, active_prop, index):
            row = layout.row(align=True)
            if item.state == "withdrawn":
                name = row.row(align=True)
                name.active = False
                name.label(text=item.file, icon="TRASH")
                if _may_write(context):
                    row.operator("em.files_undo_withdraw", text="Undo",
                                 icon="LOOP_BACK").record_id = item.id
                return
            from ..state_symbols import sign
            ic, _text, _meaning = sign("file." + item.state)
            row.alert = item.state in ("missing", "empty_copy")
            row.label(text=item.file, icon=ic)
            sub = row.row(align=True)
            sub.alignment = "RIGHT"
            if item.versions:
                sub.label(text=item.versions)              # «v3/4»: in use, of how many
            if item.withdraw and _may_write(context):
                sub.operator("em.files_withdraw", text="", icon="X",
                             emboss=False).resource_id = item.id

        def draw_filter(self, context, layout):
            layout.label(text="The search and its menu are above the list.", icon="INFO")

        def filter_items(self, context, data, propname):
            wm = context.window_manager
            items = getattr(data, propname)
            state = getattr(wm, "em_files_state", "all")
            kind = getattr(wm, "em_files_kind", "all")
            words = (getattr(wm, "em_files_query", "") or "").lower().split()
            flags = [self.bitflag_filter_item] * len(items)
            for i, it in enumerate(items):
                if not (shown(state, kind, it.state, it.what)
                        and all(w in it.search for w in words)):
                    flags[i] = 0
            return flags, []

    class EM_MT_files_filter(bpy.types.Menu):
        """What the list shows: the kind of resource, where its bytes are, and
        what was withdrawn"""
        bl_idname = "EM_MT_files_filter"
        bl_label = "Show"

        def draw(self, context):
            wm = context.window_manager
            col = self.layout.column()
            col.label(text="Kind")
            for key, text, _ in KINDS:
                col.prop_enum(wm, "em_files_kind", key, text=text)
            col.separator()
            col.label(text="Where")
            n = len([x for x in wm.em_files if x.state == "withdrawn"])
            for key, text, _ in STATES:
                col.prop_enum(wm, "em_files_state", key,
                              text=f"{text} ({n})" if key == "withdrawn" else text)

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
                self.report({"ERROR"}, "the files are not checked yet (↻ in Files): the search is for the missing ones")
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
                self.report({"ERROR"}, "the files are not checked yet: ↻ in Files")
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

    # ── the versions: which one is current, which is history, which is gone ──

    def _graph_or_report(op, context):
        from ..functions import is_graph_available
        ok, graph = is_graph_available(context)
        if not ok or graph is None:
            op.report({"ERROR"}, "no graph loaded")
            return None
        from . import operators as ops
        session = ops.current_session(context)
        if (session.joined or session.seated) and not session.can_write:
            op.report({"ERROR"}, "you may read this room, not change it")
            return None
        return graph

    def _refresh(context, graph):
        from . import file_states
        try:
            file_states.resolve_active(context, graph)
        except Exception as exc:  # noqa: BLE001 — the gesture is done; the list follows at the next check
            print(f"[storage] the list was not rebuilt: {exc}")

    class EM_OT_files_use_version(bpy.types.Operator):
        """Use this version: what cites the resource cites this version again.
        No new version is made; the later ones stay as history"""
        bl_idname = "em.files_use_version"
        bl_label = "Use"
        resource_id: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            from .. import resource_governance as governance
            from .scene_sync import to_the_room
            graph = _graph_or_report(self, context)
            if graph is None:
                return {"CANCELLED"}
            try:
                out = to_the_room(graph, lambda g: governance.use_version(g, self.resource_id))
            except Exception as exc:  # noqa: BLE001 — the reason is the person's
                self.report({"ERROR"}, f"could not use this version: {exc}")
                return {"CANCELLED"}
            if not out["moved"]:
                self.report({"INFO"}, "this version is already in use")
                return {"FINISHED"}
            shown = show_in_scene(context, graph, self.resource_id)
            _refresh(context, graph)
            n = next((v["n"] for v in governance.versions(graph, self.resource_id)
                      if v["id"] == self.resource_id), "?")
            self.report({"WARNING" if shown["kept"] else "INFO"},
                        f"v{n} in use · no new version · {shown['said']}")
            return {"FINISHED"}

    class EM_OT_files_replace(bpy.types.Operator):
        """Replace with the selected object: the object of this resource is sent
        as a new version of it; the old version stays as history"""
        bl_idname = "em.files_replace"
        bl_label = "Replace with the selected object"
        resource_id: bpy.props.StringProperty()  # type: ignore

        @classmethod
        def poll(cls, context):
            # the card's resource is the selected row: only ITS object (13 Oct
            # 2026: US 3's mesh was offered as a version of US 2)
            try:
                rid = selected(context.window_manager).id
            except (IndexError, AttributeError):
                return False
            if not bound_object(context, rid):
                cls.poll_message_set("Select the object of this resource in the scene")
                return False
            return True

        def invoke(self, context, event):
            return context.window_manager.invoke_confirm(self, event)

        def execute(self, context):
            from . import operators as ops
            from .scene_sync import revise_object, to_the_room
            graph = _graph_or_report(self, context)
            if graph is None:
                return {"CANCELLED"}
            if not ops.current_session(context).seated:
                self.report({"ERROR"}, "not in a room: there is nowhere to send the bytes to")
                return {"CANCELLED"}
            obj = bound_object(context, self.resource_id)
            if obj is None:
                obj = context.active_object
                self.report({"ERROR"}, f"{obj.name if obj else 'nothing selected'}: "
                            "not the object of this resource")
                return {"CANCELLED"}
            try:
                out = to_the_room(graph, lambda g: revise_object(context, g, obj, self.resource_id))
            except Exception as exc:  # noqa: BLE001
                self.report({"ERROR"}, f"{obj.name}: not sent ({exc})")
                return {"CANCELLED"}
            _refresh(context, graph)
            info = out["info"]
            self.report({"INFO"}, f"{obj.name}: the current revision already has these bytes"
                        if info.get("same") else
                        f"{obj.name} sent as a new revision ({info['size'] / 1e6:.1f} MB)")
            return {"FINISHED"}

    class EM_OT_files_withdraw(bpy.types.Operator):
        """Withdraw from the room… — the resource and its versions leave the
        room's graph, for everybody (you can undo it). The bytes stay in the
        node's store"""
        bl_idname = "em.files_withdraw"
        bl_label = "Withdraw from the room…"
        resource_id: bpy.props.StringProperty()  # type: ignore

        def invoke(self, context, event):
            from .. import resource_governance as governance
            graph = _graph_or_report(self, context)
            if graph is None:
                return {"CANCELLED"}
            self.plan = governance.withdraw_plan(graph, self.resource_id)
            return context.window_manager.invoke_props_dialog(self, width=520)

        def draw(self, context):
            plan = getattr(self, "plan", None) or {"members": [], "files": [], "citing": []}
            col = self.layout.column()
            box = col.box()
            box.alert = True
            box.label(text="This withdraws the resource from the room's graph.", icon="ERROR")
            box.label(text="Everybody in the room stops seeing it; its bytes stay in the store.")
            box.label(text="You can undo it while the room remembers it.")
            n = len(plan["members"])
            col.label(text=f"{n} version(s)" + (f" and {len(plan['files'])} part(s)"
                                                if plan["files"] else ""), icon="FILE")
            if plan["citing"]:
                col.label(text="It is cited by — these citations go with it:", icon="LINKED")
                for c in plan["citing"][:8]:
                    col.label(text=f"{c['source_name']}  ({c['edge_type'].replace('_', ' ')})",
                              icon="BLANK1")
                if len(plan["citing"]) > 8:
                    col.label(text=f"… and {len(plan['citing']) - 8} more", icon="BLANK1")
            else:
                col.label(text="Nothing cites it.", icon="CHECKMARK")

        def execute(self, context):
            from .. import resource_governance as governance
            from .room_session import REMOVED_IN_ROOM
            from .scene_sync import to_the_room
            graph = _graph_or_report(self, context)
            if graph is None:
                return {"CANCELLED"}
            import datetime as dt
            from .room_session import WITHDRAWN
            from .scene_sync import _section
            before = _section(graph)
            name = governance.display_name(graph, self.resource_id)
            plan = to_the_room(graph, lambda g: governance.withdraw(g, self.resource_id))
            REMOVED_IN_ROOM.update(plan["members"] + plan["files"])
            record = governance.withdrawal_record(
                before, plan, by=_me(context),
                at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            record["name"] = name
            WITHDRAWN[record["id"]] = record
            _refresh(context, graph)
            self.report({"INFO"}, f"{name} withdrawn ({len(plan['members'])} version(s), "
                        f"{len(plan['citing'])} citation(s)) · Undo: the list's menu, «Withdrawn»")
            return {"FINISHED"}

    class EM_OT_files_undo_withdraw(bpy.types.Operator):
        """Undo the withdrawal: the resource, its versions and its citations
        come back, for everybody in the room"""
        bl_idname = "em.files_undo_withdraw"
        bl_label = "Undo"
        record_id: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            import datetime as dt
            from .. import resource_governance as governance
            from . import operators as ops
            from .room_session import REMOVED_IN_ROOM, WITHDRAWN
            graph = _graph_or_report(self, context)
            record = WITHDRAWN.get(self.record_id)
            if graph is None or record is None:
                return {"CANCELLED"}
            name = record.get("name") or withdrawn_name(graph, record)
            at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for op in governance.undo_ops(record, at=at):
                try:
                    ops._apply_wire_op(op, context, graph)
                except Exception as exc:  # noqa: BLE001 — one op is one line
                    print(f"[storage] undo: {op.get('op')} not applied here: {exc}")
                ops.emit_op(op)
            for node in record.get("nodes") or []:
                REMOVED_IN_ROOM.discard(node.get("id"))
            WITHDRAWN.pop(self.record_id, None)
            _refresh(context, graph)
            self.report({"INFO"}, f"{name} is back in the room")
            return {"FINISHED"}

    class EM_OT_files_copy(bpy.types.Operator):
        """Copy this value"""
        bl_idname = "em.files_copy"
        bl_label = "Copy"
        bl_options = {"INTERNAL"}
        value: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            context.window_manager.clipboard = self.value
            self.report({"INFO"}, "copied")
            return {"FINISHED"}

    class EM_OT_files_remove_from_scene(bpy.types.Operator):
        """Remove from the scene the objects whose resource is superseded or
        withdrawn (one, or all of them). Nothing in the room changes"""
        bl_idname = "em.files_remove_from_scene"
        bl_label = "Remove from the scene"
        bl_options = {"REGISTER", "UNDO"}
        object_name: bpy.props.StringProperty(default="")  # type: ignore

        def execute(self, context):
            names = ([self.object_name] if self.object_name
                     else [o["object"] for o in marked_objects(context)])
            gone = 0
            for name in names:
                obj = bpy.data.objects.get(name)
                if obj is not None:
                    bpy.data.objects.remove(obj, do_unlink=True)
                    gone += 1
            self.report({"INFO"}, f"{gone} object(s) removed from the scene")
            return {"FINISHED"}

    return (EMFileRow, EM_UL_files, EM_MT_files_filter, EM_OT_files_select, EM_OT_files_find_moved,
            EM_OT_files_relink_moved, EM_OT_files_bucket_check, EM_OT_files_bucket_promote,
            EM_OT_files_free_local, EM_OT_files_use_version, EM_OT_files_replace,
            EM_OT_files_withdraw, EM_OT_files_undo_withdraw, EM_OT_files_copy,
            EM_OT_files_remove_from_scene)


def _may_write(context) -> bool:  # pragma: no cover — bpy
    """In a room with a role that writes (or outside any room)."""
    try:
        from . import operators as ops
        session = ops.current_session(context)
        return not ((session.joined or session.seated) and not session.can_write)
    except Exception:  # noqa: BLE001
        return False


def bound_object(context, rid: str):  # pragma: no cover — bpy
    """The active object when it is a mesh bound to the resource `rid` (its
    chain, or the unit / RM that cites it), else None."""
    obj = getattr(context, "active_object", None)
    if obj is None or obj.type != "MESH" or not rid:
        return None
    from ..functions import is_graph_available
    ok, graph = is_graph_available(context)
    if not ok or graph is None:
        return None
    props = {k: obj.get(k) for k in ("em_resource_id", "em_rm_node_id", "em_asset_sha256")}
    try:
        return obj if _gov().bound_to(graph, rid, props) else None
    except Exception:  # noqa: BLE001 — not sure is not bound
        return None


def _me(context) -> str:  # pragma: no cover — bpy
    try:
        from . import operators as ops
        return str(getattr(ops.current_session(context), "author", "") or "you")
    except Exception:  # noqa: BLE001
        return "you"


def _people(context) -> Dict[str, str]:  # pragma: no cover — bpy
    """The room's people, and this Blender's own name from its token (the
    ORCID the room stamps on what it writes → «Editor Due»)."""
    out: Dict[str, str] = {}
    try:
        from . import operators as ops
        session = ops.current_session(context)
        out.update(people(list(getattr(session, "members", []) or [])))
        from . import room as room_cfg
        from .where import claims_of
        claims = claims_of(room_cfg._session.get("token") or "")
        name = str(claims.get("name") or claims.get("preferred_username") or "")
        if name:
            for key in (getattr(session, "author", ""), claims.get("orcid"),
                        claims.get("sub"), claims.get("preferred_username")):
                if key:
                    out.setdefault(str(key), name)
    except Exception:  # noqa: BLE001
        pass
    return out


def show_in_scene(context, graph, res_id: str) -> Dict[str, Any]:  # pragma: no cover — bpy
    """After «Use»: the scene shows the version in use. Its bytes are fetched
    (or found in the scene by their digest); an object of the same resource
    with OTHER bytes leaves the scene and gives its name to the one that came
    — unless it was changed here and not sent: then it stays, marked, and
    the sentence says so (a gesture never throws away work)."""
    import bpy  # type: ignore
    from .. import resource_governance as governance
    from .materialise import PROP_DIGEST, PROP_RESOURCE, materialise, plan
    from .scene_sync import PROP_FINGERPRINT, mesh_fingerprint
    try:
        records = [r for r in plan(graph)["resident"] if r.get("resource_id") == res_id]
        report = materialise(graph, records=records) if records else {"materialised": [], "reused": []}
    except Exception as exc:  # noqa: BLE001 — the pointer moved; the bytes come at the next check
        return {"kept": [], "said": f"its geometry comes at the next «Check the scene» ({exc})"}
    came = [bpy.data.objects.get(n) for m in report.get("materialised") or []
            for n in m.get("objects") or []]
    came = [o for o in came if o is not None]
    chain = set(governance.chain_of(graph, res_id))
    removed, kept = [], []
    for obj in list(bpy.data.objects):
        rid = str(obj.get(PROP_RESOURCE) or "")
        if obj in came or rid not in chain or governance.object_status(
                graph, rid, str(obj.get(PROP_DIGEST) or "")) != governance.STATUS_SUPERSEDED:
            continue
        recorded = str(obj.get(PROP_FINGERPRINT) or "")
        if recorded and mesh_fingerprint(obj) != recorded:
            kept.append(obj.name)
            continue
        removed.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)
    if came and removed:
        came[0].name = removed[0]
    said = ("its geometry is in the scene" if came or report.get("reused")
            else "its geometry comes at the next «Check the scene»")
    if kept:
        said += f" · {', '.join(kept)} has changes not sent: kept, marked «superseded»"
    return {"kept": kept, "said": said}


def marked_objects(context) -> List[Dict[str, Any]]:  # pragma: no cover — bpy
    """The objects of the scene bound to a resource that is superseded (a newer
    revision has other bytes) or withdrawn: ``[{object, status, resource}]``."""
    import bpy  # type: ignore
    from .. import resource_governance as governance
    from ..functions import is_graph_available
    from .materialise import PROP_DIGEST, PROP_RESOURCE
    from .room_session import REMOVED_IN_ROOM
    ok, graph = is_graph_available(context)
    if not ok or graph is None:
        return []
    # drawn at every redraw: read again only when the graph, the objects or
    # the room's tombstones changed
    key = (id(graph), len(graph.nodes), len(graph.edges), len(bpy.data.objects),
           len(REMOVED_IN_ROOM),
           hash(tuple(str(o.get(PROP_RESOURCE) or "") for o in bpy.data.objects)))
    if _MARKED.get("key") == key:
        return _MARKED["rows"]
    out = []
    for obj in bpy.data.objects:
        rid = str(obj.get(PROP_RESOURCE) or "")
        if not rid:
            continue
        status = governance.object_status(graph, rid, str(obj.get(PROP_DIGEST) or ""),
                                          removed=REMOVED_IN_ROOM)
        if status:
            out.append({"object": obj.name, "status": status, "resource": rid})
    _MARKED.update(key=key, rows=out)
    return out


_MARKED: Dict[str, Any] = {}


def draw_marked(layout, context) -> None:  # pragma: no cover — bpy
    """The objects in the scene that show a superseded or withdrawn resource,
    each with the gesture that removes it — never removed by themselves."""
    marked = marked_objects(context)
    if not marked:
        return
    box = layout.box()
    head = box.row(align=True)
    head.alert = True
    head.label(text=f"In the scene, not current: {len(marked)}", icon="ERROR")
    head.operator("em.files_remove_from_scene", text="Remove all",
                  icon="TRASH").object_name = ""
    for m in marked[:10]:
        row = box.row(align=True)
        said = {"superseded": "another version is in use",
                "withdrawn": "withdrawn from the room"}.get(m["status"], m["status"])
        row.label(text=f"{m['object']} — {said}", icon="OBJECT_DATA")
        row.operator("em.files_remove_from_scene", text="",
                     icon="X").object_name = m["object"]
    if len(marked) > 10:
        box.label(text=f"… and {len(marked) - 10} more")


def fill(context, rows: List[Dict[str, Any]]) -> None:  # pragma: no cover — bpy
    """Rebuild the list (keeping the selected row when it is still there),
    with the withdrawn resources the room keeps after the others."""
    wm = context.window_manager
    keep, keep_head = "", ""
    try:
        keep = selected(wm).id
        keep_head = selected(wm).head
    except (IndexError, AttributeError):
        pass
    try:
        from ..functions import is_graph_available
        from .room_session import WITHDRAWN
        ok, graph = is_graph_available(context)
        rows = list(rows) + withdrawn_rows(graph if ok else None, list(WITHDRAWN.values()),
                                           _people(context))
    except Exception as exc:  # noqa: BLE001 — the list stands without them
        print(f"[storage] withdrawn not listed: {exc}")
    wm.em_files.clear()
    for x in rows:
        it = wm.em_files.add()
        for k, v in x.items():
            if k in it.bl_rna.properties:
                setattr(it, k, str(v))
    wm.em_files_index = kept_index(rows, keep, keep_head)


def selected(wm):
    """The selected row of Files; IndexError when none (a Blender collection
    reads -1 as the LAST row: «no row» must stay no row)."""
    i = int(getattr(wm, "em_files_index", -1))
    if i < 0:
        raise IndexError("no row selected")
    return wm.em_files[i]


def kept_index(rows, keep: str, keep_head: str = "") -> int:
    """The row selected before the list was rebuilt: by its id, or by its
    chain (`head`) — after «Use» the row of a resource takes the id of the
    version in use. Gone → no row (-1), never another one: measured on 13 Oct
    2026 at 16:10, after «Use» the card fell back on row 0 («Blend datablock
    for ME_EST_bk_LOD2») and «Replace» sent US 2 as a revision of it."""
    if not keep and not keep_head:
        return 0 if rows else -1
    for i, x in enumerate(rows):
        if x.get("id") == keep or (keep_head and x.get("head") == keep_head):
            return i
    return -1


def _in_room() -> bool:  # pragma: no cover — bpy
    try:
        from . import room as room_cfg
        return bool(room_cfg.room().get("room_id"))
    except Exception:  # noqa: BLE001
        return False


def draw(layout, context, results) -> None:  # pragma: no cover — bpy
    """Files (MICRO tre pannelli, 13 Oct 2026): a sentence that keeps itself up
    to date with Download and ↻, one search with its menu, the list, and the
    card of the selected row — its name and state, its versions, the gestures
    possible now, the Details (closed)."""
    from . import file_states
    wm = context.window_manager
    from ..functions import is_graph_available
    ok, graph = is_graph_available(context)
    graph = graph if ok else None
    # 1 · the head: what there is, and what to do about it
    head = layout.row(align=True)
    c = row_counts(wm.em_files) if results else {}
    head.label(text=summary_line(c, _in_room()) if results else "Files not checked yet",
               icon="FILE_FOLDER")
    if c.get("on_node") and _in_room():
        head.operator("em.files_keep", text="Download", icon="IMPORT").resource_id = ""
    head.operator("em.files_check", text="", icon="FILE_REFRESH")
    if file_states.ULTIMI.get("list_error"):
        layout.label(text=f"List: {file_states.ULTIMI['list_error']}", icon="ERROR")
    draw_marked(layout, context)
    # MICRO RM e aggancio · the objects not in the graph, with the gesture
    # that makes one the proxy of a unit
    from .proxy_hook import draw_not_in_graph
    draw_not_in_graph(layout, context)
    draw_moved(layout, context)
    # 2 · one search, its menu on the right
    q = layout.row(align=True)
    q.prop(wm, "em_files_query", text="", icon="VIEWZOOM")
    filtered = wm.em_files_state != "all" or wm.em_files_kind != "all"
    q.menu("EM_MT_files_filter", text="", icon="FILTER" if filtered else "DOWNARROW_HLT")
    layout.template_list("EM_UL_files", "", wm, "em_files", wm, "em_files_index", rows=6)
    try:
        it = selected(wm)
    except IndexError:
        return
    if not shown(wm.em_files_state, wm.em_files_kind, it.state, it.what):
        return
    draw_card(layout, context, graph, it)


def draw_card(layout, context, graph, it) -> None:  # pragma: no cover — bpy
    """The card of one row: name and state → Versions → the gestures possible
    now → Details (closed)."""
    from . import file_states
    from ..state_symbols import sign
    wm = context.window_manager
    card = layout.box()
    # 1 · the name, and its state in a sentence
    if it.state == "withdrawn":
        card.label(text=it.file, icon="TRASH")
        card.label(text=" · ".join(b for b in ("Withdrawn from the room", it.where) if b) + ".")
        if _may_write(context):
            card.operator("em.files_undo_withdraw", text="Undo", icon="LOOP_BACK").record_id = it.id
        return
    icon, text, meaning = sign("file." + it.state)
    card.label(text=it.file, icon=icon)
    col = card.column(align=True)
    col.label(text=STATE_SENTENCE.get(it.state) or (f"{text}: {meaning}" if meaning else text))
    # 2 · the versions, counted by their bytes, oldest first
    groups = (_gov().distinct_versions(_gov().versions(graph, it.id))
              if graph is not None else [])
    if len(groups) > 1:
        names = _people(context)
        col.separator()
        col.label(text="Versions", icon="RECOVER_LAST")
        for v in groups:
            row = col.row(align=True)
            row.label(text=version_line({**v, "by": who_is(v.get("by"), names, graph)}),
                      icon="CHECKMARK" if v["in_use"] else "BLANK1")
            if not v["in_use"] and _may_write(context):
                row.operator("em.files_use_version", text="Use").resource_id = v["id"]
    # 3 · the gestures possible now, and only those
    res = next((r for r in file_states.ULTIMI.get("results") or [] if r["id"] == it.id), None)
    acts = card.row(align=True)
    if it.state == "on_node" and _in_room():
        acts.operator("em.files_keep", text="Download", icon="IMPORT").resource_id = it.id
    if it.state in ("missing", "empty_copy"):
        acts.operator("em.files_find_here", text="Find here…", icon="VIEWZOOM").resource_id = it.id
    if it.state == "on_disk" and _in_room():
        acts.operator("em.files_upload", text="Upload", icon="EXPORT").resource_id = it.id
    if res and res.get("path") and not in_cache(res["path"]):
        # a copy in the cache (`/var/folders/…`) is nowhere a person keeps
        # files: its folder is in the Details, not a gesture
        acts.operator("em.files_open_where", text="Open where it is",
                      icon="FILEBROWSER").path = res["path"]
    obj = bound_object(context, it.id) if _in_room() and _may_write(context) else None
    if obj is not None:
        card.operator("em.files_replace", text=f"Replace with the selected object ({obj.name})",
                      icon="FILE_REFRESH").resource_id = it.id
    # 4 · Details, closed
    b = (file_states.ULTIMI.get("bucket") or {}).get(it.id)
    det = card.row(align=True)
    det.prop(wm, "em_files_details", text="Details", emboss=False,
             icon="TRIA_DOWN" if wm.em_files_details else "TRIA_RIGHT")
    if wm.em_files_details:
        _draw_details(card.column(align=True), graph, it, res, b, groups, _people(context))


def _details(graph, it, res, bucket, groups=(), names=None) -> List[tuple]:  # pragma: no cover — bpy
    """``[(label, value)]`` of the Details: the codes, the addresses, the
    jargon — everything a row and a title never show — and where it comes
    from, in plain sentences."""
    data: Dict[str, Any] = {}
    node = graph.find_node_by_id(it.id) if graph is not None else None
    if node is not None and isinstance(getattr(node, "data", None), dict):
        data = node.data
    out = []
    try:
        from .. import provenance_card
        c = provenance_card.card(graph, it.id) if graph is not None else {}
        for line in provenance_card.story(c, lambda by: who_is(by, names, graph), when):
            out.append(("Where it comes from", line))
    except Exception as exc:  # noqa: BLE001 — a card never breaks the Details
        out.append(("Where it comes from", f"not read ({exc})"))
    if it.doc:
        out.append(("Document", it.doc))
    if it.rm:
        out.append(("Shown by", it.rm))
    if it.use:
        out.append(("Used for", it.use.replace(",", ", ").replace("_", " ")))
    if data.get("residency"):
        out.append(("Kept", {"resident": "in the room's store (resident)",
                             "reference": "in another store (reference)"}.get(
                                 data["residency"], data["residency"])))
    out.append(("Id", it.id))
    if data.get("checksum"):
        out.append(("Digest", str(data["checksum"])))
    if data.get("size_bytes"):
        out.append(("Size", f"{int(data['size_bytes']) / 1e6:.2f} MB"))
    for g in groups:
        for v in g.get("same") or []:
            out.append((f"Same bytes as v{g['n']}",
                        " · ".join(b for b in (when(v.get("at") or ""),
                                               who_is(v.get("by"), names, graph), v["id"]) if b)))
        if g.get("by") and looks_like_orcid(g["by"]):
            out.append((f"v{g['n']} by", g["by"]))
    for p in (res or {}).get("positions") or []:
        mark = {True: "✓", False: "✗"}.get(p.get("ok"), "?")
        out.append((f"{mark} {p.get('kind')}", str(p.get("where") or "—")))
    if not (res or {}).get("positions") and it.where:
        out.append(("Address", it.where))
    if bucket:
        sg = BUCKET_SIGN.get(bucket["state"], ("?", bucket["state"]))
        out.append(("Bucket", f"{sg[0]} {sg[1]}" + (f" — {bucket['note']}" if bucket.get("note") else "")))
        if bucket.get("bucket"):
            out.append(("Bucket address", bucket["bucket"]))
    return out


def _draw_details(col, graph, it, res, bucket, groups=(), names=None) -> None:  # pragma: no cover — bpy
    """Two lines per value: the label, then the value whole (never cut in the
    middle) with its Copy."""
    for label, value in _details(graph, it, res, bucket, groups, names):
        head = col.row(align=True)
        head.active = False
        head.label(text=label)
        row = col.row(align=True)
        row.label(text=value)
        row.operator("em.files_copy", text="", icon="COPYDOWN", emboss=False).value = value


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
    # the count is in the head of Files («N missing»): here only the gesture
    box.operator("em.files_find_moved", text="Find moved files…", icon="VIEWZOOM")
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


def bucket_configured(env=None) -> bool:
    """A bucket is set when Blender's environment names one (the S3_*
    variables Heriverse uses)."""
    env = os.environ if env is None else env
    return bool(env.get("S3_ENDPOINT") and env.get("S3_BUCKET"))


def in_cache(path: str, caches=None) -> bool:
    """A path in a cache: the temporary folders of this computer or the add-on's
    own cache (`em_cache`), never where a person put a file."""
    import tempfile
    p = os.path.realpath(str(path or ""))
    roots = list(caches or []) + [tempfile.gettempdir(), "/var/folders", "/private/var/folders"]
    if f"{os.sep}em_cache{os.sep}" in p:
        return True
    return any(p.startswith(os.path.realpath(r).rstrip(os.sep) + os.sep) for r in roots if r)


def bucket_todo(checked: bool, rows: Dict[str, Dict[str, Any]], has_files: bool = True,
                configured: bool = True) -> str:
    """What the bucket asks of you, said on the head of Project storage even
    when it is closed: «No bucket» (grey: none configured), «Bucket not
    checked» (grey), «Bucket: 2 differ» (red: a difference measured), or
    nothing. `bucket_alert` says which are red."""
    if not has_files:
        return ""
    if not configured:
        return "No bucket"
    if not checked:
        return "Bucket not checked"
    tally: Dict[str, int] = {}
    for r in (rows or {}).values():
        tally[r.get("state", "")] = tally.get(r.get("state", ""), 0) + 1
    if tally.get("differ"):
        return f"Bucket: {tally['differ']} differ"
    if tally.get("neither"):
        return f"Bucket: {tally['neither']} lost"
    if tally.get("disk_only"):
        return f"Bucket: {tally['disk_only']} not uploaded"
    return ""


def bucket_alert(said: str) -> bool:
    """Red only for a difference measured — never for a bucket not set or not
    checked (13 Oct 2026: «Bucket not checked» in red over no bucket at all)."""
    return said.startswith("Bucket: ")


def draw_bucket(layout, context) -> None:  # pragma: no cover — bpy
    """The bucket: check it (quick, or byte for byte), how many stand in each
    way, upload the file selected in Files, and free the disk copies the
    bucket proves."""
    from . import file_states
    box = layout.box()
    head = box.row(align=True)
    head.label(text="Bucket", icon="WORLD")
    head.operator("em.files_bucket_check", text="Check", icon="FILE_REFRESH").deep = False
    head.operator("em.files_bucket_check", text="Verify bytes", icon="CHECKMARK").deep = True
    rows = file_states.ULTIMI.get("bucket") or {}
    if not rows:
        box.label(text="Not checked: it compares each file's disk copy with its bucket copy.")
    else:
        tally: Dict[str, int] = {}
        for r in rows.values():
            tally[r["state"]] = tally.get(r["state"], 0) + 1
        grid = box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for k in ("aligned", "same_size", "differ", "disk_only", "bucket_only", "neither", "unknown"):
            if tally.get(k):
                g = grid.row()
                g.alert = k in ("differ", "neither")
                g.label(text=f"{BUCKET_SIGN[k][0]} {tally[k]} {k.replace('_', ' ')}")
    wm = context.window_manager
    try:
        it = selected(wm)
    except (IndexError, AttributeError):
        it = None
    b = rows.get(it.id) if it is not None else None
    if it is not None and it.state in ("on_disk", "both") and not (
            b and b["state"] in ("aligned", "same_size")):
        box.operator("em.files_bucket_promote", text=f"Upload {it.file} to the bucket",
                     icon="EXPORT").resource_id = it.id
    if any(r["state"] == "aligned" for r in rows.values()):
        box.operator("em.files_free_local", text="Free local copies…", icon="TRASH")


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    wm = bpy.types.WindowManager
    wm.em_files = bpy.props.CollectionProperty(type=_CLASSES[0])
    wm.em_files_index = bpy.props.IntProperty()
    wm.em_files_query = bpy.props.StringProperty(
        name="Search", description="Words of the name, the document, the model")
    wm.em_files_kind = bpy.props.EnumProperty(name="Kind", items=KINDS)
    wm.em_files_state = bpy.props.EnumProperty(name="Where", items=STATES)
    wm.em_files_details = bpy.props.BoolProperty(
        name="Details", default=False,
        description="The codes and addresses of this resource: id, digest, where its "
                    "bytes are, the cache — to copy")


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    wm = bpy.types.WindowManager
    for name in ("em_files", "em_files_index", "em_files_query", "em_files_kind", "em_files_state",
                 "em_files_details"):
        if hasattr(wm, name):
            delattr(wm, name)
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
