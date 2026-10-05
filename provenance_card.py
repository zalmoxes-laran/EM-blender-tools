"""D1 · «Where it comes from»: the DTC of ONE asset as a card, not a panel.

E.D. (5 Oct 2026): «al massimo una card per dire da dove viene un asset
selezionato». The DTC as a panel in Files — an authoring form for processes,
inputs and outputs — goes; the authoring is EMStudio's. What stays in EM Tools
is a card that appears where a list has an asset selected, and says its chain:
the step that made it (process, technique), who and when, with which tool, the
inputs with the common signs of where their bytes are — and «Open in EMStudio»
for the rest.

Where a selection has an asset (measured on Templu Mare, MICRO-IL-PANNELLO-
DICE-IL-VERO): the RM list (its object → the resource it was materialised
from, else the one its RM links), Asset versions (the active object, the same
way), the Document Manager (the document's linked resource), Files (each row is
a resource: its button shows the card under the list, Files having no selection of
its own).

`card(graph, resource_id, states)` is pure: the suite reads it without Blender.
"""


from typing import Any, Dict, List, Optional

#: how many inputs the card names before «+N more»
INPUTS_SHOWN = 4


def _data(node: Any) -> Dict[str, Any]:
    d = getattr(node, "data", None)
    return d if isinstance(d, dict) else {}


def _tool_name(tool: Any) -> str:
    if isinstance(tool, dict):
        return str(tool.get("name") or "")
    return str(tool or "")


def _day(stamp: Any) -> str:
    """`2026-10-05T14:07:39Z` → `2026-10-05`: the card says the day."""
    return str(stamp or "")[:10]


def card(graph: Any, resource_id: str,
         states: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """`{resource, name, steps: [{process, kind, technique, who, when, tool,
    inputs: [{id, name, state}], more}], used_by}` — the chain one hop back
    (what made it) and how many steps used it. `states` maps a resource id to
    its file state (`on_disk`, `on_node`, …, the one resolver's)."""
    from s3dgraphy import api

    states = states or {}
    node = graph.find_node_by_id(str(resource_id)) if resource_id else None
    if node is None:
        return {"resource": None, "name": "", "steps": [], "used_by": 0}
    chain = api.derivation_chain(graph, node.node_id)
    steps: List[Dict[str, Any]] = []
    for event in chain.get("made_by") or []:
        enode = graph.find_node_by_id(event["id"])
        d = _data(enode)
        inputs = []
        for iid in event.get("inputs") or []:
            inode = graph.find_node_by_id(iid)
            inputs.append({"id": iid,
                           "name": str(getattr(inode, "name", "") or iid),
                           "state": states.get(iid, "")})
        steps.append({
            "id": event["id"],
            "process": str(d.get("act_name") or event.get("name") or ""),
            "kind": str(d.get("dtc_kind") or event.get("dtc_kind") or ""),
            "technique": str(d.get("technique") or ""),
            "who": str(d.get("created_by") or d.get("modified_by") or ""),
            "when": _day(d.get("created_at") or d.get("modified_at")),
            "tool": _tool_name(d.get("tool")) or _tool_name(event.get("tool")),
            "inputs": inputs[:INPUTS_SHOWN],
            "more": max(0, len(inputs) - INPUTS_SHOWN),
        })
    return {"resource": node.node_id, "name": str(getattr(node, "name", "") or ""),
            "state": states.get(node.node_id, ""), "steps": steps,
            "used_by": len(chain.get("used_by") or [])}


def lines(c: Dict[str, Any], glyph=lambda state: "") -> List[str]:
    """The card as the sentences it draws (one per line), signs included."""
    if not c.get("resource"):
        return ["no resource selected"]
    out = []
    head = c["name"]
    if c.get("state") and glyph(c["state"]):
        head = f"{glyph(c['state'])} {head}"
    out.append(head)
    if not c["steps"]:
        out.append("no step of its chain is recorded: born here, or brought "
                   "without its provenance")
    for s in c["steps"]:
        what = " · ".join(p for p in (s["process"], s["kind"], s["technique"]) if p)
        out.append(f"made by: {what or 'a step with no name'}")
        by = " · ".join(p for p in (s["who"] and f"by {s['who']}",
                                     s["when"] and f"on {s['when']}",
                                     s["tool"] and f"with {s['tool']}") if p)
        if by:
            out.append(by)
        for i in s["inputs"]:
            sign = glyph(i["state"]) if i["state"] else ""
            out.append(f"from: {(sign + ' ') if sign else ''}{i['name']}")
        if s["more"]:
            out.append(f"from: +{s['more']} more")
    if c.get("used_by"):
        out.append(f"used by {c['used_by']} later step(s)")
    return out


# ── where a selection has an asset ───────────────────────────────────────────

def resource_of_object(graph: Any, obj: Any, scene: Any = None) -> str:  # pragma: no cover — bpy
    """The resource an object shows: the version its mesh shows, the one it
    was materialised from, its asset, else the resource its RM links (the
    master first)."""
    mesh = getattr(obj, "data", None)
    shown = mesh.get("em_version_id") if mesh is not None and hasattr(mesh, "get") else None
    if shown and graph.find_node_by_id(str(shown)) is not None:
        return str(shown)
    for prop in ("em_resource_id", "em_asset_id"):
        rid = obj.get(prop) if obj is not None else None
        if rid and graph.find_node_by_id(str(rid)) is not None:
            return str(rid)
    try:
        from .rm_manager.containers import resolve_rm_node_id
        rm_id = resolve_rm_node_id(graph, obj, scene=scene, migra=False)
    except Exception:  # noqa: BLE001
        rm_id = None
    return resource_linked_to(graph, rm_id) if rm_id else ""


def resource_linked_to(graph: Any, node_id: str) -> str:
    """The resource a node (an RM, a document) links, the master first."""
    linked = [graph.find_node_by_id(e.edge_target) for e in graph.edges
              if e.edge_type == "has_linked_resource" and e.edge_source == node_id]
    linked = [n for n in linked if n is not None
              and getattr(n, "node_type", "") in ("resource", "link")]
    if not linked:
        return ""
    masters = [n for n in linked if _data(n).get("tier") == "master"]
    return (masters or linked)[0].node_id


# ── Blender ─────────────────────────────────────────────────────────────────

def _states() -> Dict[str, str]:  # pragma: no cover — bpy
    try:
        from .sync_manager import file_states
        return {r["id"]: r["state"] for r in file_states.ULTIMI.get("results") or []}
    except Exception:  # noqa: BLE001
        return {}


def _glyph(state: str) -> str:  # pragma: no cover — bpy
    try:
        from .state_symbols import glyph
        return glyph(f"file.{state}") if state else ""
    except Exception:  # noqa: BLE001
        return ""


def draw(layout, context, resource_id: str) -> None:  # pragma: no cover — bpy
    """The card, in a box, for `resource_id` of the active graph (nothing
    when there is no resource)."""
    if not resource_id:
        return
    from .functions import check_active_graph
    ok, graph = check_active_graph(context, show_message=False)
    if not (ok and graph is not None):
        return
    try:
        c = card(graph, resource_id, _states())
    except Exception as exc:  # noqa: BLE001 — a card never breaks a panel
        layout.label(text=f"Where it comes from: {exc}", icon="ERROR")
        return
    if not c.get("resource"):
        return
    # R2 · a file is named by its file, never «Link to D.05»: the one
    # resolver's description, when Files has been checked
    try:
        from .sync_manager import file_states
        said = (file_states.ULTIMI.get("described") or {}).get(c["resource"]) or {}
        if said.get("file"):
            c["name"] = said["file"]
    except Exception:  # noqa: BLE001
        pass
    box = layout.box()
    col = box.column(align=True)
    col.label(text="Where it comes from", icon="NODETREE")
    said = lines(c, _glyph)
    col.label(text=said[0], icon="FILE")
    for line in said[1:]:
        icon = ("SETTINGS" if line.startswith("made by") else
                "IMPORT" if line.startswith("from:") else "BLANK1")
        col.label(text=line[:90], icon=icon)
    op = box.operator("em.open_in_emstudio", text="Open in EMStudio", icon="WINDOW")
    op.node_id = c["resource"]
    op.unit_name = c["name"]


def _classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_OT_provenance_show(bpy.types.Operator):
        """Where this file comes from: its DTC as a card under the list (the
        step that made it, who, when, with which tool, its inputs)"""

        bl_idname = "em.provenance_show"
        bl_label = "Where it comes from"

        resource_id: bpy.props.StringProperty()  # type: ignore

        def execute(self, context):
            wm = context.window_manager
            wm.em_provenance_resource = ("" if wm.em_provenance_resource == self.resource_id
                                         else self.resource_id)
            return {"FINISHED"}

    return (EM_OT_provenance_show,)


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    bpy.types.WindowManager.em_provenance_resource = bpy.props.StringProperty(
        name="Where it comes from", default="",
        description="The file of Files whose card is shown")
    _CLASSES = _classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
    if hasattr(bpy.types.WindowManager, "em_provenance_resource"):
        del bpy.types.WindowManager.em_provenance_resource
