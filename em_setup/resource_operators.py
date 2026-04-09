# em_setup/resource_operators.py
"""
Operators for resource collection migration.
The resource_collection type is now integrated into the auxiliary files system,
so most operators use the existing auxiliary.add_file / auxiliary.import_now / etc.
This module provides the migration operator for old projects.
"""

import bpy
from bpy.types import Operator


class RESOURCE_OT_migrate_from_auxiliary(Operator):
    """Migrate legacy resource_folder settings from auxiliary files to dedicated resource_collection entries"""
    bl_idname = "resource.migrate_from_auxiliary"
    bl_label = "Migrate Resources to Collections"
    bl_description = (
        "For each auxiliary file that has resource_folder set, "
        "create a dedicated resource_collection entry and clear the old setting"
    )
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            self.report({'ERROR'}, "No GraphML file loaded")
            return {'CANCELLED'}

        graphml = em_tools.graphml_files[em_tools.active_file_index]
        migrated = 0

        for aux_file in graphml.auxiliary_files:
            # Only migrate non-resource_collection types that have resource_folder set
            if aux_file.file_type == "resource_collection":
                continue
            if not aux_file.resource_folder:
                continue

            # Check if already migrated (same resource_folder in a resource_collection entry)
            already_exists = any(
                a.file_type == "resource_collection" and a.resource_folder == aux_file.resource_folder
                for a in graphml.auxiliary_files
            )
            if already_exists:
                print(f"Skipping '{aux_file.name}': resource_folder already migrated")
                continue

            # Create new resource_collection entry
            new_rc = graphml.auxiliary_files.add()
            new_rc.name = f"{aux_file.name} (resources)"
            new_rc.file_type = "resource_collection"
            new_rc.resource_folder = aux_file.resource_folder
            new_rc.custom_thumbs_path = aux_file.custom_thumbs_path
            new_rc.target_node_types = 'STRATIGRAPHIC'
            new_rc.scan_mode = 'FOLDER_NAME'
            new_rc.auto_reload_on_em_update = aux_file.auto_reload_on_em_update

            # Clear the old resource_folder from the auxiliary file
            aux_file.resource_folder = ""
            aux_file.custom_thumbs_path = ""

            migrated += 1
            print(f"Migrated resource_folder from '{aux_file.name}' to resource collection")

        if migrated > 0:
            graphml.active_auxiliary_index = len(graphml.auxiliary_files) - 1
            self.report({'INFO'}, f"Migrated {migrated} resource collection(s)")
        else:
            self.report({'INFO'}, "No auxiliary files with resource_folder to migrate")

        return {'FINISHED'}


# Registration
classes = (
    RESOURCE_OT_migrate_from_auxiliary,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
