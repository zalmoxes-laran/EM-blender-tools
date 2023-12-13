import bpy
from .functions import *
from bpy.types import Operator
from bpy.types import Menu, Panel, UIList, PropertyGroup
from . import sqlite_io


#####################################################################
#SETUP MENU

class EM_SetupPanel:
    bl_label = "EM setup (v1.4.0) dev8"
    bl_space_type = 'VIEW_3D' 
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        em_settings = scene.em_settings
        obj = context.object
        
        if len(scene.em_list) > 0:
            is_em_list = True
        else:
            is_em_list = False
        #box = layout.box()

        row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="EM file")
        
        if scene.EM_file:
            col = split.column(align=True)
            if is_em_list:
                button_load_text = 'Reload'
                button_load_icon = 'FILE_REFRESH'
            else:
                button_load_text = 'Load'
                button_load_icon = 'IMPORT'
            col.operator("import.em_graphml", icon= button_load_icon, text=button_load_text)
        else:
            col.label(text="Select a GraphML file below", icon='SORT_ASC')
        #row = layout.row()
        if is_em_list:
            col = split.column(align=True)
            op = col.operator("list_icon.update", icon="PRESET", text='Refresh')
            op.list_type = "all"

        row = layout.row(align=True)
        row.prop(context.scene, 'EM_file', toggle = True, text ="")
        
        ############# box con le statistiche del file ##################
        box = layout.box()
        row = box.row(align=True)
        #row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="US/USV")
        #col = split.column()
        col.prop(scene, "em_list", text='')
        col = split.column()
        col.label(text="Periods")
        #col = split.column()
        col.prop(scene, "epoch_list", text='')

        col = split.column()
        col.label(text="Properties")
        #col = split.column()
        col.prop(scene, "em_properties_list", text='')

        col = split.column()
        col.label(text="Sources")
        #col = split.column()
        col.prop(scene, "em_sources_list", text='')

        ################ da qui setto la cartella DosCo ##################

        row = layout.row(align=True)
        box = layout.box()
        row = box.row()
        row.prop(context.scene, 'EMDosCo_dir', toggle = True, text ="DosCo") 
        em_settings = bpy.context.window_manager.em_addon_settings
        row.prop(em_settings, "dosco_advanced_options", text="advanced options")

        if em_settings.dosco_advanced_options:
            row = box.row()
            row.label(text="Populate extractors, documents and combiners using DosCo files:")
            row = box.row()
            row.prop(em_settings, 'overwrite_url_with_dosco_filepath', text = "Overwrite paths")
            row.prop(em_settings, 'preserve_web_url', text = "Preserve web urls (if any)")
        #preserve_web_url = settings.preserve_web_url
        #overwrite_url_with_dosco_filepath = settings.overwrite_url_with_dosco_filepath

# Ora puoi utilizzare `preserve_web_url` e `overwrite_url_with_dosco_filepath` nel tuo addon
 

        ################ da qui setto la lista delle sources ##################

        row = layout.row()
        box = layout.box()
        row = box.row()
        row.label(text="Source file (xlsx)")
        row.operator("load.emdb_xlsx", icon="STICKY_UVS_DISABLE", text='')
        row.operator("open_prefs_panel.em_tools", icon="SETTINGS", text="")
        row = box.row()

        
        row.prop(scene, "EMdb_xlsx_filepath", text="")      

        ################ da qui porzione di pannello per EMdb #####################

        row = layout.row(align=True)
        box = layout.box()
        row = box.row()
        db_type_current = scene.current_db_type
        split = row.split()
        col = split.column()
        col.label(text="EMdb file")
        col = split.column(align=True)
        op = col.operator("import.emdb_sqlite", icon= 'IMPORT', text='Import')
        op.db_type = db_type_current
        col = split.column(align=True)
        col.menu(sqlite_io.EMdb_type_menu.bl_idname, text=db_type_current, icon='COLOR')
        row = box.row()
        #row = layout.row(align=True)
        row.prop(context.scene, 'EMdb_file', toggle = True, text ="")

class VIEW3D_PT_SetupPanel(Panel, EM_SetupPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_SetupPanel"
    bl_context = "objectmode"

#SETUP MENU
#####################################################################

classes = [
    VIEW3D_PT_SetupPanel]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.EMdb_file = StringProperty(
        name = "EM db file",
        default = "",
        description = "Define the path to the EM db (sqlite) file",
        subtype = 'FILE_PATH'
    )   

    bpy.types.Scene.EMDosCo_dir = StringProperty(
        name = "EM DosCo folder",
        default = "",
        description = "Define the path to the EM DosCo folder",
        subtype = 'DIR_PATH'
    )   

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.EMdb_file
    del bpy.types.Scene.EMDosCo_dir
