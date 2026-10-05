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
            # V2 · the study the room holds — where, with whom and as what
            # is «Where you work»'s to say, not repeated here
            head.label(text=f"{study_title(origin)} · the study in the room",
                       icon="COMMUNITY")
        elif origin.is_file:
            head.label(text=origin.label,
                       icon="FILE" if origin.is_emjson else "FILE_BLANK")
        else:
            head.label(text="No file", icon="QUESTION")
        if origin.key == active_key:
            # EMStudio's «⌘S» mark: the active graph is in this branch, and
            # Save (the bar above) writes this branch. P2 · one way of saving
            # a branch: the per-branch save icon and «Save all files» left the
            # view (Save all files is in the ▾ menu)
            head.label(text="", icon="CHECKMARK")
        writing = writing_in(origin, rows, active)
        if writing:
            sub = col.row()
            sub.separator(factor=2.0)
            sub.label(text=f"Writing in: {writing}", icon="GREASEPENCIL")
        if origin.is_room:
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
            if hasattr(row, "is_publishable"):
                try:
                    from .. import icons_manager
                    line.prop(row, "is_publishable", text="",
                              icon_value=icons_manager.get_icon_value(
                                  "em_publish" if row.is_publishable
                                  else "em_no_publish"))
                except Exception:  # noqa: BLE001
                    line.prop(row, "is_publishable", text="")
            if i == active:
                _draw_active_path(col, row, i, present, origin)


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


def draw_toolbar(layout, context, em_tools, stato) -> None:
    """P2 (6 Oct 2026) · the commands on the graphs as a compact bar of icons
    above the tree, like the toolbar of EMStudio's EMtree: + Add graph,
    ↻ Reload, Save, − Remove, and the rest in the ▾ menu (Save as…, Save all
    files, Multigraph). The names are the tooltips (the operators'
    descriptions; a button off says why with `poll_message_set`)."""
    bar = layout.row(align=True)
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


CLASSES = (EM_OT_graph_activate, EM_OT_graph_origin_save, EM_OT_graph_save_all,
           EM_MT_graph_more)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
