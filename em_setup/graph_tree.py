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


def writing_in(origin, rows, active) -> str:
    """S1 · «Writing in: <graph>» — the graph of the room's study the edits
    are for: the active one when it is in this room's branch."""
    if not (0 <= active < len(rows)):
        return ""
    row = rows[active]
    if graph_origins.origin_of(row, abspath=_abspath).key != origin.key:
        return ""
    return getattr(row, "graph_code", "") or row.name


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


def save_origin(context, index: int) -> tuple:
    """Save the origin of row `index`. → `(ok, message, needs_save_as)`."""
    from s3dgraphy import get_graph

    em_tools = context.scene.em_tools
    rows = _rows(em_tools)
    if not (0 <= index < len(rows)):
        return False, "no graph selected", False
    origin = graph_origins.origin_of(rows[index], abspath=_abspath)
    if origin.is_room:
        state, _icon = room_state(origin)
        return (True, f"{rows[index].name} lives in the {origin.label}: every "
                      f"edit goes to the room as it is made, there is no file "
                      f"to write ({state})", False)
    if not origin.is_file:
        return False, "this graph has no file yet", True
    if not origin.is_emjson:
        return (False, f"{origin.label} is a GraphML (not lossless): save the "
                       f"graph as em.json", True)
    members = graph_origins.members_of(rows, origin, abspath=_abspath)
    active_gid = rows[index].name
    result = graph_origins.save_file(origin.path, members, get_graph,
                                     active_graph_id=active_gid)
    return True, result.sentence(), False


def persist_active(context) -> tuple:
    """G1 · the «salvataggio virtuoso» after a creation: the ACTIVE graph to its
    origin — its em.json, or nothing to write in a room. Never a GraphML: a
    graph that has no em.json yet is said, not saved. → `(ok, message)`."""
    ok, message, save_as = save_origin(context, context.scene.em_tools.active_file_index)
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

    def execute(self, context):
        try:
            ok, message, save_as = save_origin(context, self.index)
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
        head = col.row(align=True)
        if origin.is_room:
            head.label(text=origin.label, icon="WORLD")
        elif origin.is_file:
            head.label(text=origin.label,
                       icon="FILE" if origin.is_emjson else "FILE_BLANK")
        else:
            head.label(text="No file", icon="QUESTION")
        if origin.key == active_key:
            # EMStudio's «⌘S» mark: the active graph is in this branch
            head.label(text="", icon="CHECKMARK")
        if origin.is_emjson:
            op = head.operator("em.graph_origin_save", text="", icon="FILE_TICK",
                               emboss=False)
            op.index = indices[0]
        if origin.is_room:
            state, icon = room_state(origin)
            sub = col.row()
            sub.separator(factor=2.0)
            sub.label(text=state, icon=icon)
            writing = writing_in(origin, rows, active)
            if writing:
                sub = col.row()
                sub.separator(factor=2.0)
                sub.label(text=f"Writing in: {writing}", icon="GREASEPENCIL")
            for ref in cited_of(origin):
                sub = col.row()
                sub.separator(factor=2.0)
                sub.label(text=f"↗ {ref} · cited, read only", icon="LIBRARY_DATA_DIRECT")
        for i in indices:
            row = rows[i]
            graph = get_graph(row.name)
            present = bool(graph is not None and getattr(graph, "nodes", None))
            line = col.row(align=True)
            line.separator(factor=2.0)
            label = row.graph_code if getattr(row, "graph_code", "") else row.name
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
            if getattr(row, "file_format", "GRAPHML") == "EMJSON":
                rl = line.operator("import.em_emjson", text="", icon="FILE_REFRESH",
                                   emboss=False)
                rl.file_index = i
            else:
                rl = line.operator("import.em_graphml", text="",
                                   icon="FILE_REFRESH", emboss=False)
                rl.graphml_index = i
            if hasattr(row, "is_publishable"):
                try:
                    from .. import icons_manager
                    line.prop(row, "is_publishable", text="",
                              icon_value=icons_manager.get_icon_value(
                                  "em_publish" if row.is_publishable
                                  else "em_no_publish"))
                except Exception:  # noqa: BLE001
                    line.prop(row, "is_publishable", text="")
    if sum(1 for o, _ in branches if o.is_emjson) > 1:
        box.operator("em.graph_save_all", icon="FILE_TICK")


CLASSES = (EM_OT_graph_activate, EM_OT_graph_origin_save, EM_OT_graph_save_all)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
