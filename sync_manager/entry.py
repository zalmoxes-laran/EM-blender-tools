"""J1 · entering a room with a file that is not empty: a question, not a merge.

Measured on 5 Oct 2026: the entry merged the room's document into the session
in silence (`operators._adopt_snapshot`, «merged, never substituted»), and the
room's starting package (`blend-packages`) was never offered. Merging is the
cheaper mistake when the file is empty, and the wrong default when it holds
another study: the two get mixed and the next Save writes them together.

So, when the working .blend already has graphs or objects linked to a graph,
before adopting, one question with three answers:

1. **Open the room's .blend** in a new file beside this one — recommended, and
   offered first, when the room has a package: the package carries the scene
   and its libraries, and opening it beside leaves this file as it is;
2. **Start a new file** and download the room's contents into it — this file
   is left as it is (not saved, not touched);
3. **Merge into this file**, with the list of what gets mixed.

With an empty file the entry goes on as before. A re-entry into the room this
file already works in (a seated session, or rows whose origin is that room)
asks nothing: it is the same study.

`is_empty_state` and `choices` are pure (`tests/test_entry_choice.py`); the
reading of the scene and the three gestures are behind them.
"""

# NOT `from __future__ import annotations`: the operator below is built inside a
# function and Blender evaluates its property annotations in these globals.
import os
from typing import Any, Dict, List, Optional

CHOICE_PACKAGE = "PACKAGE"
CHOICE_NEW = "NEW"
CHOICE_MERGE = "MERGE"

#: what was asked last, for the dialog and the smoke (session state)
PENDING: Dict[str, Any] = {}


def is_empty_state(graphs: List[str], linked_objects: int) -> bool:
    """A file with no graph and no object linked to a graph is empty."""
    return not graphs and not linked_objects


def choices(has_package: bool) -> List[Dict[str, Any]]:
    """The three answers, in the order they are offered: the package first
    when the room has one (and then it is the recommended one)."""
    package = {"id": CHOICE_PACKAGE, "text": "Open the room's .blend in a new file beside this one",
               "recommended": has_package, "enabled": has_package}
    new = {"id": CHOICE_NEW, "text": "Start a new file and download the room's contents",
           "recommended": not has_package, "enabled": True}
    merge = {"id": CHOICE_MERGE, "text": "Merge the room into this file",
             "recommended": False, "enabled": True}
    return [package, new, merge] if has_package else [new, merge, package]


# ── Blender ─────────────────────────────────────────────────────────────────

def read_file_state(context) -> Dict[str, Any]:  # pragma: no cover — bpy
    """What this file holds: its graphs (names) and the objects linked to one."""
    import bpy  # type: ignore
    from s3dgraphy import get_graph
    from .scene_check import _BINDING_PROPS
    em_tools = getattr(context.scene, "em_tools", None)
    graphs = []
    for row in list(getattr(em_tools, "graphml_files", ()) or ()):
        g = get_graph(row.name)
        if g is not None and getattr(g, "nodes", None):
            graphs.append(getattr(row, "graph_code", "") or row.name)
    rm = set()
    try:
        rm = {i.name for i in context.scene.rm_list}
    except Exception:  # noqa: BLE001
        pass
    linked = sum(1 for o in bpy.data.objects
                 if o.name in rm or any(o.get(p) for p in _BINDING_PROPS))
    return {"graphs": graphs, "linked_objects": linked,
            "file": os.path.basename(bpy.data.filepath) or "an unsaved file"}


def same_room(context, base: str, room_id: str) -> bool:  # pragma: no cover — bpy
    """This file already works in that room: a seated session, or a row whose
    origin is the room."""
    from . import room_session as _rs
    base = (base or "").rstrip("/")
    for _g, s in _rs.sessions():
        if s.seated and s.room_id == room_id and (s.base_url or "").rstrip("/") == base:
            return True
    em_tools = getattr(context.scene, "em_tools", None)
    for row in list(getattr(em_tools, "graphml_files", ()) or ()):
        if str(getattr(row, "origin_kind", "")) == "ROOM" and \
                str(getattr(row, "origin_room", "")) == room_id:
            return True
    return False


def needs_choice(context, base: str, room_id: str) -> bool:  # pragma: no cover — bpy
    if same_room(context, base, room_id):
        return False
    state = read_file_state(context)
    return not is_empty_state(state["graphs"], state["linked_objects"])


def ask(context, base: str, room_id: str) -> None:  # pragma: no cover — bpy
    """Open the question (headless: remember it, the caller answers)."""
    import bpy  # type: ignore
    PENDING.clear()
    PENDING.update({"base": base, "room_id": room_id, "asked": True})
    if bpy.app.background:
        print(f"[room] entering {room_id} with a file that is not empty: asked "
              f"open the package / new file / merge")
        return
    bpy.ops.em.room_enter_choice("INVOKE_DEFAULT", base=base, room_id=room_id)


def _packages(base: str, room_id: str) -> List[Dict[str, Any]]:  # pragma: no cover
    from . import room as room_cfg
    from . import scene_package
    token = room_cfg._session.get("token")
    room_cfg.set_room(base, room_id, token)
    try:
        return scene_package.list_packages()
    except Exception:  # noqa: BLE001 — no package is an answer too
        return []


def forget_the_other_file() -> int:  # pragma: no cover — bpy
    """The graphs of the file that was open stay in s3dgraphy's manager (it
    lives in the process, not in the .blend): measured, «start a new file»
    came into the room with the copy's GT16 beside the room's graphs. They
    are forgotten here, with the containers remembered for their files."""
    from s3dgraphy.multigraph.multigraph import multi_graph_manager
    from .. import graph_origins
    gone = len(multi_graph_manager.graphs)
    multi_graph_manager.graphs.clear()
    graph_origins.forget_all()
    return gone


def enter_after_load(base: str, room_id: str, token: Optional[str], *,
                     materialise: bool) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Join with the file just loaded (the new file, or the package)."""
    import bpy  # type: ignore
    from . import operators as ops
    forget_the_other_file()
    context = bpy.context
    context.scene.em_room_url = base
    context.scene.em_room_id = room_id
    result = ops.join_room(context, base, room_id, token or "", adopt=True)
    if result.get("ok") and materialise:
        ok, graph = ops.is_graph_available(context)
        if ok:
            from .materialise import materialise as fetch, summarise
            try:
                result["message"] += " · geometry: " + summarise(fetch(graph))
            except Exception as exc:  # noqa: BLE001
                result["message"] += f" · geometry not downloaded: {exc}"
    return result


def answer(context, choice: str, base: str, room_id: str) -> Dict[str, Any]:  # pragma: no cover — bpy
    """Carry out one of the three answers. → join_room's dict (+ `file`)."""
    import bpy  # type: ignore
    from . import operators as ops
    from . import room as room_cfg
    token = room_cfg._session.get("token")
    PENDING.update({"answered": choice})
    if choice == CHOICE_MERGE:
        return ops.join_room(context, base, room_id, token or "", adopt=True)
    if choice == CHOICE_NEW:
        # this file is not saved and not touched: a new, empty one takes its
        # place in this window, and the room's contents come into it
        bpy.ops.wm.read_homefile(use_empty=True)
        out = enter_after_load(base, room_id, token, materialise=True)
        out["file"] = "a new file"
        return out
    if choice == CHOICE_PACKAGE:
        from . import scene_package
        packages = _packages(base, room_id)
        if not packages:
            return {"ok": False, "message": "the room has no starting package"}
        record = packages[0]
        folder = os.path.dirname(bpy.data.filepath) or bpy.app.tempdir
        target = os.path.join(folder, scene_package.package_name(
            record.get("filename") or room_id, record["sha256"]))
        if not os.path.exists(target):
            data = scene_package.get_package(record["sha256"])
            with open(target, "wb") as handle:
                handle.write(data)
            scene_package.unpack_beside(bpy.app.binary_path, target)
        bpy.ops.wm.open_mainfile(filepath=target)
        out = enter_after_load(base, room_id, token, materialise=False)
        out["file"] = target
        return out
    return {"ok": False, "message": f"unknown answer {choice!r}"}


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_OT_room_enter_choice(bpy.types.Operator):
        """This file already holds a study: open the room's .blend beside it,
        start a new file with the room's contents, or merge the room into this
        file"""

        bl_idname = "em.room_enter_choice"
        bl_label = "Enter the room"

        base: bpy.props.StringProperty(default="", options={"HIDDEN"})  # type: ignore
        room_id: bpy.props.StringProperty(default="", options={"HIDDEN"})  # type: ignore
        choice: bpy.props.EnumProperty(  # type: ignore
            name="How",
            items=((CHOICE_PACKAGE, "Open the room's .blend beside this one",
                    "The room's starting package, in a new file beside this one; "
                    "this file is left as it is"),
                   (CHOICE_NEW, "Start a new file",
                    "A new file with the room's contents downloaded; this file is "
                    "left as it is (not saved)"),
                   (CHOICE_MERGE, "Merge into this file",
                    "The room's document merged into this file's graphs")),
            default=CHOICE_NEW)

        def invoke(self, context, event):
            packages = _packages(self.base, self.room_id)
            PENDING["choices"] = choices(bool(packages))
            PENDING["state"] = read_file_state(context)
            self.choice = CHOICE_PACKAGE if packages else CHOICE_NEW
            return context.window_manager.invoke_props_dialog(
                self, width=540, confirm_text="Enter")

        def draw(self, context):
            layout = self.layout
            state = PENDING.get("state") or read_file_state(context)
            layout.label(text=f"{state['file']} already holds a study:", icon="INFO")
            layout.label(text=f"{len(state['graphs'])} graph(s): "
                              f"{', '.join(state['graphs'][:4])}"
                         + (" …" if len(state["graphs"]) > 4 else ""), icon="BLANK1")
            layout.label(text=f"{state['linked_objects']} object(s) linked to a graph",
                         icon="BLANK1")
            col = layout.column()
            for c in PENDING.get("choices") or choices(False):
                row = col.row()
                row.enabled = c["enabled"]
                row.prop_enum(self, "choice", c["id"],
                              text=c["text"] + ("  (recommended)" if c["recommended"] else ""))
            if self.choice == CHOICE_MERGE:
                layout.label(text="The room's graphs are merged into these by UUID; "
                                  "the next Save writes them together.", icon="ERROR")

        def execute(self, context):
            base, room_id, choice = self.base, self.room_id, self.choice
            result = answer(context, choice, base, room_id)
            # after a new file is loaded this operator's own data may be gone:
            # what is said goes through the console and the panel's log
            print(f"[room] {room_id}: {result.get('message')}")
            try:
                from .windows import note_transition
                note_transition(f"entered {room_id} ({choice.lower()}): "
                                f"{str(result.get('message'))[:80]}")
            except Exception:  # noqa: BLE001
                pass
            return {"FINISHED"} if result.get("ok") else {"CANCELLED"}

    return (EM_OT_room_enter_choice,)


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
