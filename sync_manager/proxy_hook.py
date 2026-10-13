"""MICRO RM e aggancio (13 Oct 2026) · an object «only here» becomes the proxy
of a unit: a gesture you can see.

Measured in `tavolo-2026-10-12`, editor2, 17:50: «US 4» (an Icosphere of 42
vertices) was `em_only_here` — the sync's check resolves an object to a unit
by its NAME (`scene_check.scene_objects`), and the unit is called «US 4 · B
online (più recente) 19:56:23» in the room. The gesture that binds them
existed (`listitem.toobj`, the link icon beside «Type: US» in the
Stratigraphy Manager), but E.D. did not find it: «è come se mancasse il
comando». Now:

* **Files** says the objects not in the graph («1 object here is not in the
  graph: US 4») with **«Make it the proxy of…»** beside each;
* the same gesture in **Object ▸ EM**;
* the unit is chosen by name, the similar ones first (`rank_units`: «US 4» →
  «US 4 · B online…» before «US 40»);
* the object takes the unit's proxy name (the addon's one naming rule), and
  the next «Sync the scene…» offers it ticked as the unit's proxy, which goes
  in the canonical form (unit → geometry property → shape → resource,
  `commands.promote_model`).

The ranking and the sentence are pure, measured by `tests/test_rm_aggancio.py`.
"""

# NOT `from __future__ import annotations`: the operator's properties are
# read in this module's globals (see scene_check).
import re
from typing import Any, Dict, List, Optional, Tuple

#: written on the object by the gesture: the unit it was made the proxy of.
#: «Sync the scene…» ticks such a new proxy for you.
PROP_PROXY_OF = "em_proxy_of"


# ── pure ────────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _tight(text: str) -> str:
    return re.sub(r"[\s_\-.]+", "", _norm(text))


def _score(object_name: str, unit: Tuple[str, str]) -> int:
    base = re.sub(r"\.\d{3}$", "", str(object_name or ""))
    n, t = _norm(base), _tight(base)
    uid, name = unit
    un, ut = _norm(name), _tight(name)
    if not n:
        return 9
    if un == n or _norm(uid) == n:
        return 0
    if ut == t or _tight(uid) == t:
        return 1
    if un.startswith(n) and not un[len(n):len(n) + 1].isalnum():
        return 2
    if ut.startswith(t) and not ut[len(t):len(t) + 1].isdigit():
        return 3
    if re.search(rf"(?<!\w){re.escape(n)}(?!\w)", un):
        return 4
    return 9


def rank_units(object_name: str, units: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """`units`: ``[(id, name)]`` → the same, the names most like the
    object's first, then the others by name. «US 4» is like «US 4 · B online
    (più recente) 19:56:23» (the name, then a word boundary) and not like
    «US 40»; «US_4» and «us4» are like «US 4». A Blender copy suffix
    (``.001``) does not count."""
    return sorted(units, key=lambda u: (_score(object_name, u), _norm(u[1]), u[0]))


def alike(object_name: str, unit: Tuple[str, str]) -> bool:
    """The unit's name is like the object's (what `rank_units` puts first)."""
    return _score(object_name, unit) < 9


def not_in_graph_line(names: List[str]) -> Optional[str]:
    """«1 object here is not in the graph: US 4» — or None."""
    if not names:
        return None
    shown = ", ".join(names[:4]) + (f" … +{len(names) - 4}" if len(names) > 4 else "")
    if len(names) == 1:
        return f"1 object here is not in the graph: {shown}"
    return f"{len(names)} objects here are not in the graph: {shown}"


# ── Blender ─────────────────────────────────────────────────────────────────

def _graph(context):  # pragma: no cover — bpy
    try:
        from ..functions import is_graph_available
        ok, graph = is_graph_available(context)
        return graph if ok else None
    except Exception:  # noqa: BLE001
        return None


def graph_units(graph) -> List[Tuple[str, str]]:  # pragma: no cover — bpy
    from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
    return [(str(n.node_id), str(getattr(n, "name", "") or n.node_id))
            for n in getattr(graph, "nodes", []) if isinstance(n, StratigraphicNode)]


def not_in_graph(context) -> List[str]:  # pragma: no cover — bpy
    """The geometry objects the last check marked «only here»."""
    import bpy  # type: ignore
    from .scene_check import GEOMETRY_TYPES, PROP_ONLY_HERE
    return sorted(o.name for o in bpy.data.objects
                  if o.get(PROP_ONLY_HERE) and o.type in GEOMETRY_TYPES)


def make_proxy(context, graph, obj, unit_id: str) -> Dict[str, Any]:  # pragma: no cover — bpy
    """`obj` becomes the proxy of `unit_id`: it takes the unit's proxy name,
    leaves «only here», and is marked for the next Sync. → ``{ok, name,
    unit, error}``."""
    import bpy  # type: ignore
    from ..operators.addon_prefix_helpers import node_name_to_proxy_name
    from .scene_check import PROP_ONLY_HERE, ULTIMA_VERIFICA

    node = graph.find_node_by_id(unit_id) if graph is not None else None
    if node is None:
        return {"ok": False, "error": f"{unit_id} is not a unit of this graph"}
    name = node_name_to_proxy_name(node.name, context=context, graph=graph)
    other = bpy.data.objects.get(name)
    if other is not None and other is not obj:
        return {"ok": False, "error": f"{node.name} already has a proxy here: {other.name}"}
    before = obj.name
    obj.name = name
    if obj.name != name:
        return {"ok": False, "error": f"Blender did not give {before} the name {name!r} "
                                      f"(too long?)"}
    if PROP_ONLY_HERE in obj.keys():
        del obj[PROP_ONLY_HERE]
    obj[PROP_PROXY_OF] = str(unit_id)
    if before in (ULTIMA_VERIFICA.get("only_here") or []):
        ULTIMA_VERIFICA["only_here"] = [n for n in ULTIMA_VERIFICA["only_here"] if n != before]
    try:
        from ..object_cache import invalidate_object_cache
        invalidate_object_cache()
        from ..functions import update_icons
        update_icons(context, "em_list")
    except Exception as exc:  # noqa: BLE001 — the binding stands
        print(f"[proxy] lists not refreshed after binding {name}: {exc}")
    return {"ok": True, "name": name, "unit": node.name, "was": before}


_ITEMS: List[Tuple[str, str, str]] = []


def _unit_items(_self, _context):  # pragma: no cover — bpy
    # Blender keeps only references to these strings: they live in the module
    return _ITEMS or [("", "No unit in the graph", "")]


def _operator_classes():  # pragma: no cover — bpy
    import bpy  # type: ignore

    class EM_OT_make_proxy_of(bpy.types.Operator):
        """This object becomes the proxy of a stratigraphic unit of the graph:
        it takes the unit's name, and the next «Sync the scene…» sends it as
        the unit's proxy"""
        bl_idname = "em.make_proxy_of"
        bl_label = "Make it the proxy of…"
        bl_options = {"REGISTER", "UNDO"}

        object_name: bpy.props.StringProperty(  # type: ignore
            name="Object", description="The object (empty: the active one)")
        unit: bpy.props.EnumProperty(  # type: ignore
            name="Unit", items=_unit_items,
            description="The unit this object is the proxy of (similar names first)")

        @classmethod
        def poll(cls, context):
            if _graph(context) is None:
                cls.poll_message_set("No graph loaded")
                return False
            return True

        def _object(self, context):
            import bpy  # type: ignore
            if self.object_name:
                return bpy.data.objects.get(self.object_name)
            obj = context.active_object
            return obj if obj is not None and obj.type == "MESH" else None

        def invoke(self, context, event):
            obj = self._object(context)
            if obj is None:
                self.report({"ERROR"}, "Select the object to make a proxy")
                return {"CANCELLED"}
            self.object_name = obj.name
            ranked = rank_units(obj.name, graph_units(_graph(context)))
            close = {u[0] for u in ranked if alike(obj.name, u)}
            _ITEMS[:] = [(uid, name, ("similar name · " if uid in close else "") + uid)
                         for uid, name in ranked]
            if not _ITEMS:
                self.report({"ERROR"}, "The graph has no stratigraphic unit")
                return {"CANCELLED"}
            self.unit = _ITEMS[0][0]
            return context.window_manager.invoke_props_dialog(self, width=460)

        def draw(self, context):
            col = self.layout.column()
            col.label(text=f"«{self.object_name}» becomes the proxy of:", icon="LINKED")
            col.prop(self, "unit", text="")
            close = [i for i in _ITEMS if i[2].startswith("similar")]
            if close:
                col.label(text="Similar names first: " + ", ".join(i[1] for i in close[:3]),
                          icon="BLANK1")
            col.label(text="It takes the unit's name; the next Sync sends it as its proxy.",
                      icon="INFO")

        def execute(self, context):
            obj = self._object(context)
            graph = _graph(context)
            if obj is None or graph is None or not self.unit:
                self.report({"ERROR"}, "nothing to bind: no object, graph or unit")
                return {"CANCELLED"}
            out = make_proxy(context, graph, obj, self.unit)
            if not out["ok"]:
                self.report({"ERROR"}, out["error"])
                return {"CANCELLED"}
            self.report({"INFO"}, f"{out['was']} is the proxy of {out['unit']} now: "
                                  f"«Sync the scene…» sends it")
            return {"FINISHED"}

    class EM_MT_object_em(bpy.types.Menu):
        """EM gestures on the selected object"""
        bl_idname = "EM_MT_object_em"
        bl_label = "EM"

        def draw(self, context):
            self.layout.operator("em.make_proxy_of", icon="LINKED").object_name = ""

    return (EM_OT_make_proxy_of, EM_MT_object_em)


def _object_menu(self, context):  # pragma: no cover — bpy
    self.layout.separator()
    self.layout.menu("EM_MT_object_em")


def draw_not_in_graph(layout, context) -> None:  # pragma: no cover — bpy
    """Files: the objects not in the graph, each with «Make it the proxy of…»."""
    names = not_in_graph(context)
    line = not_in_graph_line(names)
    if not line:
        return
    box = layout.box()
    box.label(text=line, icon="QUESTION")
    for name in names[:6]:
        row = box.row(align=True)
        row.label(text=name, icon="OBJECT_DATA")
        row.operator("em.make_proxy_of", text="Make it the proxy of…",
                     icon="LINKED").object_name = name


_CLASSES: tuple = ()


def register():  # pragma: no cover — bpy
    import bpy  # type: ignore
    global _CLASSES
    _CLASSES = _operator_classes()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_object.append(_object_menu)


def unregister():  # pragma: no cover — bpy
    import bpy  # type: ignore
    try:
        bpy.types.VIEW3D_MT_object.remove(_object_menu)
    except Exception:  # noqa: BLE001
        pass
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # noqa: BLE001
            pass
