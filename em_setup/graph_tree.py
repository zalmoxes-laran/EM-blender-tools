"""M1/M2 · the graphs of the scene as a tree: «file or room → graphs».

The rows stay where they always were (`em_tools.graphml_files`, read by some
seventy places); what changes is how they are drawn and where «Save» writes.
The branch of a row is its origin (`graph_origins.origin_of`): an em.json, a
GraphML, a room on a node. Clicking a graph makes it THE active graph — the one
the lists show, the one edits apply to and, when it lives in a room, the room
the edits go to. «Save» on a branch writes that file with its own graphs only.

Wording follows EMStudio's EMTree, so the two tools describe the same project
the same way.
"""

from __future__ import annotations

import bpy  # type: ignore
from bpy.props import IntProperty  # type: ignore

from .. import graph_origins
from ..georef_manager.on_save import GEOREF_ITEMS


def _rows(em_tools):
    return list(getattr(em_tools, "graphml_files", ()) or ())


def _abspath(path: str) -> str:
    return bpy.path.abspath(path)


def _loaded(row) -> bool:
    from s3dgraphy import get_graph
    graph = get_graph(row.name)
    return bool(graph is not None and getattr(graph, "nodes", None))


def room_state(origin) -> tuple:
    """`(sentence, icon)` for a room branch: joined or not, role, people.
    V1 · through `room_session.session_of_room`, the same lookup «Where you
    work» reads (`room_session.here`): the two never answer differently."""
    try:
        from ..sync_manager import room_session as _rs
    except Exception:  # noqa: BLE001
        return ("room state unknown", "QUESTION")
    session = _rs.session_of_room(None, origin.room_id)
    if session is not None and session.joined:
        role = f" as {session.role}" if session.role else ""
        people = len(session.members or [])
        return (f"joined{role} · {people} here", "LINKED")
    if session is not None and session.offline:
        return (f"offline · {session.waiting()} edit(s) waiting", "TIME")
    return ("not connected: Reconnect in Where you work to send edits", "UNLINKED")


def _text_of(name) -> str:
    """A graph's name as s3dgraphy keeps it: a string, or a dict by language."""
    if isinstance(name, dict):
        for key in ("en", "it"):
            if name.get(key):
                return str(name[key])
        return next((str(v) for v in name.values() if v), "")
    return str(name or "")


def study_title(origin) -> str:
    """V2 · what the study in a room is called: the room's title as the node
    said it (the list, the creation, the entry), else its id."""
    try:
        from ..sync_manager import where
        return where.ROOM_TITLES.get(origin.room_id) or origin.room_id
    except Exception:  # noqa: BLE001
        return origin.room_id


#: graph codes that are not codes (s3dgraphy's MISSINGCODE, the template's
#: site_id): never a name
_NO_CODE = ("", "site_id", "MISSINGCODE")


def graph_name(row, origin=None) -> tuple:
    """V2 · `(name, note)` of a graph: its code, its own name, else its id.
    A room made before S1 holds its graph under the room's id: then the name
    is the study's title, and `note` says so.

    P2 (6 Oct 2026) · never the bare UUID when a name exists: a graph listed
    and not loaded (the other graphs of an em.json) takes its code or its name
    from the file it is in (`graph_origins.peek_graph_names`)."""
    code = str(getattr(row, "graph_code", "") or "")
    if code not in _NO_CODE:
        return code, ""
    try:
        from s3dgraphy import get_graph
        graph = get_graph(row.name)
    except Exception:  # noqa: BLE001
        graph = None
    own = _text_of(getattr(graph, "name", "")) if graph is not None else ""
    if own and own != row.name:
        return own, ""
    path = str(getattr(row, "graphml_path", "") or "")
    if path.lower().endswith(".json"):
        try:
            name, peeked = graph_origins.peek_graph_names(_abspath(path)).get(
                row.name, ("", ""))
        except Exception:  # noqa: BLE001 — a name is never worth a failure
            name, peeked = "", ""
        if peeked not in _NO_CODE:
            return peeked, ""
        if name and name != row.name:
            return name, ""
    if origin is not None and origin.is_room and row.name == origin.room_id:
        return study_title(origin), "the study's title, the graph has none"
    return row.name, ""


def writing_in(origin, rows, active) -> str:
    """S1 · «Writing in: <graph>» — the graph the edits are for: the active
    one when it is in this branch. V2 · by its name, never the room's id."""
    if not (0 <= active < len(rows)):
        return ""
    row = rows[active]
    if graph_origins.origin_of(row, abspath=_abspath).key != origin.key:
        return ""
    name, note = graph_name(row, origin)
    return f"{name} ({note})" if note else name


def cited_of(origin) -> list:
    """S1 · the studies the room CITES (its container_refs after the first,
    I-2): read only, no operation leaves from them."""
    try:
        from ..sync_manager import room_session as _rs
    except Exception:  # noqa: BLE001
        return []
    for _gid, session in _rs.sessions():
        if session.room_id == origin.room_id:
            return list(getattr(session, "cited", None) or [])
    return []


def origin_members(context, index: int) -> tuple:
    """What a save of row `index` writes: `(graph_ids, is_room)`; `([], False)`
    when it writes nothing (no file yet, a GraphML)."""
    rows = _rows(context.scene.em_tools)
    if not (0 <= index < len(rows)):
        return [], False
    origin = graph_origins.origin_of(rows[index], abspath=_abspath)
    if origin.is_room:
        return [rows[index].name], True
    if not origin.is_file or not origin.is_emjson:
        return [], False
    return graph_origins.members_of(rows, origin, abspath=_abspath), False


def georef_conflict(context, index: int):
    """MICRO georef al salvataggio · the discrepancy scene/graph a save of row
    `index` would stop on (see `georef_manager.on_save`), or None."""
    from ..georef_manager import on_save
    members, _room = origin_members(context, index)
    return on_save.conflict(context, members) if members else None


def save_origin(context, index: int, georef: str = "ASK") -> tuple:
    """Save the origin of row `index`. → `(ok, message, needs_save_as)`.

    MICRO georef al salvataggio · the scene's georeferencing goes into the
    scene's graph first (`georef_manager.on_save.before_write`); `georef` says
    what to do when the two differ and the scene was never aligned to the graph
    (PUSH / PULL / KEEP) — with ASK nothing is written and the message says so.
    """
    from s3dgraphy import get_graph
    from ..georef_manager import on_save

    em_tools = context.scene.em_tools
    rows = _rows(em_tools)
    if not (0 <= index < len(rows)):
        return False, "no graph selected", False
    origin = graph_origins.origin_of(rows[index], abspath=_abspath)
    if origin.is_room:
        plan = on_save.before_write(context, [rows[index].name], georef, room=True)
        if plan and plan["outcome"] == "conflict":
            return False, plan["sentence"], False
        state, _icon = room_state(origin)
        said = (f"{rows[index].name} lives in the {origin.label}: every "
                f"edit goes to the room as it is made, there is no file "
                f"to write ({state})")
        extra = on_save.tail(plan)
        return True, f"{said} · {extra}" if extra else said, False
    if not origin.is_file:
        return False, "this graph has no file yet", True
    if not origin.is_emjson:
        return (False, f"{origin.label} is a GraphML (not lossless): save the "
                       f"graph as em.json", True)
    members = graph_origins.members_of(rows, origin, abspath=_abspath)
    active_gid = rows[index].name
    plan = on_save.before_write(context, members, georef)
    if plan and plan["outcome"] == "conflict":
        return False, f"not saved: {plan['sentence']}", False
    # MICRO-EMTOOLS-CONTENITORI · the RM containers into the graphs first
    from ..rm_manager.containers import project_containers_before_save
    project_containers_before_save(context, members)
    result = graph_origins.save_file(origin.path, members, get_graph,
                                     active_graph_id=active_gid)
    from .unsaved import mark
    mark(context, origin.path)
    extra = on_save.tail(plan)
    return True, (f"{result.sentence()} · {extra}" if extra
                  else result.sentence()), False


def persist_active(context) -> tuple:
    """G1 · the «salvataggio virtuoso» after a creation: the ACTIVE graph to its
    origin — its em.json, or nothing to write in a room. Never a GraphML: a
    graph that has no em.json yet is said, not saved. → `(ok, message)`.

    Nobody is asked here (it follows a creation): a discrepancy scene/graph
    keeps the graph's georeferencing (KEEP) and the message says it."""
    ok, message, save_as = save_origin(
        context, context.scene.em_tools.active_file_index, georef="KEEP")
    if save_as:
        return False, ("not saved: this graph has no em.json yet — Save As… "
                       "writes one")
    return ok, message


class EM_OT_graph_activate(bpy.types.Operator):
    """Make this graph the active one: the lists show it, edits apply to it,
    and — when it lives in a room — the edits go to that room"""

    bl_idname = "em.graph_activate"
    bl_label = "Activate graph"
    bl_description = ("Make this the active graph: the lists show it, edits "
                      "apply to it, and its room (if any) receives them")
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1, options={"SKIP_SAVE"})  # type: ignore

    @classmethod
    def description(cls, context, properties):
        """In a room, the row says only the study's name: the rest is here."""
        try:
            rows = _rows(context.scene.em_tools)
            row = rows[properties.index]
            origin = graph_origins.origin_of(row, abspath=_abspath)
        except Exception:  # noqa: BLE001
            return cls.bl_description
        if not origin.is_room:
            return cls.bl_description
        writing = writing_in(origin, rows, context.scene.em_tools.active_file_index)
        said = [f"{study_title(origin)} · the study in the room",
                f"Writing in: {writing}" if writing else "Click to write in it",
                f"The room: {room_alignment(origin)[1]}"]
        return "\n".join(said)

    def execute(self, context):
        em_tools = context.scene.em_tools
        rows = _rows(em_tools)
        if not (0 <= self.index < len(rows)):
            return {"CANCELLED"}
        em_tools.active_file_index = self.index
        row = rows[self.index]
        try:
            from ..sync_manager import room_session as _rs
            _rs.activate(row.name)
        except Exception as exc:  # noqa: BLE001
            print(f"[graph tree] room activation skipped: {exc}")
        if _loaded(row):
            bpy.ops.em_tools.populate_lists(graphml_index=self.index)
        return {"FINISHED"}


class EM_OT_graph_origin_save(bpy.types.Operator):
    """Save this file with its own graphs only"""

    bl_idname = "em.graph_origin_save"
    bl_label = "Save this file"
    bl_description = ("Save this file with its own graphs only — the other "
                      "files of the scene are not touched")

    index: IntProperty(default=-1, options={"SKIP_SAVE"})  # type: ignore
    georef: bpy.props.EnumProperty(  # type: ignore
        name="Georeferencing", items=GEOREF_ITEMS, default="ASK",
        options={"SKIP_SAVE"})

    def invoke(self, context, event):
        self._conflict = georef_conflict(context, self.index)
        if self._conflict is None:
            return self.execute(context)
        self.georef = "KEEP"
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        from ..georef_manager import on_save
        plan = getattr(self, "_conflict", None) or georef_conflict(context, self.index)
        if plan:
            on_save.draw_choice(self.layout, self, plan)

    def execute(self, context):
        try:
            ok, message, save_as = save_origin(context, self.index, self.georef)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"Save failed: {exc}")
            return {"CANCELLED"}
        if save_as:
            context.scene.em_tools.active_file_index = self.index
            return bpy.ops.export.em_saveas("INVOKE_DEFAULT")
        self.report({"INFO"} if ok else {"WARNING"}, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


class EM_OT_graph_save_all(bpy.types.Operator):
    """Save every em.json file of the scene, each with its own graphs"""

    bl_idname = "em.graph_save_all"
    bl_label = "Save all files"
    bl_description = ("Save every em.json file of the scene, each with its own "
                      "graphs; GraphML files and rooms are not written")

    def execute(self, context):
        em_tools = context.scene.em_tools
        said = []
        for origin, indices in graph_origins.tree(_rows(em_tools), abspath=_abspath):
            if not origin.is_emjson:
                continue
            ok, message, _ = save_origin(context, indices[0])
            said.append(message)
        if not said:
            self.report({"WARNING"}, "no em.json file in this scene to save")
            return {"CANCELLED"}
        self.report({"INFO"}, " · ".join(said))
        return {"FINISHED"}


def _delete_target(context, index: int):
    """`(rows, i, row, origin)` of the graph «Delete…» acts on, or None."""
    em_tools = context.scene.em_tools
    rows = _rows(em_tools)
    i = index if index >= 0 else em_tools.active_file_index
    if not (0 <= i < len(rows)):
        return None
    return rows, i, rows[i], graph_origins.origin_of(rows[i], abspath=_abspath)


class EM_OT_graph_delete(bpy.types.Operator):
    """Delete this graph from its em.json — after the report"""

    bl_idname = "em.graph_delete"
    bl_label = "Delete the graph from its em.json…"
    bl_description = ("Take the graph OUT of its em.json (− only takes it off "
                      "the scene, and the file keeps it). First the report, "
                      "s3Dgraphy's: its nodes and edges, the links of the "
                      "other graphs that point at it, the shelf entries only "
                      "it used, the files nobody else uses (never deleted), "
                      "the Blender objects tied to it (they stay). Written "
                      "by the next save of the file")

    index: IntProperty(default=-1, options={"SKIP_SAVE"})  # type: ignore
    drop_links: bpy.props.BoolProperty(  # type: ignore
        name="Remove the links of the other graphs that point at it",
        description="Otherwise they stay, marked as pointing at a deleted graph",
        default=False, options={"SKIP_SAVE"})
    drop_shelf: bpy.props.BoolProperty(  # type: ignore
        name="Take the shelf entries only it used off the shelf",
        description="Otherwise they stay on the shelf", default=False,
        options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        target = _delete_target(context, -1)
        if target is None:
            cls.poll_message_set("No graph selected")
            return False
        _rows_, _i, _row, origin = target
        if origin.is_room:
            cls.poll_message_set("The graph lives in a room: it is the room's "
                                 "study, not a file's")
            return False
        if not (origin.is_file and origin.is_emjson):
            cls.poll_message_set("The graph is not in an em.json (a GraphML or "
                                 "no file): there is no file to take it out of")
            return False
        if graph_origins.removal_api() is None:
            cls.poll_message_set("The s3Dgraphy bundled here is older than "
                                 "«Delete the graph»: it comes with the next "
                                 "bundle")
            return False
        return True

    def _report(self, context, dry_run=True):
        from s3dgraphy import get_graph
        rows, i, row, origin = _delete_target(context, self.index)
        members = graph_origins.members_of(rows, origin, abspath=_abspath)
        return graph_origins.remove_from_file(
            origin.path, row.name, members, get_graph,
            links="drop" if self.drop_links else "keep",
            shelf="drop" if self.drop_shelf else "keep", dry_run=dry_run)

    def _objects(self, context):
        from s3dgraphy import get_graph
        from ..graph_code import graph_code_of
        _rows_, _i, row, _origin = _delete_target(context, self.index)
        graph = get_graph(row.name)
        code = (graph_code_of(graph) if graph is not None else None) or ""
        return graph_origins.objects_of_graph(
            graph, (o.name for o in bpy.data.objects), code)

    def invoke(self, context, event):
        try:
            self._said = self._report(context)
        except Exception as exc:  # noqa: BLE001 — GraphRemovalError, ImportError
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self._objs = self._objects(context)
        return context.window_manager.invoke_props_dialog(self, width=560)

    def draw(self, context):
        from s3dgraphy.graph_removal import removal_summary
        layout = self.layout
        try:
            rep = self._report(context)
        except Exception as exc:  # noqa: BLE001
            layout.label(text=str(exc), icon="ERROR")
            return
        col = layout.column(align=True)
        for sentence in removal_summary(rep):
            col.label(text=sentence[:1].upper() + sentence[1:])
        for link in rep["links_in"][:6]:
            col.label(text=f"   {link['graph_id']} · {link['source_name'] or link['source']} "
                           f"→ {link['target_name'] or link['target']} ({link['edge_type']})")
        if rep["links_in"]:
            layout.prop(self, "drop_links")
        for entry in rep["shelf_only_here"][:6]:
            col.label(text=f"   shelf: {entry['name'] or entry['locator']}")
        if rep["shelf_only_here"]:
            layout.prop(self, "drop_shelf")
        for path in rep["files_alone"][:6]:
            col.label(text=f"   file: {path}", icon="FILE")
        objs = getattr(self, "_objs", None) or self._objects(context)
        box = layout.box()
        if objs:
            box.label(text=f"{len(objs)} Blender objects are tied to it by name: "
                           f"they stay in the scene", icon="OBJECT_DATA")
            box.label(text=", ".join(objs[:10]) + (f" … and {len(objs) - 10} more"
                                                    if len(objs) > 10 else ""))
        else:
            box.label(text="No Blender object is tied to it by name",
                      icon="OBJECT_DATA")

    def execute(self, context):
        from s3dgraphy import remove_graph as unload
        from s3dgraphy.graph_removal import removal_summary
        from .. import emjson_state
        target = _delete_target(context, self.index)
        if target is None:
            return {"CANCELLED"}
        _rows_, i, row, origin = target
        gid = row.name
        try:
            objs = self._objects(context)
            rep = self._report(context, dry_run=False)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        # off the manager and off the list; the objects stay where they are
        unload(gid)
        em_tools = context.scene.em_tools
        em_tools.graphml_files.remove(i)
        em_tools.active_file_index = min(max(0, i - 1), len(em_tools.graphml_files) - 1)
        emjson_state.note_deleted(origin.path, gid)
        said = removal_summary(rep)
        print(f"[em.json] graph deleted from {origin.path}:")
        for sentence in said:
            print(f"  · {sentence}")
        if objs:
            print(f"  · Blender objects tied to it by name, left in the scene: {', '.join(objs)}")
        rows = _rows(em_tools)
        if rows and 0 <= em_tools.active_file_index < len(rows) and _loaded(rows[em_tools.active_file_index]):
            try:
                bpy.ops.em_tools.populate_lists(graphml_index=em_tools.active_file_index)
            except Exception as exc:  # noqa: BLE001
                print(f"[graph tree] populate after delete skipped: {exc}")
        tail = (f" · {len(objs)} Blender objects tied to it stay" if objs else "")
        self.report({"INFO"}, f"{said[0]} — save {origin.label} to write it{tail}")
        return {"FINISHED"}


def draw_graph_tree(layout, context, em_tools) -> None:
    """The tree: a branch per origin, a row per graph, the active one marked."""
    from s3dgraphy import get_graph

    rows = _rows(em_tools)
    box = layout.box()
    col = box.column(align=True)
    branches = graph_origins.tree(rows, abspath=_abspath)
    active = em_tools.active_file_index
    active_key = (graph_origins.origin_of(rows[active], abspath=_abspath).key
                  if 0 <= active < len(rows) else None)
    for origin, indices in branches:
        if origin.is_room:
            _draw_room_branch(col, origin, indices, rows, active)
            continue
        head = col.row(align=True)
        unsaved = _unsaved_reasons(origin)
        if origin.is_file:
            # MICRO salva · ● before the name: the graph in memory moved away
            # from the file since it was loaded or saved
            head.label(text=f"● {origin.label}" if unsaved else origin.label,
                       icon="FILE" if origin.is_emjson else "FILE_BLANK")
        else:
            head.label(text="No file", icon="QUESTION")
        if origin.key == active_key:
            # EMStudio's «⌘S» mark: the active graph is in this branch, and
            # Save (the bar above) writes this branch. P2 · one way of saving
            # a branch: the per-branch save icon and «Save all files» left the
            # view (Save all files is in the ▾ menu)
            head.label(text="", icon="CHECKMARK")
            draw_save_row(col, origin, unsaved)
        writing = writing_in(origin, rows, active)
        if writing:
            sub = col.row()
            sub.separator(factor=2.0)
            sub.label(text=f"Writing in: {writing}", icon="GREASEPENCIL")
        for i in indices:
            row = rows[i]
            graph = get_graph(row.name)
            present = bool(graph is not None and getattr(graph, "nodes", None))
            line = col.row(align=True)
            line.separator(factor=2.0)
            label = graph_name(row, origin)[0]
            op = line.operator(
                "em.graph_activate", text=label,
                icon="RADIOBUT_ON" if i == active else "RADIOBUT_OFF",
                emboss=(i == active), depress=(i == active))
            op.index = i
            from ..functions import get_compatible_icon
            line.label(text="", icon=get_compatible_icon(
                "SEQUENCE_COLOR_04" if present else "SEQUENCE_COLOR_01"))
            if getattr(row, "geo_applied", False) and getattr(row, "geo_note", ""):
                line.label(text="", icon="ORIENTATION_GLOBAL")
            load_op(line, getattr(row, "file_format", "GRAPHML") == "EMJSON", i,
                    emboss=False)
            if i == active:
                _draw_active_path(col, row, i, present, origin)


def _unsaved_reasons(origin) -> list:
    if not origin.is_emjson:
        return []
    try:
        from .unsaved import reasons
        return reasons(origin)
    except Exception:  # noqa: BLE001 — a mark is never worth a failed panel
        return []


def draw_save_row(col, origin, unsaved) -> None:
    """MICRO salva (17 Oct 2026) · E.D. never found the save: it was a bare
    icon (FILE_TICK) between + ↻ and − in the bar, «Save as…» in the ▾ menu.
    Under the name of the active graph's file, two buttons WITH words: «Save
    em.json» (in place) and «Save as…»; a GraphML or a graph with no file
    gets «Save as em.json…» alone. When the file is behind the scene, the
    button is lit and one line says why."""
    line = col.row(align=True)
    line.separator(factor=2.0)
    if origin.is_emjson:
        save = line.row(align=True)
        save.alert = bool(unsaved)
        save.operator("export.em_save", text="Save em.json", icon="FILE_TICK")
        line.operator("export.em_saveas", text="Save as…", icon="FILE_NEW")
        if unsaved:
            note = col.row()
            note.separator(factor=2.0)
            note.label(text="Unsaved: " + " · ".join(unsaved), icon="INFO")
    else:
        line.operator("export.em_saveas", text="Save as em.json…",
                      icon="FILE_NEW")


def room_alignment(origin) -> tuple:
    """`(icon, sentence)` of a room's study: ✓ aligned, ⋯ sending, or not
    connected — the same session «Where you work» reads."""
    try:
        from ..sync_manager import room_session as _rs
        session = _rs.session_of_room(None, origin.room_id)
    except Exception:  # noqa: BLE001
        session = None
    if session is None or not (session.joined or session.offline):
        return ("UNLINKED", "not connected")
    waiting = session.waiting()
    if session.offline:
        return ("UNLINKED", f"offline · {waiting} waiting" if waiting else "offline")
    if waiting:
        return ("TIME", f"sending {waiting}")
    return ("CHECKMARK", "aligned")


def _draw_room_branch(col, origin, indices, rows, active) -> None:
    """MICRO tre pannelli (13 Oct 2026) · in a room the tree is ONE row: the
    study of the room, the pencil when you write in it, the tick of the
    alignment. «… · the study in the room» and «Writing in:» are its tooltip
    (`EM_OT_graph_activate.description`); where, with whom and as what is
    «Where you work»'s to say."""
    for i in indices:
        row = rows[i]
        line = col.row(align=True)
        label = study_title(origin) if len(indices) == 1 else graph_name(row, origin)[0]
        op = line.operator("em.graph_activate", text=label,
                           icon="GREASEPENCIL" if i == active else "RADIOBUT_OFF",
                           emboss=(i == active), depress=(i == active))
        op.index = i
        line.label(text="", icon=room_alignment(origin)[0])
    for ref in cited_of(origin):
        sub = col.row()
        sub.separator(factor=2.0)
        sub.label(text=f"↗ {ref} · cited, read only", icon="LIBRARY_DATA_DIRECT")


def load_op(layout, emjson: bool, index: int, text: str = "",
            icon: str = "FILE_REFRESH", emboss: bool = True):
    """The load command, with the dispatch on the format, in ONE place: an
    em.json given to the GraphML importer is parsed as XML («not
    well-formed»), and the index property is named differently in the two
    (`file_index` against `graphml_index`)."""
    if emjson:
        op = layout.operator("import.em_emjson", text=text, icon=icon, emboss=emboss)
        op.file_index = index
    else:
        op = layout.operator("import.em_graphml", text=text, icon=icon, emboss=emboss)
        op.graphml_index = index
    return op


def _draw_active_path(col, row, index, present, origin) -> None:
    """P2 · the Path of the selected graph inside its row, not under the tree;
    with Load beside it while the graph is not loaded. In a room with no file
    the Path is not drawn (V2: the study is the room's)."""
    if origin.is_room and not row.graphml_path:
        return
    line = col.row(align=True)
    line.separator(factor=4.0)
    if row.graphml_path and not present:
        line = line.split(factor=0.72, align=True)
    line.prop(row, "graphml_path", text="")
    if row.graphml_path and not present:
        load_op(line, getattr(row, "file_format", "GRAPHML") == "EMJSON", index,
                text="Load", icon="IMPORT")


def emjson_branches(em_tools) -> int:
    return sum(1 for o, _ in graph_origins.tree(_rows(em_tools), abspath=_abspath)
               if o.is_emjson)


def _loaded_count(em_tools) -> int:
    from s3dgraphy import get_graph
    return sum(1 for r in _rows(em_tools)
               if getattr(r, "is_graph", False) or get_graph(r.name))


def in_room() -> bool:
    """This Blender works in a room now (its study is the room's)."""
    try:
        from ..sync_manager import room as room_cfg
        return bool(room_cfg.room().get("room_id"))
    except Exception:  # noqa: BLE001
        return False


def draw_toolbar(layout, context, em_tools, stato) -> None:
    """P2 (6 Oct 2026) · the commands on the graphs as a compact bar of icons
    above the tree, like the toolbar of EMStudio's EMtree: + Add graph,
    ↻ Reload, Save, − Remove, and the rest in the ▾ menu (Save as…, Save all
    files, Multigraph). The names are the tooltips (the operators'
    descriptions; a button off says why with `poll_message_set`)."""
    bar = layout.row(align=True)
    if in_room():
        # MICRO una verità (13 Oct 2026) · in a room the study is the room's:
        # + ↻ 💾 − speak of local files. Only ▾, with Save as… for a copy
        bar.menu("EM_MT_graph_more", text="", icon="DOWNARROW_HLT")
        return
    bar.operator("em_tools.add_file", text="", icon="ADD")
    sub = bar.row(align=True)
    sub.enabled = bool(stato.get("ha_path"))
    load_op(sub, bool(stato.get("emjson")), stato["indice"])
    bar.operator("export.em_save", text="", icon="FILE_TICK")
    bar.operator("em_tools.remove_file", text="", icon="REMOVE")
    if getattr(context.scene, "landscape_mode_active", False):
        # the one state of the bar worth seeing: the scene shows every graph
        bar.label(text="Multigraph", icon="WORLD")
    bar.separator()
    bar.menu("EM_MT_graph_more", text="", icon="DOWNARROW_HLT")


class EM_MT_graph_more(bpy.types.Menu):
    """The rest of the commands on the graphs"""

    bl_idname = "EM_MT_graph_more"
    bl_label = "Graphs"

    def draw(self, context):
        layout = self.layout
        em_tools = context.scene.em_tools
        layout.operator("export.em_saveas", text="Save as…", icon="FILE_NEW")
        row = layout.row()
        row.enabled = emjson_branches(em_tools) > 1
        row.operator("em.graph_save_all", icon="FILE_TICK")
        layout.separator()
        on = getattr(context.scene, "landscape_mode_active", False)
        row = layout.row()
        row.enabled = on or _loaded_count(em_tools) >= 2
        op = row.operator("em.toggle_landscape_mode",
                          text="Multigraph: off" if on else "Multigraph: on",
                          icon="WORLD" if on else "WORLD_DATA")
        op.enable = not on
        layout.operator("wm.call_menu", text="What is Multigraph?",
                        icon="INFO").name = "EM_MT_LandscapeInfo"
        # MICRO contenuti-workspace-elimina-grafo · the graph LEAVES its em.json
        layout.separator()
        layout.operator("em.graph_delete", icon="TRASH")


CLASSES = (EM_OT_graph_activate, EM_OT_graph_origin_save, EM_OT_graph_save_all,
           EM_OT_graph_delete, EM_MT_graph_more)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
