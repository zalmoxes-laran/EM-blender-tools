"""PropertyGroup backing the DTC authoring panel (EMTools).

UI buffer only — the single source of truth is the s3dgraphy graph (see
dtc_graph.py). The kind enums are DATA-DRIVEN from s3dgraphy's ``dtc_kinds``
vocabulary; the process selector is derived live from the active graph. Nothing
here is a Blender scene object.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import PropertyGroup

from . import dtc_graph


# Enum item callbacks must keep their returned lists alive at module scope
# (Blender GC gotcha).
_process_kind_cache = [("", "—", "")]
_input_kind_cache = [("", "—", "")]
_output_kind_cache = [("", "—", "")]
_process_cache = [("", "— none —", "")]


def _kind_items(axis: str, cache: list):
    try:
        kinds = dtc_graph.dtc_kinds().get(axis, [])
    except Exception:
        kinds = []
    items = [(k, k, f"{axis} kind: {k}") for k in kinds] or [("", "—", "")]
    cache.clear()
    cache.extend(items)
    return cache


def _process_items(self, context):
    """The DTC processes in the active graph (id = node id), + a 'new/none' row."""
    items = [("", "— select / add a process —", "")]
    try:
        from ..functions import check_active_graph
        ok, graph = check_active_graph(context, show_message=False)
        if ok and graph is not None:
            for p in dtc_graph.list_processes(graph):
                label = p["name"] or p["id"][:8]
                if p["kind"]:
                    label += f" ({p['kind']})"
                items.append((p["id"], label, "DTC process"))
    except Exception:
        pass
    _process_cache.clear()
    _process_cache.extend(items)
    return _process_cache


class EM_DtcProps(PropertyGroup):
    show: BoolProperty(name="DTC", default=False)
    active_process: EnumProperty(
        name="Process", items=_process_items,
        description="The DTC process (transformation event) to author")
    process_kind: EnumProperty(
        name="Process kind", items=lambda s, c: _kind_items("process", _process_kind_cache),
        description="Kind of processing step (data-driven from dtc_kinds)")
    input_kind: EnumProperty(
        name="Input kind", items=lambda s, c: _kind_items("input", _input_kind_cache),
        description="Acquisition kind (data-driven from dtc_kinds)")
    input_url: StringProperty(name="Input file", description="URL / path of the input Resource")
    output_kind: EnumProperty(
        name="Output kind", items=lambda s, c: _kind_items("output", _output_kind_cache),
        description="Produced object kind (data-driven from dtc_kinds)")
    output_url: StringProperty(name="Output file", description="URL / path of the output Resource")
    derive_output: BoolProperty(
        name="Derived from inputs", default=True,
        description="Also wire the output ─dtc_derived_from→ the process's inputs")
    status: StringProperty(name="", default="")


classes = (EM_DtcProps,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.em_dtc = bpy.props.PointerProperty(type=EM_DtcProps)


def unregister():
    del bpy.types.Scene.em_dtc
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
