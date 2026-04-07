"""
GraphML export operators for EM-blender-tools.

Provides Save (update in-place) and Save As (new file) operators
for writing graph changes back to GraphML files.
"""

import os
import bpy  # type: ignore
from bpy.props import StringProperty  # type: ignore
from bpy_extras.io_utils import ExportHelper  # type: ignore

from s3dgraphy import get_graph
from s3dgraphy.exporter.graphml import GraphMLPatcher


class EM_export_GraphML(bpy.types.Operator):
    """Save changes to the active GraphML file"""
    bl_idname = "export.graphml_update"
    bl_label = "Save GraphML"
    bl_description = (
        "Update the active GraphML file with current graph data. "
        "Existing nodes are updated, new nodes and edges are added"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0:
            return False
        if em_tools.active_file_index >= len(em_tools.graphml_files):
            return False
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        return bool(graphml.graphml_path)

    def execute(self, context):
        from ..functions import normalize_path
        from ..graph_updaters import update_graph_with_scene_data

        em_tools = context.scene.em_tools
        graphml_file = em_tools.graphml_files[em_tools.active_file_index]
        filepath = normalize_path(graphml_file.graphml_path)

        # Get the in-memory graph
        graph = get_graph(graphml_file.name)
        if graph is None:
            self.report({'ERROR'}, "No graph loaded. Import the GraphML first.")
            return {'CANCELLED'}

        # Update graph with scene data (semantic shapes, representation models, etc.)
        update_graph_with_scene_data(graphml_file.name, context=context)

        # Create rotating backup before saving
        try:
            from ..operators.enrich_graphml import rotate_backups
            addon_prefs = context.preferences.addons.get(__package__.split('.')[0])
            max_backups = addon_prefs.preferences.graphml_backup_count if addon_prefs else 2
            backup_path = rotate_backups(filepath, max_backups)
            if backup_path:
                self.report({'INFO'}, f"Backup created: {os.path.basename(backup_path)}")
        except Exception as e:
            self.report({'WARNING'}, f"Could not create backup: {e}")

        # Run the patcher
        try:
            patcher = GraphMLPatcher(filepath, graph)
            patcher.load()

            # Validate EMIDs
            problems = patcher.validate_emids()
            for p in problems:
                self.report({'WARNING'}, p)

            nodes_updated = patcher.update_existing_nodes()
            nodes_added = patcher.add_new_nodes()
            edges_added = patcher.add_new_edges()
            patcher.ensure_svg_resources()
            patcher.save()

            msg = (f"GraphML saved: {nodes_updated} nodes updated, "
                   f"{nodes_added} nodes added, {edges_added} edges added")
            self.report({'INFO'}, msg)
            return {'FINISHED'}

        except FileNotFoundError:
            self.report({'ERROR'}, f"GraphML file not found: {filepath}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error saving GraphML: {str(e)}")
            return {'CANCELLED'}


class EM_export_GraphML_SaveAs(bpy.types.Operator, ExportHelper):
    """Export the active graph to a new GraphML file"""
    bl_idname = "export.graphml_saveas"
    bl_label = "Save GraphML As..."
    bl_description = (
        "Save the active graph to a new GraphML file. "
        "Creates a copy of the original with all current changes applied"
    )
    bl_options = {'REGISTER'}

    filename_ext = ".graphml"
    filter_glob: StringProperty(default="*.graphml", options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0:
            return False
        if em_tools.active_file_index >= len(em_tools.graphml_files):
            return False
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        return bool(graphml.graphml_path)

    def execute(self, context):
        from ..functions import normalize_path
        from ..graph_updaters import update_graph_with_scene_data

        em_tools = context.scene.em_tools
        graphml_file = em_tools.graphml_files[em_tools.active_file_index]
        source_filepath = normalize_path(graphml_file.graphml_path)

        graph = get_graph(graphml_file.name)
        if graph is None:
            self.report({'ERROR'}, "No graph loaded. Import the GraphML first.")
            return {'CANCELLED'}

        update_graph_with_scene_data(graphml_file.name, context=context)

        try:
            patcher = GraphMLPatcher(source_filepath, graph)
            patcher.load()

            problems = patcher.validate_emids()
            for p in problems:
                self.report({'WARNING'}, p)

            patcher.update_existing_nodes()
            patcher.add_new_nodes()
            patcher.add_new_edges()
            patcher.ensure_svg_resources()
            patcher.save(output_path=self.filepath)

            self.report({'INFO'}, f"GraphML saved to: {self.filepath}")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Error saving GraphML: {str(e)}")
            return {'CANCELLED'}


def register():
    bpy.utils.register_class(EM_export_GraphML)
    bpy.utils.register_class(EM_export_GraphML_SaveAs)


def unregister():
    bpy.utils.unregister_class(EM_export_GraphML_SaveAs)
    bpy.utils.unregister_class(EM_export_GraphML)
