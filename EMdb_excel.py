import bpy
from bpy.types import Operator, AddonPreferences, Panel
from bpy.props import StringProperty, BoolProperty
import os

import logging
log = logging.getLogger(__name__)

class OBJECT_OT_EM_open_prefs(Operator):
    """Open EM tools preferences panel"""
    bl_idname = "open_prefs_panel.em_tools"
    bl_label = "open EM tools preferences panel"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        bpy.ops.preferences.addon_show(module=__package__)
        return {'FINISHED'}

class OBJECT_OT_load_EMdb_xlsx(Operator):
    """If the button is grey, open preference panel (button with the gears here on the right) and launch installation of necessary dependances"""
    bl_idname = "load.emdb_xlsx"
    bl_label = "Load EMdb xlsx"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        scene = context.scene
        is_active_button = False
        prefs = context.preferences.addons.get(__package__, None)
        if prefs.preferences.is_external_module:# and scene.EMdb_xlsx_filepath is not None:
            is_active_button = True
        return is_active_button
	
    def execute(self, context):
        # import functions for this task
        # execute function
        import pandas
        import openpyxl
        scene = context.scene
        newfile_name = scene.EMdb_xlsx_filepath
        data = pandas.read_excel(newfile_name, sheet_name ='sources')
        df = pandas.DataFrame(data, columns=['Name', 'Description']) 
        print(df)
        for index, row in df.iterrows():
            #print(row['c1'], row['c2'])
            for source_item in scene.em_sources_list:
                if source_item.name == row['Name']:
                    source_item.description = row['Description']

        return {'FINISHED'}
'''
class ToolsPanelEMdbsources:
    bl_label = "EMdb sources list"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.active_object
        #resolution_pano = scene.RES_pano

        #row = layout.row()
        #row.label(text="Google Spreadsheet setup")
        row = layout.row()
        row.label(text="Load Source list xlsx file")
        row.operator("load.emdb_xlsx", icon="STICKY_UVS_DISABLE", text='')
        row.operator("open_prefs_panel.em_tools", icon="SETTINGS", text="")
        row = layout.row()
        layout.prop(scene, "EMdb_xlsx_filepath", text="xlsx path")


class VIEW3D_PT_EMDB_panel(Panel, ToolsPanelEMdbsources):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_EMDB_panel"
    #bl_context = "objectmode"
'''
classes = [
    OBJECT_OT_EM_open_prefs,
    OBJECT_OT_load_EMdb_xlsx,
    #VIEW3D_PT_EMDB_panel,
    ]

# Registration
def register():
    #prima di registrare classi, verifico se ci sono
    #check_external_modules()

    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError as e:
            log.warning('{} is already registered, now unregister and retry... '.format(cls))
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)

    bpy.types.Scene.EMdb_xlsx_filepath = StringProperty(
        name="Path to xlsx file",
        default="",
        description="Path to xlsx file",
        subtype='FILE_PATH'
    )

def unregister():
        
    for cls in classes:
            try:
                bpy.utils.unregister_class(cls)
            except RuntimeError:
                pass
    del bpy.types.Scene.EMdb_xlsx_filepath