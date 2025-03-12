import bpy # type: ignore
import xml.etree.ElementTree as ET
import os
import sys
import bpy.props as prop # type: ignore
import subprocess
from bpy.props import StringProperty # type: ignore
from bpy.types import Panel, UIList # type: ignore
from .functions import *

#####################################################################
#Paradata Section

class EM_ParadataPanel:
    bl_label = "Paradata Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Restituisce True se mode_switch è False, quindi il pannello viene mostrato solo in modalità 3D GIS
        return em_tools.mode_switch

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object
        row = layout.row()

        # define variables 
        if scene.paradata_streaming_mode:
            property_list_var = "em_v_properties_list"
            property_list_index_var = "em_v_properties_list_index"
            property_list_cmd = "scene.em_v_properties_list"
            property_list_index_cmd = "scene.em_v_properties_list_index"

            combiner_list_var = "em_v_combiners_list"
            combiner_list_index_var = "em_v_combiners_list_index"
            combiner_list_cmd = "scene.em_v_combiners_list"
            combiner_list_index_cmd = "scene.em_v_combiners_list_index"

            extractor_list_var = "em_v_extractors_list"
            extractor_list_index_var = "em_v_extractors_list_index"
            extractor_list_cmd = "scene.em_v_extractors_list"
            extractor_list_index_cmd = "scene.em_v_extractors_list_index"

            source_list_var = "em_v_sources_list"
            source_list_index_var = "em_v_sources_list_index"
            source_list_cmd = "scene.em_v_sources_list"
            source_list_index_cmd = "scene.em_v_sources_list_index"

        else:
            property_list_var = "em_properties_list"
            property_list_index_var = "em_properties_list_index"
            property_list_cmd = "scene.em_properties_list"
            property_list_index_cmd = "scene.em_properties_list_index"

            combiner_list_var = "em_combiners_list"
            combiner_list_index_var = "em_combiners_list_index"
            combiner_list_cmd = "scene.em_combiners_list"
            combiner_list_index_cmd = "scene.em_combiners_list_index"

            extractor_list_var = "em_extractors_list"
            extractor_list_index_var = "em_extractors_list_index"
            extractor_list_cmd = "scene.em_extractors_list"
            extractor_list_index_cmd = "scene.em_extractors_list_index"  

            source_list_var = "em_sources_list"
            source_list_index_var = "em_sources_list_index"
            source_list_cmd = "scene.em_sources_list"
            source_list_index_cmd = "scene.em_sources_list_index"           

    ###############################################################################
    ##          Properties
    ###############################################################################

        len_property_var = "len("+property_list_cmd+")"
        if eval(property_list_index_cmd) >= 0 and eval(len_property_var) > 0:

            # layout.row().separator()

            row.label(text="Properties: ("+str(eval(len_property_var))+")")
            row.prop(scene, "prop_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
            row = layout.row()
            row.template_list("EM_UL_properties_managers", "", scene, property_list_var, scene, property_list_index_var, rows=2)

            #item_source = scene.em_properties_list[scene.em_properties_list_index]
            item_property = eval(property_list_cmd)[eval(property_list_index_cmd)]
            box = layout.box()
            row = box.row(align=True)
            row = box.row()
            row.prop(item_property, "name", text="", icon='FILE_TEXT')
            row = box.row()
            row.prop(item_property, "description", text="", slider=True, emboss=True, icon='TEXT')
        else:
            row.label(text="No paradata here :-(")
    ###############################################################################
    ##          Combiners
    ###############################################################################

        len_combiner_var = "len("+combiner_list_cmd+")"
        if eval(combiner_list_index_cmd) >= 0 and eval(len_combiner_var) > 0:

            # layout.row().separator()

            row = layout.row()
            row.label(text="Combiners: ("+str(eval(len_combiner_var))+")")
            row.prop(scene, "comb_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
            row = layout.row()
            row.template_list("EM_UL_combiners_managers", "", scene, combiner_list_var, scene, combiner_list_index_var, rows=1)
        
            item_property = eval(combiner_list_cmd)[eval(combiner_list_index_cmd)]
            box = layout.box()
            row = box.row(align=True)
            row = box.row()
            row.prop(item_property, "name", text="", icon='FILE_TEXT')
            row = box.row()
            row.prop(item_property, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_property, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            op.node_type = combiner_list_var
            
    ###############################################################################
    ##          Extractors
    ###############################################################################

        len_source_var = "len("+extractor_list_cmd+")"
        if eval(extractor_list_index_cmd) >= 0 and eval(len_source_var) > 0:

            # layout.row().separator()

            row = layout.row()
            row.label(text="Extractors: ("+str(eval(len_source_var))+")")
            row.prop(scene, "extr_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
            row = layout.row()
            row.template_list("EM_UL_extractors_managers", "", scene, extractor_list_var, scene, extractor_list_index_var, rows=2)

            item_source = eval(extractor_list_cmd)[eval(extractor_list_index_cmd)]
            box = layout.box()
            row = box.row(align=True)
            row = box.row()
            row.prop(item_source, "name", text="", icon='FILE_TEXT')
            op = row.operator("listitem.toobj", icon="PASTEDOWN", text='')
            op.list_type = extractor_list_var
            
            if scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                op = row.operator("select.fromlistitem", text='', icon="MESH_CUBE")
                op.list_type = extractor_list_var
            else:
                row.label(text="", icon='MESH_CUBE')
            if obj:
                if check_if_current_obj_has_brother_inlist(obj.name, extractor_list_var):
                    op = row.operator("select.listitem", text='', icon="LONGDISPLAY")
                    op.list_type = extractor_list_var
                else:
                    row.label(text="", icon='LONGDISPLAY')   
            
            row = box.row()
            row.prop(item_source, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_source, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            op.node_type = extractor_list_var

    ###############################################################################
    ##          Sources
    ###############################################################################

        len_source_var = "len("+source_list_cmd+")"
        if eval(source_list_index_cmd) >= 0 and eval(len_source_var) > 0:

            # layout.row().separator()

            row = layout.row()
            row.label(text="Docs: ("+str(eval(len_source_var))+")")
            
            row = layout.row()

            row.template_list("EM_UL_sources_managers", "", scene, source_list_var, scene, source_list_index_var, rows=2)

            item_source = eval(source_list_cmd)[eval(source_list_index_cmd)]
            box = layout.box()
            row = box.row()
            row.prop(item_source, "name", text="", icon='FILE_TEXT')
            split = row.split()
            op = row.operator("listitem.toobj", icon="PASTEDOWN", text='')
            op.list_type = source_list_var
            
            #split = layout.split()
            if scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                #col = split.column()
                op = row.operator("select.fromlistitem", text='', icon="MESH_CUBE")
                op.list_type = source_list_var
            else:
                #col = split.column()
                row.label(text="", icon='MESH_CUBE')
            if obj:
                if check_if_current_obj_has_brother_inlist(obj.name, source_list_var):
                    #col = split.column(align=True)
                    op = row.operator("select.listitem", text='', icon="LONGDISPLAY")
                    op.list_type = source_list_var
                else:
                    #col = split.column()
                    row.label(text="", icon='LONGDISPLAY')              
            
            row = box.row()
            row.prop(item_source, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_source, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            op.node_type = source_list_var
            row = box.row()

class VIEW3D_PT_ParadataPanel(Panel, EM_ParadataPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ParadataPanel"
    bl_context = "objectmode"

class EM_UL_sources_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.22, align = True)
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon=item.icon_url)

class EM_UL_properties_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.4, align = True)
        layout.label(text = item.name)
        layout.label(text = item.description)

class EM_UL_combiners_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.25, align = True)
        layout.label(text = item.name)
        layout.label(text = item.description)

class EM_UL_extractors_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.25, align = True)
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon=item.icon_url)

# Paradata section 
#####################################################################


#### da qui si definiscono le funzioni e gli operatori

class EM_files_opener(bpy.types.Operator):
    """If the button is grey, set the path to a DosCo folder in the EM setup panel above"""
    bl_idname = "open.file"
    bl_label = "Open a file using external software or a url using the default system browser"
    bl_options = {"REGISTER", "UNDO"}

    node_type: StringProperty() # type: ignore

    #@classmethod
    #def poll(cls, context):
        # The button works if DosCo and the url field are valorised
    #    return context.scene.EMDosCo_dir 

    def execute(self, context):
        scene = context.scene        
        file_res_path = eval("scene."+self.node_type+"[scene."+self.node_type+"_index].url")
        if is_valid_url(file_res_path): # nel caso nel nodo fonte ci sia una risorsa online
            print(file_res_path)
            bpy.ops.wm.url_open(url=file_res_path)

        else: # nel caso nel nodo fonte ci sia una risorsa locale
            basedir = bpy.path.abspath(scene.EMDosCo_dir)
            path_to_file = os.path.join(basedir, file_res_path)
            if os.path.exists(path_to_file):
                try:
                    if os.name == 'nt':  # Windows
                        os.startfile(path_to_file)
                    elif os.name == 'posix':  # macOS, Linux
                        opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                        subprocess.run([opener, path_to_file])
                except Exception as e:
                    print("Error when opening the file:", e)
                    self.report({'WARNING'}, "Cannot open file: " + str(e))
                    return {'CANCELLED'}
            
        return {'FINISHED'}

# aggiungere icona con presenza autori: 'COMMUNITY' oppure assenza 'QUESTION'

classes = [
    VIEW3D_PT_ParadataPanel,
    EM_UL_properties_managers,
    EM_UL_sources_managers,
    EM_UL_extractors_managers,
    EM_UL_combiners_managers,
    ]

# Registration
def register():

    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
        
    for cls in classes:
        bpy.utils.unregister_class(cls)



