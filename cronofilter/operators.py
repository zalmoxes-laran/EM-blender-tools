# cronofilter/operators.py
"""CronoFilter operators: add/remove/move horizons, save/load to .cf.json, auto-generate from epochs."""

import json

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .properties import _hex_to_rgb


class CF_OT_AddHorizon(Operator):
    """Add a new chronological horizon"""
    bl_idname = "cronofilter.add_horizon"
    bl_label = "Add Horizon"
    bl_description = "Add a new chronological horizon"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cf_settings = context.scene.cf_settings
        new_horizon = cf_settings.horizons.add()
        new_horizon.label = f"Horizon_{len(cf_settings.horizons)}"
        cf_settings.active_horizon_index = len(cf_settings.horizons) - 1
        return {'FINISHED'}


class CF_OT_RemoveHorizon(Operator):
    """Remove the active chronological horizon"""
    bl_idname = "cronofilter.remove_horizon"
    bl_label = "Remove Horizon"
    bl_description = "Remove the selected chronological horizon"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cf_settings = context.scene.cf_settings
        if cf_settings.horizons and cf_settings.active_horizon_index >= 0:
            cf_settings.horizons.remove(cf_settings.active_horizon_index)
            cf_settings.active_horizon_index = max(0, cf_settings.active_horizon_index - 1)
        return {'FINISHED'}


class CF_OT_MoveHorizon(Operator):
    """Move horizon up or down in the list"""
    bl_idname = "cronofilter.move_horizon"
    bl_label = "Move Horizon"
    bl_description = "Move the selected horizon up or down"
    bl_options = {'REGISTER', 'UNDO'}

    direction: StringProperty(default="UP") # type: ignore

    def execute(self, context):
        cf_settings = context.scene.cf_settings
        current_index = cf_settings.active_horizon_index

        if self.direction == "UP" and current_index > 0:
            cf_settings.horizons.move(current_index, current_index - 1)
            cf_settings.active_horizon_index = current_index - 1
        elif self.direction == "DOWN" and current_index < len(cf_settings.horizons) - 1:
            cf_settings.horizons.move(current_index, current_index + 1)
            cf_settings.active_horizon_index = current_index + 1

        return {'FINISHED'}


class CF_OT_SaveHorizons(Operator, ExportHelper):
    """Save chronological horizons to .cf.json file"""
    bl_idname = "cronofilter.save_horizons"
    bl_label = "Save Horizons"
    bl_description = "Save chronological horizons to a .cf.json file"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".cf.json"
    filter_glob: StringProperty(default="*.cf.json", options={'HIDDEN'}) # type: ignore

    def execute(self, context):
        try:
            cf_settings = context.scene.cf_settings

            def color_to_hex(color_vector):
                r, g, b = color_vector
                return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

            export_data = {
                "version": "1.0",
                "type": "cronofilter_horizons",
                "horizons": {},
            }

            for i, horizon in enumerate(cf_settings.horizons):
                horizon_id = f"custom_horizon_{i}"
                export_data["horizons"][horizon_id] = {
                    "name": horizon.label,
                    "start": horizon.start_time,
                    "end": horizon.end_time,
                    "color": color_to_hex(horizon.color),
                    "enabled": horizon.enabled,
                }

            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)

            self.report({'INFO'}, f"Horizons saved to {self.filepath}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to save horizons: {str(e)}")
            return {'CANCELLED'}


class CF_OT_LoadHorizons(Operator, ImportHelper):
    """Load chronological horizons from .cf.json file"""
    bl_idname = "cronofilter.load_horizons"
    bl_label = "Load Horizons"
    bl_description = "Load chronological horizons from a .cf.json file"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".cf.json"
    filter_glob: StringProperty(default="*.cf.json", options={'HIDDEN'}) # type: ignore

    def execute(self, context):
        try:
            cf_settings = context.scene.cf_settings

            def hex_to_color(hex_string):
                hex_string = hex_string.lstrip('#')
                if len(hex_string) != 6:
                    return (0.5, 0.5, 0.5)
                try:
                    r = int(hex_string[0:2], 16) / 255.0
                    g = int(hex_string[2:4], 16) / 255.0
                    b = int(hex_string[4:6], 16) / 255.0
                    return (r, g, b)
                except ValueError:
                    return (0.5, 0.5, 0.5)

            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if data.get("type") != "cronofilter_horizons":
                self.report({'ERROR'}, "Invalid file format - not a CronoFilter horizons file")
                return {'CANCELLED'}

            cf_settings.horizons.clear()

            horizons_data = data.get("horizons", {})
            for _horizon_id, horizon_data in horizons_data.items():
                new_horizon = cf_settings.horizons.add()
                new_horizon.label = horizon_data.get("name", "Unnamed")
                new_horizon.start_time = horizon_data.get("start", 0)
                new_horizon.end_time = horizon_data.get("end", 100)
                new_horizon.color = hex_to_color(horizon_data.get("color", "#808080"))
                new_horizon.enabled = horizon_data.get("enabled", True)

            cf_settings.active_horizon_index = 0
            self.report({'INFO'}, f"Loaded {len(cf_settings.horizons)} horizons from {self.filepath}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to load horizons: {str(e)}")
            return {'CANCELLED'}


class CF_OT_AutoHorizons(Operator):
    """Generate horizons automatically from all loaded graphs' epochs"""
    bl_idname = "cronofilter.auto_horizons"
    bl_label = "Auto from Epochs"
    bl_description = "Generate chronological horizons by intersecting epochs from all loaded graphs"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        cf_settings = scene.cf_settings

        from ..landscape_system.populate_functions import get_all_loaded_graphs

        all_graphs = get_all_loaded_graphs(context)
        if not all_graphs:
            self.report({'WARNING'}, "No graphs loaded")
            return {'CANCELLED'}

        # Collect all epoch time boundaries
        breakpoints = set()
        epoch_info = []  # (start, end, name, color, graph_code)

        for graph_code, graph in all_graphs.items():
            for node in graph.nodes:
                if hasattr(node, 'node_type') and node.node_type == 'EpochNode':
                    s = getattr(node, 'start_time', None)
                    e = getattr(node, 'end_time', None)
                    if s is not None and e is not None:
                        try:
                            s_val = float(s)
                            e_val = float(e)
                        except (ValueError, TypeError):
                            continue
                        breakpoints.add(s_val)
                        breakpoints.add(e_val)
                        color = getattr(node, 'color', '#808080')
                        epoch_info.append((s_val, e_val, node.name, color, graph_code))

        if len(breakpoints) < 2:
            self.report({'WARNING'}, "Not enough epoch data to generate horizons")
            return {'CANCELLED'}

        sorted_bp = sorted(breakpoints)
        cf_settings.horizons.clear()

        for i in range(len(sorted_bp) - 1):
            bp_start = sorted_bp[i]
            bp_end = sorted_bp[i + 1]

            # Find the best epoch for this interval:
            # 1. Prefer the most specific epoch that fully contains the interval
            # 2. Fallback: the epoch with the most overlap
            best_epoch = None
            best_span = float('inf')
            best_overlap_epoch = None
            best_overlap = 0.0

            for ep_start, ep_end, ep_name, ep_color, ep_graph in epoch_info:
                if ep_start <= bp_start and ep_end >= bp_end:
                    span = ep_end - ep_start
                    if span < best_span:
                        best_span = span
                        best_epoch = (ep_name, ep_color, ep_graph)
                else:
                    overlap_start = max(bp_start, ep_start)
                    overlap_end = min(bp_end, ep_end)
                    overlap = max(0.0, overlap_end - overlap_start)
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_overlap_epoch = (ep_name, ep_color, ep_graph)

            chosen = best_epoch or best_overlap_epoch

            new_h = cf_settings.horizons.add()
            new_h.start_time = int(bp_start)
            new_h.end_time = int(bp_end)
            new_h.enabled = True

            if chosen:
                new_h.label = f"{chosen[0]} ({chosen[2]})"
                new_h.color = _hex_to_rgb(chosen[1])
            else:
                new_h.label = f"{int(bp_start)}-{int(bp_end)}"

        cf_settings.active_horizon_index = 0
        self.report({'INFO'}, f"Generated {len(cf_settings.horizons)} horizons from {len(epoch_info)} epochs")
        return {'FINISHED'}


classes = (
    CF_OT_AddHorizon,
    CF_OT_RemoveHorizon,
    CF_OT_MoveHorizon,
    CF_OT_SaveHorizons,
    CF_OT_LoadHorizons,
    CF_OT_AutoHorizons,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
