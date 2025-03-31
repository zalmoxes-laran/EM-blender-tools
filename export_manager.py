import bpy
import string
import json
import os
import shutil

from bpy_extras.io_utils import ExportHelper
from bpy.types import Operator
from bpy.types import Panel, UIList

from bpy.props import EnumProperty, StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty
import bpy.props as prop

from .functions import *

import random

from .s3Dgraphy.utils.utils import convert_shape2type
from .s3Dgraphy.exporter.json_exporter import JSONExporter


#####################################################################
#Export Section

class EM_ExportPanel:
    bl_label = "Export Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}
    
    '''
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Restituisce True se mode_switch è False, quindi il pannello viene mostrato solo in modalità 3D GIS
        return em_tools.mode_switch
    '''
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        export_vars = context.window_manager.export_vars
 
        row = layout.row()
        box = layout.box()
        row = box.row()
        row.label(text="Export:")
        row = box.row()
        op = row.operator("export.uuss_export", text="EM (csv)", emboss=True, icon='LONGDISPLAY')
        row = box.row()
        row.prop(context.window_manager.export_tables_vars, 'table_type', expand=True)
        
        # Heriverse Export Section
        box = layout.box()
        row = box.row()
        row.prop(export_vars, "heriverse_expanded", 
                text="Heriverse Export", 
                icon='TRIA_DOWN' if export_vars.heriverse_expanded else 'TRIA_RIGHT',
                emboss=False)

        if export_vars.heriverse_expanded:
            row = box.row()
            # Use scene properties instead of export_vars
            row.prop(scene, "heriverse_export_path", text="Export Path")
            
            row = box.row()
            row.prop(scene, "heriverse_project_name", text="Project Name")
            
            row = box.row()
            row.prop(export_vars, "heriverse_export_all_graphs", text="Export All Graphs")
            
            row = box.row()
            col = row.column()
            col.prop(export_vars, "heriverse_overwrite_json", text="Export JSON")
            col = row.column()
            col.prop(export_vars, "heriverse_export_dosco", text="Export DosCo")
    

            if export_vars.heriverse_overwrite_json and not export_vars.heriverse_export_rm:
                warning_box = box.box()
                warning_box.alert = True
                row = warning_box.row()
                row.label(text="⚠️ Warning: JSON export without RM export!", icon='ERROR')
                row = warning_box.row()
                row.label(text="Links between RM nodes and models will be missing")
                row = warning_box.row()
                row.label(text="in the JSON if RM Export is not enabled.")


            row = box.row()
            col = row.column()
            col.prop(export_vars, "heriverse_export_proxies", text="Export Proxies")
            col = row.column() 
            col.prop(export_vars, "heriverse_export_rm", text="Export RM")
            row = box.row()
            col = row.column()
            col.prop(export_vars, "heriverse_export_rmdoc", text="Export RM Doc")
            col = row.column()
            col.prop(export_vars, "heriverse_export_rmsf", text="Export RM SF")

            row = box.row()
            col = row.column()
            col.prop(export_vars, "heriverse_create_zip", text="Create ZIP")
            col = row.column()
            col.prop(scene, "heriverse_export_panorama", text="Add Panorama")


            # Advanced options section
            row = box.row()
            row.prop(export_vars, "heriverse_advanced_options",
                    text="Advanced Options",
                    icon='TRIA_DOWN' if export_vars.heriverse_advanced_options else 'TRIA_RIGHT',
                    emboss=False)

            if export_vars.heriverse_advanced_options:
                box_pd = box.box()
                row_pd = box_pd.row()
                row_pd.prop(export_vars, "heriverse_use_draco", text="Use Draco Compression")
                row_pd = box_pd.row()
                if export_vars.heriverse_use_draco:
                    row_pd.prop(export_vars, "heriverse_draco_level", text="Compression Level")
                    row_pd = box_pd.row()
                row_pd.prop(export_vars, "heriverse_separate_textures", text="Separate Textures")
                row_pd = box_pd.row()
                # Add the GPU instancing option here
                row_pd.prop(export_vars, "heriverse_use_gpu_instancing", text="Use GPU Instancing")
                
                # Add texture compression options when separate textures is enabled
                if export_vars.heriverse_separate_textures:
                    box_comp = box.box()
                    row_comp = box_comp.row()
                    row_comp.label(text="Texture Compression:")
                    
                    row_comp = box_comp.row()
                    row_comp.prop(scene, "heriverse_enable_compression", text="Enable Compression")
                    
                    if scene.heriverse_enable_compression:
                        row_comp = box_comp.row()
                        row_comp.prop(scene, "heriverse_texture_max_res", text="Max Size")
                        row_comp.prop(scene, "heriverse_texture_quality", text="Quality")
                        
                        row_comp = box_comp.row()
                        row_comp.label(text="Quality: 100=lossless, 80=good, 60=compressed, 40=heavily compressed")


                if export_vars.heriverse_export_rmdoc:

                    box_pd = box.box()
                    row_pd = box_pd.row()
                    row_pd.label(text="ParaData Export Options:")
                    row_pd = box_pd.row()
                    row_pd.prop(scene, "heriverse_preserve_rmdoc_transform", text="Preserve Transforms for each RMDoc")
                    row_pd = box_pd.row()
                    row_pd.prop(scene, "heriverse_paradata_texture_compression", text="Compress Textures")
                    if scene.heriverse_paradata_texture_compression:
                        row_pd = box.row()

                        row_pd = box_pd.row()
                        row_pd.prop(scene, "heriverse_rmdoc_texture_max_res", text="Max Size")
                        row_pd.prop(scene, "heriverse_rmdoc_texture_quality", text="Quality")


                # Nuova opzione per i tileset
                box_tileset = box.box()
                row_tileset = box_tileset.row()
                row_tileset.label(text="Cesium Tileset Options:")
                row_tileset = box_tileset.row()
                row_tileset.prop(export_vars, "heriverse_skip_extracted_tilesets")

            row = box.row()
            row.operator("export.heriverse", text="Export Heriverse Project", icon='WORLD_DATA')

        # EMviq Export Section
        box = layout.box()
        row = box.row()
        row.prop(export_vars, "emviq_expanded", 
                text="EMviq export", 
                icon='TRIA_DOWN' if export_vars.emviq_expanded else 'TRIA_RIGHT',
                emboss=False)

        if export_vars.emviq_expanded:
            row = box.row()
            row.prop(context.scene, 'EMviq_project_name', toggle=True, text="")
            row.label(text="<-- Project's name")
            row = box.row()#(align=True)
            row.prop(context.scene, 'EMviq_model_author_name', toggle=True, text="")
            row.label(text="<-- Model's author(s)")
            row = box.row()
            row.prop(context.scene, 'EMviq_user_name', toggle=True, text="")
            row.label(text="<-- ATON user's name")
            row = box.row()
            row.prop(context.scene, 'password', toggle=True, text="")
            row.label(text="<-- ATON user's password")
            row = box.row()
            row.prop(context.scene, 'ATON_path', toggle=True, text="")
            row.label(text="<-- path to ATON")

            '''
            row = layout.row()  # (align=True)
            row.prop(context.scene, 'EMviq_folder', toggle=True, text="")
            row.label(text="<-- Collection folder export path")
            row = layout.row()#(align=True)
            row.prop(context.scene, 'EMviq_scene_folder', toggle=True, text="")
            row.label(text="<-- Scene folder export path")
            '''

            row = box.row()
            row.prop(export_vars, 'format_file', expand=True)
            #box = layout.box()
            row = box.row()
            row.prop(context.scene, 'enable_image_compression', toggle = True, text='Use tex compression')
            row.prop(context.scene, 'EM_gltf_export_maxres', toggle = True, text='Max res')
            row.prop(context.scene, 'EM_gltf_export_quality', toggle = True, text='Size')
            row = box.row()
            op = row.operator("export_manager.export", text="Generate full EMviq Project", emboss=True, icon='LONGDISPLAY')
            op.em_export_type = 'EMviq'
            op.em_export_format = export_vars.format_file

            row = box.row()
            row.label(text="Export partial Emviq project's components:")
            row = box.row()
            op = row.operator("export_manager.export", text="Proxies", emboss=True, icon='SHADING_SOLID')
            op.em_export_type = 'Proxies'
            op = row.operator("export_manager.export", text="GraphML", emboss=True, icon='SHADING_SOLID')
            op.em_export_type = 'GraphML'
            op = row.operator("export_manager.export", text="RM", emboss=True, icon='SHADING_TEXTURE')
            op.em_export_type = 'RM'

            row = layout.row()

            row.operator("open.emviq", text="Open on EMviq", emboss=True, icon='SHADING_TEXTURE')
            #row.operator("run.aton", text="Run Aton", emboss=True, icon='SHADING_TEXTURE')
        
        if scene.emviq_error_list_index >= 0 and len(scene.emviq_error_list) > 0:
            row.template_list("ER_UL_List", "EM nodes", scene, "emviq_error_list", scene, "emviq_error_list_index")
            item = scene.emviq_error_list[scene.emviq_error_list_index]
            box = layout.box()
            row = box.row(align=True)

            split = row.split()
            col = split.column()
            row.prop(item, "name", text="")
            split = row.split()
            col = split.column()
            op = col.operator("select.fromlistitem", text='', icon="MESH_CUBE")
            op.list_type = "emviq_error_list"
            #op = col.operator("listitem.toobj", icon="PASTEDOWN", text='')
            #op.list_type = "emviq_error_list"
            #row = layout.row()
            #row.label(text="Description:")
            row = box.row()
            #layout.alignment = 'LEFT'
            row.prop(item, "description", text="", slider=True, emboss=True)

class VIEW3D_PT_ExportPanel(Panel, EM_ExportPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ExportPanel"
    bl_context = "objectmode"

class ER_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.30, align = True)
        layout.label(text = item.texture_type, icon = 'ERROR')
        layout.label(text = item.material, icon='NONE', icon_value=0)

#Export Section
#####################################################################

class EM_runaton(bpy.types.Operator):
    """Run Aton"""
    bl_idname = "run.aton"
    bl_label = "Run Aton"
    bl_description = "Run Aton"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        utente_aton = scene.EMviq_user_name
        path_aton = scene.ATON_path 
        aton_exe = path_aton+"quickstart.sh"
        
        import subprocess
        subprocess.run([aton_exe])

        return {'FINISHED'}

class EM_export(bpy.types.Operator):
    """Export manager"""
    bl_idname = "export_manager.export"
    bl_label = "Export manager"
    bl_description = "Export manager"
    bl_options = {'REGISTER', 'UNDO'}

    em_export_type : StringProperty() # type: ignore
    em_export_format : StringProperty() # type: ignore

    def __init__(self):
        self.stato_collezioni = {}

    def execute(self, context):
        #init general variables
        scene = context.scene
        utente_aton = scene.EMviq_user_name
        progetto_aton = scene.EMviq_project_name

        # deselect everything in the scene
        bpy.ops.object.select_all(action='DESELECT')

        # Salva lo stato delle collezioni prima di procedere con l'export
        self.salva_stato_collezioni()

        # prepare folder paths
        fix_if_relative_folder = bpy.path.abspath(scene.ATON_path)
        base_dir = os.path.dirname(fix_if_relative_folder)
        
        if os.path.exists(os.path.join(base_dir,"data","scenes",utente_aton,progetto_aton)):
            base_dir_scenes = os.path.join(base_dir,"data","scenes",utente_aton,progetto_aton)
        else:
            base_dir_scenes = self.createfolder(os.path.join(base_dir,"data","scenes",utente_aton), progetto_aton)

        if os.path.exists(os.path.join(base_dir,"data","collections",utente_aton+"-collections","models",progetto_aton)):
            base_dir_collections = os.path.join(base_dir,"data","collections",utente_aton+"-collections","models",progetto_aton)
        else:
            base_dir_collections = self.createfolder(os.path.join(base_dir,"data","collections",utente_aton+"-collections","models"), progetto_aton)

        # Export proxies
        if self.em_export_type == 'Proxies' or self.em_export_type == "EMviq":
            bpy.context.view_layer.layer_collection.children['Proxy'].exclude = False

            proxies_folder = self.createfolder(base_dir_scenes, 'proxies')
            self.export_proxies(scene, proxies_folder)

        # Export GraphML
        if self.em_export_type == "GraphML" or self.em_export_type == "EMviq":
    
            em_file_4_emviq = os.path.join(base_dir_scenes, "em.graphml")
            em_file_fixed_path = scene.em_tools.graphml_files[scene.em_tools.active_file_index]['graphml_path']

            #em_file_fixed_path = bpy.path.abspath(scene.EM_file)
            shutil.copyfile(em_file_fixed_path, em_file_4_emviq)

        # Export Representation Models and Scene JSON file
        if self.em_export_type == "RM" or self.em_export_type == "EMviq":
            bpy.context.view_layer.layer_collection.children['RM'].exclude = False
            #bpy.context.view_layer.layer_collection.children['RB'].exclude = False

            #setup JSON variables
            emviq_scene = {}
            scenegraph = {}
            nodes = {}
            edges = {}
            
            emviq_scene['scenegraph'] = scenegraph

            #Prepare node graph for the JSON
            nodes, edges = self.export_rm(scene, base_dir_collections, True, nodes, self.em_export_format, edges, utente_aton, progetto_aton)

            context = {}
            
            #section to activate light and background to make better visual effect
            context['environment'] = {
                "mainpano":{"url":"samples/pano/pano.jpg"},
                "lightprobes":{"auto":True},
                "mainlight":{"direction":[-0.0846315900906896,-0.7511136796681608,-0.6547256938398531]}
            }
            
            scenegraph['context'] = context

            scenegraph['nodes'] = nodes
            scenegraph['edges'] = edges

            # encode dict as JSON 
            data = json.dumps(emviq_scene, indent=4, ensure_ascii=True)

            # generate the JSON file path
            file_name = os.path.join(base_dir_scenes, "scene.json")

            # write JSON file
            with open(file_name, 'w') as outfile:
                outfile.write(data + '\n')

        # Ripristina lo stato delle collezioni dopo l'export
        self.ripristina_stato_collezioni()        

        # Export semantic description in JSON file format 
        # Generate path for the EMviq json export and call the right exporter
        json_file_path = os.path.join(base_dir_scenes, "em.json")
        bpy.ops.export.emjson('INVOKE_DEFAULT', filepath=json_file_path, use_file_dialog=False)          

        return {'FINISHED'}

    def salva_stato_collezioni(self):
        layer_collections = bpy.context.view_layer.layer_collection.children
        self._salva_stato_ricorsivo(layer_collections)

    def _salva_stato_ricorsivo(self, layer_collections):
        for collection in layer_collections:
            self.stato_collezioni[collection.name] = collection.exclude
            if collection.children:
                self._salva_stato_ricorsivo(collection.children)

    def ripristina_stato_collezioni(self):
        layer_collections = bpy.context.view_layer.layer_collection.children
        self._ripristina_stato_ricorsivo(layer_collections)

    def _ripristina_stato_ricorsivo(self, layer_collections):
        for collection in layer_collections:
            if collection.name in self.stato_collezioni:
                collection.exclude = self.stato_collezioni[collection.name]
            if collection.children:
                self._ripristina_stato_ricorsivo(collection.children)

    def export_rm(self, scene, export_folder, EMviq, nodes, format_file, edges, utente_aton, progetto_aton):
        EM_list_clear(bpy.context, "emviq_error_list")
        edges["."] = []
        for ob in bpy.data.objects:
            if len(ob.EM_ep_belong_ob) == 0:
                # in case the object does not have an epoch it belogs to, do nothing (=0)
                pass
            # in case the object belogs to ONE epoch, I manage it accordingly
            if len(ob.EM_ep_belong_ob) == 1:
                ob_tagged = ob.EM_ep_belong_ob[0]
                for epoch in scene.epoch_list:
                    if ob_tagged.epoch == epoch.name:
                        epochname1_var = epoch.name.replace(" ", "_")
                        epochname_var = epochname1_var.replace(".", "")
                        #rm_folder = self.createfolder(export_folder, "rm")
                        rm_folder = export_folder
                        export_sub_folder = self.createfolder(rm_folder, epochname_var)
                        ob.select_set(True)
                        #name = bpy.path.clean_name(ob.name)
                        export_file = os.path.join(export_sub_folder, ob.name)
                        if format_file == "obj":
                            bpy.ops.export_scene.obj(filepath=str(export_file + '.obj'), use_selection=True, axis_forward='Y', axis_up='Z', path_mode='RELATIVE')
                            copy_tex_ob(ob, export_sub_folder)

                        if format_file == "gltf":
                            bpy.ops.export_scene.gltf(export_format='GLTF_SEPARATE', ui_tab='GENERAL', export_copyright=scene.EMviq_model_author_name, export_image_format='AUTO', export_texture_dir="", export_texcoords=True, export_normals=True, export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6, export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12, export_draco_generic_quantization=12, export_tangents=False, export_materials='EXPORT', export_cameras=False, use_selection=True, export_extras=False, export_yup=True, export_apply=True, export_animations=False, export_frame_range=False, export_frame_step=1, export_force_sampling=True, export_nla_strips=False, export_def_bones=False, export_current_frame=False, export_skins=True, export_all_influences=False, export_morph=True, export_morph_normal=False, export_morph_tangent=False, export_lights=False,  will_save_settings=False, filepath=str(export_file), check_existing=False, filter_glob="*.glb;*.gltf")
                        if format_file == "fbx":
                            bpy.ops.export_scene.fbx(filepath = export_file + ".fbx", check_existing=True, filter_glob="*.fbx", use_selection=True, use_active_collection=False, global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', bake_space_transform=False, object_types={'MESH'}, use_mesh_modifiers=True, use_mesh_modifiers_render=True, mesh_smooth_type='OFF', use_mesh_edges=False, use_tspace=False, use_custom_props=False, add_leaf_bones=True, primary_bone_axis='Y', secondary_bone_axis='X', use_armature_deform_only=False, armature_nodetype='NULL', bake_anim=False, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=True, bake_anim_use_all_actions=True, bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=1.0, path_mode='AUTO', embed_textures=False, batch_mode='OFF', use_batch_own_dir=True, use_metadata=True, axis_forward='-Z', axis_up='Y')
                        if EMviq:
                            try:
                                exec(epochname_var+'_node')
                            except NameError:
                                print("well, it WASN'T defined after all!")
                                exec(epochname_var + '_node' + ' = {}')
                                exec(epochname_var + '_urls = []')
                                exec(epochname_var + "_node['urls'] = "+ epochname_var +"_urls")
                                exec("nodes['"+epoch.name+"'] = "+ epochname_var + '_node')

                                #exec(epochname_var + '_edge = []')
                                #exec(epochname_var + '_edge.append(".")')
                                #exec(epochname_var + '_edge.append("'+ epoch.name +'")')

                                #exec('edges["."].append('+epochname_var + '_edge)')
                                edges["."].append(epoch.name)
                            else:
                                print("sure, it was defined.")

                            #exec(epochname_var + '_urls.append("' + epochname_var +'/'+ ob.name + '.' + format_file +'")')
                            #but here we want to set the osgjs file format (the emviq server will convert the obj to osgjs)
                            exec(epochname_var + '_urls.append("'+utente_aton+'-collections'+'/models/'+progetto_aton+'/' + epochname_var +'/'+ ob.name + '.gltf")')
                        ob.select_set(False)
            # in case the object is in different epochs, I set up a "shared" folder instead of a folder for each epoch
            if len(ob.EM_ep_belong_ob) >= 2:
                for ob_tagged in ob.EM_ep_belong_ob:
                    for epoch in scene.epoch_list:
                        if ob_tagged.epoch == epoch.name:
                            epochname1_var = epoch.name.replace(" ", "_")
                            epochname_var = epochname1_var.replace(".", "")
                            rm_folder = export_folder
                            # create a shared folder for all the epochs
                            export_sub_folder = self.createfolder(rm_folder, "shared")
                            
                            ob.select_set(True)
                            export_file = os.path.join(export_sub_folder, ob.name)
                            if format_file == "obj":
                                bpy.ops.export_scene.obj(filepath=str(export_file + '.obj'), use_selection=True, axis_forward='Y', axis_up='Z', path_mode='RELATIVE')
                                copy_tex_ob(ob, export_sub_folder)
                            if format_file == "gltf":
                                bpy.ops.export_scene.gltf(export_format='GLTF_SEPARATE', export_copyright=scene.EMviq_model_author_name, export_image_format='AUTO', export_texture_dir="", export_texcoords=True, export_normals=True, export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6, export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12, export_draco_generic_quantization=12, export_tangents=False, export_materials='EXPORT', export_cameras=False, use_selection=True, export_extras=False, export_yup=True, export_apply=True, export_animations=False, export_frame_range=False, export_frame_step=1, export_force_sampling=True, export_nla_strips=False, export_def_bones=False, export_current_frame=False, export_skins=True, export_all_influences=False, export_morph=True, export_lights=False, will_save_settings=False, filepath=str(export_file), check_existing=False, filter_glob="*.glb;*.gltf")
                            if format_file == "fbx":
                                bpy.ops.export_scene.fbx(filepath = export_file + ".fbx", check_existing=True, filter_glob="*.fbx", use_selection=True, use_active_collection=False, global_scale=1.0, apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', bake_space_transform=False, object_types={'MESH'}, use_mesh_modifiers=True, use_mesh_modifiers_render=True, mesh_smooth_type='OFF', use_mesh_edges=False, use_tspace=False, use_custom_props=False, add_leaf_bones=True, primary_bone_axis='Y', secondary_bone_axis='X', use_armature_deform_only=False, armature_nodetype='NULL', bake_anim=False, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=True, bake_anim_use_all_actions=True, bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=1.0, path_mode='AUTO', embed_textures=False, batch_mode='OFF', use_batch_own_dir=True, use_metadata=True, axis_forward='-Z', axis_up='Y')

                            # if EMviq export is required, also the metadata are exported
                            if EMviq:
                                # I check if the epoch variable is already present, otherwise I create it
                                try:
                                    exec(epochname_var+'_node')
                                except NameError:
                                    #print("well, it WASN'T defined after all!")
                                    exec(epochname_var + '_node' + ' = {}')
                                    exec(epochname_var + '_urls = []')
                                    exec(epochname_var + "_node['urls'] = "+ epochname_var +"_urls")
                                    exec("nodes['"+epoch.name+"'] = "+ epochname_var + '_node')

                                    edges["."].append(epoch.name)

                                else:
                                    pass
                                    #print("sure, it was defined.")
                                
                                exec(epochname_var + '_urls.append("'+utente_aton+'-collections'+'/models/'+progetto_aton+'/' +'/shared/'+ ob.name + '.gltf")')
                                #exec(epochname_var + '_urls.append("rm/shared/' + ob.name + '.osgjs")')
                            ob.select_set(False)
        print(f'E ora di trovare le cartelle per comprimere le immagini: parto dalla folder {export_folder}')
        if scene.enable_image_compression:
            for sub_folder in os.listdir(export_folder):
                print(f'Ho trovato oggetto {sub_folder}')

                if os.path.isdir(os.path.join(export_folder, sub_folder)):
                    print(f'questa subfolder è una directory: {sub_folder}')
                    self.image_compression(os.path.join(export_folder, sub_folder))

        return nodes, edges

    def image_compression(self, dir_path):
        # create new image or just find your image in bpy.data
        scene = bpy.context.scene
        temp_image_format = scene.render.image_settings.file_format
        temp_image_quality = scene.render.image_settings.quality
        scene.render.image_settings.file_format = 'JPEG'
        scene.render.image_settings.quality = scene.EM_gltf_export_quality
        print(f'Cerco nella directory {dir_path}')
        for entry in os.listdir(dir_path):
            if os.path.isfile(os.path.join(dir_path, entry)):
                if entry.lower().endswith('.jpg') or entry.lower().endswith('.png'):
                    print(f'inizio a comprimere {entry}')
                    image_file_path = bpy.path.abspath(os.path.join(dir_path, entry))
                    image_dblock = bpy.data.images.load(image_file_path)
                    print(f"l'immagine importata ha lato {str(image_dblock.size[0])}")
                    if self.check_if_scalable(image_dblock):
                        image_dblock.scale(scene.EM_gltf_export_maxres,scene.EM_gltf_export_maxres)
                        print(f"l'immagine importata ha ora lato {str(image_dblock.size[0])}")
                        print(f"ho compresso {image_dblock.name} con path {image_dblock.filepath}")
                        #image_dblock.filepath = image_file_path
                        image_dblock.update()
                        image_dblock.save_render(image_file_path,scene= bpy.context.scene)

        scene.render.image_settings.file_format = temp_image_format 
        scene.render.image_settings.quality = temp_image_quality 
        return 

    def check_if_scalable(self, image_block):
        is_scalable = False
        if image_block.size[0] > bpy.context.scene.EM_gltf_export_maxres and image_block.size[1] > bpy.context.scene.EM_gltf_export_maxres:
            is_scalable =True
        if bpy.context.scene.EM_gltf_export_quality < 100:
            is_scalable =True
        return is_scalable

    def export_proxies(self, scene, export_folder):
        for proxy in bpy.data.objects:
            for em in scene.em_list:
                if proxy.name == em.name:
                    proxy.select_set(True)
                    name = bpy.path.clean_name(em.name)
                    export_file = os.path.join(export_folder, name)
                    bpy.ops.export_scene.gltf(export_format='GLTF_SEPARATE', export_copyright=scene.EMviq_model_author_name, export_image_format='AUTO', export_texture_dir="", export_texcoords=True, export_normals=True, export_draco_mesh_compression_enable=False, export_draco_mesh_compression_level=6, export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12, export_draco_generic_quantization=12, export_tangents=False, export_materials='NONE', export_cameras=False, use_selection=True, export_extras=False, export_yup=True, export_apply=True, export_animations=False, export_frame_range=False, export_frame_step=1, export_force_sampling=True, export_nla_strips=False, export_def_bones=False, export_current_frame=False, export_skins=True, export_all_influences=False, export_morph=True, export_lights=False,  will_save_settings=False, filepath=str(export_file), check_existing=False, filter_glob="*.glb;*.gltf")
                    proxy.select_set(False)

    def createfolder(self, base_dir, foldername):
        
        if not base_dir:
            raise Exception("Set again the GraphML file path in the first panel above before to export")

        export_folder = os.path.join(base_dir, foldername)
        if not os.path.exists(export_folder):
            os.makedirs(export_folder)
            print('There is no '+ foldername +' folder. Creating one...')
        else:
            print('Found previously created '+foldername+' folder. I will use it')

        return export_folder

class EM_openemviq(bpy.types.Operator):
    """Open EMviq"""
    bl_idname = "open.emviq"
    bl_label = "Open EMviq"
    bl_description = "Open EMviq"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        utente_aton = scene.EMviq_user_name
        progetto_aton = scene.EMviq_project_name 
        
        import webbrowser
        url_emviq = "http://localhost:8080/a/emviq/?s="+utente_aton+"/"+progetto_aton
        webbrowser.open(url_emviq)  # Go to example.com


        return {'FINISHED'}

class JSON_OT_exportEMformat(bpy.types.Operator, ExportHelper):
    """Export project data in EMviq JSON format"""
    bl_idname = "export.emjson"
    bl_label = "Export EMviq JSON"
    bl_options = {"REGISTER", "UNDO"}

    # Proprietà per controllare se mostrare la finestra di dialogo
    use_file_dialog: BoolProperty(
        name="Use File Dialog",
        description="Use the file dialog to choose where to save the JSON",
        default=True
    ) # type: ignore

    filename_ext = ".json"

    def invoke(self, context, event):
        if self.use_file_dialog:
            return ExportHelper.invoke(self, context, event)
        else:
            return self.execute(context)
    
    def execute(self, context):
        # If filepath is provided explicitly through the parameter, use it
        file_path = self.filepath
        
        if not file_path or self.use_file_dialog:
            scene = context.scene
            utente_aton = scene.EMviq_user_name
            progetto_aton = scene.EMviq_project_name 
            
            # prepare folder paths
            fix_if_relative_folder = bpy.path.abspath(scene.ATON_path)
            base_dir = os.path.dirname(fix_if_relative_folder)
            
            if os.path.exists(os.path.join(base_dir,"data","scenes",utente_aton,progetto_aton)):
                base_dir_scenes = os.path.join(base_dir,"data","scenes",utente_aton,progetto_aton)
            else:
                base_dir_scenes = self.createfolder(os.path.join(base_dir,"data","scenes",utente_aton), progetto_aton)

            # generate the JSON file path
            file_path = os.path.join(base_dir_scenes, "em.json")

        # eventually reactivate collections RM and RB
        collectionRM = context.view_layer.layer_collection.children.get('RM')
        if collectionRM:
            collectionRM.exclude = False
        collectionRB = context.view_layer.layer_collection.children.get('RB')
        if collectionRB:
            collectionRB.exclude = False

        try:
            # setup JSON variables
            root = {}
            contextgraph = {}
            semanticgraph = {}
            nodes = {}
            edges = {}
            epochs = {}
            emlist = {}
            site1 = {}
            
            root["context"] = contextgraph
            root["graphs"] = emlist
            contextgraph['epochs'] = epochs
            epochs = self.extract_epochs_from_epoch_list(context.scene, epochs)
            
            semanticgraph['EMlist'] = emlist
            emlist['graph1'] = site1 # questo sarà sostituito dal nome del sito

            # preparo le proprietà del grafo1
            site1['name'] = "Acropoli"
            site1['description'] = "Modello 3D Acropoli di Segni"
            site1_data = {}
            site1['data'] = site1_data
            geo_position = {}
            site1_data['geo_position'] = geo_position
            geo_position['epsg'] = 3004
            geo_position['shift_x'] = 0
            geo_position['shift_y'] = 0
            geo_position['shift_z'] = 0

            # Prepare node graph for the JSON
            nodes, edges = self.extract_nodes_edges_for_emjson(context.scene, nodes, edges)
            site1['nodes'] = nodes
            site1['edges'] = edges
            
            # encode dict as JSON 
            data = json.dumps(root, indent=4, ensure_ascii=True)
            
            # write JSON file
            with open(file_path, 'w') as outfile:
                outfile.write(data + '\n')
                
            print(f"Successfully exported EMviq JSON to {file_path}")
            self.report({'INFO'}, f"Successfully exported EMviq JSON to {file_path}")
            return {'FINISHED'}
            
        except Exception as e:
            print(f"Error during EMviq JSON export: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}
    
    def createfolder(self, base_dir, foldername):
        export_folder = os.path.join(base_dir, foldername)
        if not os.path.exists(export_folder):
            os.makedirs(export_folder)
            print(f'There is no {foldername} folder. Creating one...')
        else:
            print(f'Found previously created {foldername} folder. I will use it')
        return export_folder
    
    def extract_nodes_edges_for_emjson(self, scene, nodes, edges):
        # passo i nodi UUSS:
        index_nodes = 0
        
        for uuss in scene.em_list:
            uuss_node = {}
            uuss_data = {}
            uuss_layout = {}

            uuss_node["type"] = convert_shape2type(uuss.shape, uuss.border_style)[0]
            uuss_node["name"] = uuss.name

            uuss_node["data"] = uuss_data 
            uuss_data["description"] = uuss.description
            uuss_data["epochs"] = [uuss.epoch]
            uuss_data["url"] = uuss.url
            uuss_data["rel_time"] = uuss.y_pos
            uuss_data["time"] = 0  ### DA DEFINIRE MEGLIO CON VARIABILE
            uuss_data["end_rel_time"] = 2024  ### DA DEFINIRE MEGLIO CON VARIABILE
            uuss_data["end_time"] = 0  ### DA DEFINIRE MEGLIO CON VARIABILE

            nodes[uuss.name] = uuss_node

        for property in scene.em_properties_list:
            property_node = {}
            property_data = {}
            property_layout = {}
            property_node["type"] = "property"
            property_node["name"] = property.name

            property_node["data"] = property_data
            property_data["description"] = property.description
            property_data["icon"] = self.set_has_proxy_value(property.icon)
            property_data["url"] = property.url
            property_data["url_type"] = "External link"  ## DA DEFINIRE MEGLIO

            nodes[property.id_node] = property_node

        for combiner in scene.em_combiners_list:
            combiner_node = {}
            combiner_data = {}
            combiner_layout = {}
            combiner_node["type"] = "combiner"
            combiner_node["name"] = combiner.name

            combiner_node["data"] = combiner_data
            combiner_data["description"] = combiner.description
            combiner_data["url"] = combiner.url

            nodes[combiner.id_node] = combiner_node

        for extractor in scene.em_extractors_list:
            extractor_node = {}
            extractor_data = {}
            extractor_layout = {}
            extractor_node["type"] = "extractor"
            extractor_node["name"] = extractor.name

            extractor_node["data"] = extractor_data
            extractor_data["description"] = extractor.description
            extractor_data["icon"] = self.set_has_proxy_value(extractor.icon)
            extractor_data["url"] = extractor.url
            extractor_data["src"] = ""

            nodes[extractor.id_node] = extractor_node

        for source in scene.em_sources_list:
            source_node = {}
            source_data = {}
            source_layout = {}
            source_node["type"] = "document"
            source_node["name"] = source.name

            source_node["data"] = source_data
            source_data["description"] = source.description
            source_data["icon"] = self.set_has_proxy_value(source.icon)
            source_data["url"] = source.url

            nodes[source.id_node] = source_node

        # Suppongo che 'scene.edges_list' sia una lista di edge disponibili
        edges = {}
        for edge in scene.edges_list:
            edge_type = edge.edge_type
            
            # Crea la lista per questo tipo di edge se non esiste già
            if edge_type not in edges:
                edges[edge_type] = []

            # Crea il dizionario per l'edge corrente
            edge_dict = {
                "from": self.original_id_to_new_name(scene, edge.source),
                "to": self.original_id_to_new_name(scene, edge.target)
            }

            # Aggiungi l'edge alla lista corrispondente
            edges[edge_type].append(edge_dict)

        return nodes, edges

    def extract_epochs_from_epoch_list(self, scene, epochs):
        for epoch in scene.epoch_list:
            epoch_node = {}
            epoch_node['min'] = epoch.min_y
            epoch_node['max'] = epoch.max_y
            epoch_node['start'] = -1000
            epoch_node['end'] = 2024
            epoch_node['color'] = epoch.epoch_color
            epochs[epoch.name] = epoch_node
        return epochs

    def edge_type_to_color(self, type):
        if type == "line":
            color = "red"
        elif type == "dashed":
            color = "blue"
        else:
            color = "black"
        return color

    def original_id_to_new_name(self, scene, id_node):
        for UUSS in scene.em_list:
            if UUSS.id_node == id_node:
                return UUSS.name
        for property in scene.em_properties_list:
            if property.id_node == id_node:
                return property.id_node
        for combiner in scene.em_combiners_list:
            if combiner.id_node == id_node:
                return combiner.id_node
        for extractor in scene.em_extractors_list:
            if extractor.id_node == id_node:
                return extractor.id_node
        for source in scene.em_sources_list:
            if source.id_node == id_node:
                return source.id_node
        return id_node

    def set_has_proxy_value(self, string):
        hasproxy = False
        if string == "RESTRICT_INSTANCED_OFF":
            hasproxy = True
        return hasproxy


class OBJECT_OT_ExportUUSS(bpy.types.Operator):
    bl_idname = "export.uuss_export"
    bl_label = "Export UUSS"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.export.uuss_data('INVOKE_DEFAULT')
        return {'FINISHED'}

class ExportuussData(Operator, ExportHelper):
    """Export UUSS data into a csv file"""
    bl_idname = "export.uuss_data"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export UUSS Data"

    # ExportHelper mixin class uses this
    filename_ext = ".csv"

    filter_glob: StringProperty(
            default="*.csv",
            options={'HIDDEN'},
            maxlen=255,  # Max internal buffer length, longer would be clamped.
            ) # type: ignore

    only_UUSS_with_proxies: BoolProperty(
            name="Only elements with proxies",
            description="Only elements with proxies",
            default=False,
            ) # type: ignore

    header_line: BoolProperty(
            name="Header line",
            description="Header line with description of the columns",
            default=True,
            ) # type: ignore

    def execute(self, context):
        return self.write_UUSS_data(context, self.filepath, self.only_UUSS_with_proxies, self.header_line)

    def write_UUSS_data(self, context, filepath, only_UUSS, header):
        print("running write some data...")
        
        f = open(filepath, 'w', encoding='utf-8')

        if  context.window_manager.export_tables_vars.table_type == 'US/USV':
            if header:
                f.write("Name; Description; Epoch; Type \n")
            for US in context.scene.em_list:
                if only_UUSS:
                    if US.icon == "RESTRICT_INSTANCED_ON":
                        f.write("%s\t %s\t %s\t %s\n" % (US.name, US.description, US.epoch, convert_shape2type(US.shape, US.border_style)[1]))
                else:
                    #previous version of the export
                    #f.write("%s\t %s\t %s\t %s\n" % (US.name, US.description, US.epoch, convert_shape2type(US.shape,US.border_style)[1]))
                    # new version of the export
                    f.write("%s\t %s\t %s\t %s\n" % (US.name, US.description, US.epoch, US.shape))
        if  context.window_manager.export_tables_vars.table_type == 'Sources':
            if header:
                f.write("Name; Description \n")
            for source in context.scene.em_sources_list:
                if only_UUSS:
                    if source.icon == "RESTRICT_INSTANCED_ON":
                        f.write("%s\t %s\n" % (source.name, source.description))
                else:
                    f.write("%s\t %s\n" % (source.name, source.description))

        if  context.window_manager.export_tables_vars.table_type == 'Extractors':
            if header:
                f.write("Name\t Description \n")
            for extractor in context.scene.em_extractors_list:
                if only_UUSS:
                    if extractor.icon == "RESTRICT_INSTANCED_ON":
                        f.write("%s\t %s\n" % (extractor.name, extractor.description))
                else:
                    f.write("%s\t %s\n" % (extractor.name, extractor.description))
        f.close()    

        return {'FINISHED'}

# Only needed if you want to add into a dynamic menu
#def menu_func_export(self, context):
#    self.layout.operator(ExportCoordinates.bl_idname, text="Text Export Operator")

classes = [
    ER_UL_List,
    VIEW3D_PT_ExportPanel,
    EM_runaton,
    EM_export,
    EM_openemviq,
    JSON_OT_exportEMformat,
    ExportuussData,
    OBJECT_OT_ExportUUSS
    ]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.password = bpy.props.StringProperty(
        name = "password Aton user",
        default = "",
        description = "Set here your password to access an Aton instance",
        subtype='PASSWORD'
    )

    bpy.types.Scene.enable_image_compression = BoolProperty(
        name="Tex compression", 
        description="Use compression settings for textures. If disabled, original images (size and compression) will be used.",
        default=True
    )
    
    # Add new Heriverse properties to the Scene
    bpy.types.Scene.heriverse_export_path = bpy.props.StringProperty(
        name="Heriverse Export Path",
        description="Path where to export Heriverse project",
        subtype='DIR_PATH',
        default=""
    )
    
    bpy.types.Scene.heriverse_project_name = bpy.props.StringProperty(
        name="Heriverse Project Name",
        description="Name of the Heriverse project",
        default=""
    )
    
    bpy.types.Scene.heriverse_export_panorama = bpy.props.BoolProperty(
        name="Export Default Panorama",
        description="Export the default panorama (defsky.jpg) to the project",
        default=True
    )
    
    # Texture compression options
    bpy.types.Scene.heriverse_enable_compression = bpy.props.BoolProperty(
        name="Enable Texture Compression",
        description="Enable compression for textures in Heriverse export",
        default=True
    )
    
    bpy.types.Scene.heriverse_texture_max_res = bpy.props.IntProperty(
        name="Max Resolution",
        description="Maximum resolution for texture edges",
        default=4096,
        min=512,
        max=8192
    )
    
    bpy.types.Scene.heriverse_texture_quality = bpy.props.IntProperty(
        name="Texture Quality",
        description="JPEG compression quality (100=lossless, 80=good, 60=compressed, 40=heavily compressed)",
        default=80,
        min=10,
        max=100
    )

    # Aggiungi queste proprietà alla classe Blender
    bpy.types.Scene.heriverse_paradata_texture_compression = bpy.props.BoolProperty(
        name="Compress ParaData Textures",
        description="Enable compression for textures in ParaData objects",
        default=True
    )

    bpy.types.Scene.heriverse_paradata_texture_quality = bpy.props.IntProperty(
        name="ParaData Texture Quality",
        description="JPEG compression quality for ParaData textures",
        min=10,
        max=100,
        default=75
    )

    bpy.types.Scene.heriverse_rmdoc_texture_max_res = bpy.props.IntProperty(
        name="ParaData Max Resolution",
        description="Maximum resolution for ParaData textures",
        default=2048,
        min=512,
        max=8192
    )

    bpy.types.Scene.heriverse_rmdoc_texture_quality = bpy.props.IntProperty(
        name="ParaData Quality",
        description="JPEG compression quality for ParaData textures (100=lossless, 80=good, 60=compressed, 40=heavily compressed)",
        default=60,
        min=10,
        max=100
    )

    bpy.types.Scene.heriverse_preserve_rmdoc_transform = bpy.props.BoolProperty(
        name="Preserve ParaData Transforms",
        description="Save and restore original position, rotation and scale of ParaData objects during export",
        default=True
    )

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.password
    del bpy.types.Scene.enable_image_compression
    
    # Remove Heriverse properties
    del bpy.types.Scene.heriverse_rmdoc_texture_quality
    del bpy.types.Scene.heriverse_rmdoc_texture_max_res
    del bpy.types.Scene.heriverse_paradata_texture_compression
    del bpy.types.Scene.heriverse_paradata_texture_quality
    del bpy.types.Scene.heriverse_export_path
    del bpy.types.Scene.heriverse_project_name
    del bpy.types.Scene.heriverse_export_panorama
    del bpy.types.Scene.heriverse_enable_compression
    del bpy.types.Scene.heriverse_texture_max_res
    del bpy.types.Scene.heriverse_texture_quality
    del bpy.types.Scene.heriverse_preserve_rmdoc_transform