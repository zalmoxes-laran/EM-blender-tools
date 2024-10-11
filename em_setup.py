import bpy
from .S3Dgraphy import load_graph, get_graph
from .S3Dgraphy import *


class EMToolsProperties(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="GraphML File")
    expanded: bpy.props.BoolProperty(name="Auxiliary files", default=False)
    graphml_path: bpy.props.StringProperty(name="GraphML Path", subtype='FILE_PATH')  # Aggiungiamo il campo per il percorso
    dosco_dir: bpy.props.StringProperty(name="DosCo Directory", subtype='DIR_PATH')
    xlsx_filepath: bpy.props.StringProperty(name="Source File (xlsx)", subtype='FILE_PATH')
    emdb_filepath: bpy.props.StringProperty(name="EMdb File (sqlite)", subtype='FILE_PATH')

class EMToolsSettings(bpy.types.PropertyGroup):
    graphml_files: bpy.props.CollectionProperty(type=EMToolsProperties)
    active_file_index: bpy.props.IntProperty()

class EMTOOLS_UL_files(bpy.types.UIList):
    """UIList to display the GraphML files"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name)

class EM_SetupPanel(bpy.types.Panel):
    bl_label = "EM Tools Setup"
    bl_idname = "VIEW3D_PT_EM_Tools_Setup"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "EM"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_tools = scene.em_tools

        # List of GraphML files
        row = layout.row()

        row.template_list("EMTOOLS_UL_files", "", em_tools, "graphml_files", em_tools, "active_file_index", rows=3)


        row = layout.row(align=True)
        row.operator('em_tools.add_file', text="Add GraphML", icon="ADD")
        row.operator('em_tools.remove_file', text="Remove GraphML", icon="REMOVE")

        # Details for selected GraphML file
        if em_tools.active_file_index >= 0 and em_tools.graphml_files:
            active_file = em_tools.graphml_files[em_tools.active_file_index]


            # Path to GraphML
            row = layout.row(align=True)
            row.prop(active_file, "graphml_path", text="GraphML Path")

            # Button to trigger the import
            row = layout.row(align=True)
            row.operator("import.em_graphml", text="Import GraphML").graphml_index = em_tools.active_file_index

            box = layout.box()
            box.prop(active_file, "expanded", icon="TRIA_DOWN" if active_file.expanded else "TRIA_RIGHT", emboss=False)

            if active_file.expanded:

                # Path to DosCo folder
                box.prop(active_file, "dosco_dir", text="DosCo Directory")
                # XLSX file
                box.prop(active_file, "xlsx_filepath", text="Source File (xlsx)")
                # EMdb file
                box.prop(active_file, "emdb_filepath", text="EMdb File (sqlite)")


class EMToolsAddFile(bpy.types.Operator):
    bl_idname = "em_tools.add_file"
    bl_label = "Add GraphML File"

    def execute(self, context):
        em_tools = context.scene.em_tools
        new_file = em_tools.graphml_files.add()
        new_file.name = "New GraphML File"
        em_tools.active_file_index = len(em_tools.graphml_files) - 1
        return {'FINISHED'}

class EMToolsRemoveFile(bpy.types.Operator):
    bl_idname = "em_tools.remove_file"
    bl_label = "Remove GraphML File"

    def execute(self, context):
        em_tools = context.scene.em_tools
        if em_tools.active_file_index >= 0:
            em_tools.graphml_files.remove(em_tools.active_file_index)
            em_tools.active_file_index = min(max(0, em_tools.active_file_index - 1), len(em_tools.graphml_files) - 1)
            graphml = em_tools.graphml_files[self.graphml_index]
            remove_graph(graphml.name)
        return {'FINISHED'}

# Lista delle classi da registrare
classes = [
    EMToolsProperties,
    EMToolsSettings,
    EMTOOLS_UL_files,
    EM_SetupPanel,
    EMToolsAddFile,
    EMToolsRemoveFile
]

def register():
    # Itera sulla lista per registrare le classi
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.em_tools = bpy.props.PointerProperty(type=EMToolsSettings)

def unregister():
    # Itera sulla lista per cancellare la registrazione delle classi
    for cls in reversed(classes):  # Usa reversed per evitare problemi di dipendenze
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.em_tools

if __name__ == "__main__":
    register()
