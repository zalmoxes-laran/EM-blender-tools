import bpy
import string
import json
import os
import shutil

from bpy_extras.io_utils import ExportHelper
from bpy.types import Operator

from bpy.props import EnumProperty, StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty
import bpy.props as prop

from .functions import *

import random

def check_if_scalable(image_block):
    is_scalable = False
    if image_block.size[0] > bpy.context.scene.EM_gltf_export_maxres and image_block.size[1] > bpy.context.scene.EM_gltf_export_maxres:
        is_scalable =True
    if bpy.context.scene.EM_gltf_export_quality < 100:
        is_scalable =True
    return is_scalable

def image_compression(dir_path):
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
                if check_if_scalable(image_dblock):
                    image_dblock.scale(scene.EM_gltf_export_maxres,scene.EM_gltf_export_maxres)
                    print(f"l'immagine importata ha ora lato {str(image_dblock.size[0])}")
                    print(f"ho compresso {image_dblock.name} con path {image_dblock.filepath}")
                    #image_dblock.filepath = image_file_path
                    image_dblock.update()
                    image_dblock.save_render(image_file_path,scene= bpy.context.scene)

    scene.render.image_settings.file_format = temp_image_format 
    scene.render.image_settings.quality = temp_image_quality 
    return 

def rws(sentence):
    sentence.replace(" ", "_")
    sentence.replace(".", "")
    return sentence

def export_proxies(scene, export_folder):
    for proxy in bpy.data.objects:
        for em in scene.em_list:
            if proxy.name == em.name:
                proxy.select_set(True)
                name = bpy.path.clean_name(em.name)
                export_file = os.path.join(export_folder, name)
                bpy.ops.export_scene.gltf(export_format='GLTF_SEPARATE', export_copyright=scene.EMviq_model_author_name, export_image_format='AUTO', export_texture_dir="", export_texcoords=True, export_normals=True, export_draco_mesh_compression_enable=False, export_draco_mesh_compression_level=6, export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12, export_draco_generic_quantization=12, export_tangents=False, export_materials='NONE', export_colors=True, export_cameras=False, use_selection=True, export_extras=False, export_yup=True, export_apply=True, export_animations=False, export_frame_range=False, export_frame_step=1, export_force_sampling=True, export_nla_strips=False, export_def_bones=False, export_current_frame=False, export_skins=True, export_all_influences=False, export_morph=True, export_lights=False, export_displacement=False, will_save_settings=False, filepath=str(export_file), check_existing=False, filter_glob="*.glb;*.gltf")

                proxy.select_set(False)

def export_rm(scene, export_folder, EMviq, nodes, format_file, edges, utente_aton, progetto_aton):
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
                    #rm_folder = createfolder(export_folder, "rm")
                    rm_folder = export_folder
                    export_sub_folder = createfolder(rm_folder, epochname_var)
                    ob.select_set(True)
                    #name = bpy.path.clean_name(ob.name)
                    export_file = os.path.join(export_sub_folder, ob.name)
                    if format_file == "obj":
                        bpy.ops.export_scene.obj(filepath=str(export_file + '.obj'), use_selection=True, axis_forward='Y', axis_up='Z', path_mode='RELATIVE')
                        copy_tex_ob(ob, export_sub_folder)

                    if format_file == "gltf":
                        bpy.ops.export_scene.gltf(export_format='GLTF_SEPARATE', ui_tab='GENERAL', export_copyright=scene.EMviq_model_author_name, export_image_format='AUTO', export_texture_dir="", export_texcoords=True, export_normals=True, export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6, export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12, export_draco_generic_quantization=12, export_tangents=False, export_materials='EXPORT', export_colors=True, export_cameras=False, use_selection=True, export_extras=False, export_yup=True, export_apply=True, export_animations=False, export_frame_range=False, export_frame_step=1, export_force_sampling=True, export_nla_strips=False, export_def_bones=False, export_current_frame=False, export_skins=True, export_all_influences=False, export_morph=True, export_morph_normal=False, export_morph_tangent=False, export_lights=False, export_displacement=False, will_save_settings=False, filepath=str(export_file), check_existing=False, filter_glob="*.glb;*.gltf")
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
                        exec(epochname_var + '_urls.append("'+utente_aton+'/'+progetto_aton+'/' + epochname_var +'/'+ ob.name + '.gltf")')
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
                        export_sub_folder = createfolder(rm_folder, "shared")
                        
                        ob.select_set(True)
                        export_file = os.path.join(export_sub_folder, ob.name)
                        if format_file == "obj":
                            bpy.ops.export_scene.obj(filepath=str(export_file + '.obj'), use_selection=True, axis_forward='Y', axis_up='Z', path_mode='RELATIVE')
                            copy_tex_ob(ob, export_sub_folder)
                        if format_file == "gltf":
                            bpy.ops.export_scene.gltf(export_format='GLTF_SEPARATE', export_copyright=scene.EMviq_model_author_name, export_image_format='AUTO', export_texture_dir="", export_texcoords=True, export_normals=True, export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6, export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12, export_draco_generic_quantization=12, export_tangents=False, export_materials='EXPORT', export_colors=True, export_cameras=False, use_selection=True, export_extras=False, export_yup=True, export_apply=True, export_animations=False, export_frame_range=False, export_frame_step=1, export_force_sampling=True, export_nla_strips=False, export_def_bones=False, export_current_frame=False, export_skins=True, export_all_influences=False, export_morph=True, export_lights=False, export_displacement=False, will_save_settings=False, filepath=str(export_file), check_existing=False, filter_glob="*.glb;*.gltf")
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
                            
                            exec(epochname_var + '_urls.append("'+utente_aton+'/'+progetto_aton+'/shared/'+ ob.name + '.gltf")')
                            #exec(epochname_var + '_urls.append("rm/shared/' + ob.name + '.osgjs")')
                        ob.select_set(False)
    print(f'E ora di trovare le cartelle per compremere le immagini: parto dalla folder {export_folder}')
    if scene.enable_image_compression:
        for sub_folder in os.listdir(export_folder):
            print(f'Ho trovato oggetto {sub_folder}')

            if os.path.isdir(os.path.join(export_folder, sub_folder)):
                print(f'questa subfolder è una directory: {sub_folder}')
                image_compression(os.path.join(export_folder, sub_folder))

    return nodes, edges

class EM_export(bpy.types.Operator):
    """Export manager"""
    bl_idname = "export_manager.export"
    bl_label = "Export manager"
    bl_description = "Export manager"
    bl_options = {'REGISTER', 'UNDO'}

    em_export_type : StringProperty()
    em_export_format : StringProperty()

    def execute(self, context):
        scene = context.scene
        utente_aton = scene.EMviq_user_name
        progetto_aton = scene.EMviq_project_name 
        
        bpy.ops.object.select_all(action='DESELECT')

        # prepare folder paths
        fix_if_relative_folder = bpy.path.abspath(scene.ATON_path)
        base_dir = os.path.dirname(fix_if_relative_folder)
        
        if os.path.exists(os.path.join(base_dir,"data","scenes",utente_aton,progetto_aton)):
            base_dir_scenes = os.path.join(base_dir,"data","scenes",utente_aton,progetto_aton)
        else:
            base_dir_scenes = createfolder(os.path.join(base_dir,"data","scenes",utente_aton), progetto_aton)

        if os.path.exists(os.path.join(base_dir,"data","collections",utente_aton,progetto_aton)):
            base_dir_collections = os.path.join(base_dir,"data","collections",utente_aton,progetto_aton)
        else:
            base_dir_collections = createfolder(os.path.join(base_dir,"data","collections",utente_aton), progetto_aton)

        # Export proxies
        if self.em_export_type == 'Proxies' or self.em_export_type == "EMviq":
            bpy.context.scene.view_layers['ViewLayer'].layer_collection.children['Proxy'].exclude = False
            proxies_folder = createfolder(base_dir_scenes, 'proxies')
            export_proxies(scene, proxies_folder)

        # Export GraphML
        if self.em_export_type == "GraphML" or self.em_export_type == "EMviq":
    
            em_file_4_emviq = os.path.join(base_dir_scenes, "em.graphml")
            em_file_fixed_path = bpy.path.abspath(scene.EM_file)
            shutil.copyfile(em_file_fixed_path, em_file_4_emviq)

        # Export Representation Models and Scene JSON file
        if self.em_export_type == "RM" or self.em_export_type == "EMviq":
            bpy.context.scene.view_layers['ViewLayer'].layer_collection.children['SB'].exclude = False
            bpy.context.scene.view_layers['ViewLayer'].layer_collection.children['RB'].exclude = False

            #setup JSON variables
            emviq_scene = {}
            scenegraph = {}
            nodes = {}
            edges = {}
            
            emviq_scene['scenegraph'] = scenegraph
            '''
            section to activate light and background to make better visual effect
            "environment":{
                "mainpano":{"url":"samples/pano/defsky-grass.jpg"},
                "lightprobes":{"auto":true},
                "mainlight":{"direction":[-0.0846315900906896,-0.7511136796681608,-0.6547256938398531]}
            },
            '''
            #Prepare node graph for the JSON
            nodes, edges = export_rm(scene, base_dir_collections, True, nodes, self.em_export_format, edges, utente_aton, progetto_aton)
            scenegraph['nodes'] = nodes
            scenegraph['edges'] = edges

            # encode dict as JSON 
            data = json.dumps(emviq_scene, indent=4, ensure_ascii=True)

            # generate the JSON file path
            file_name = os.path.join(base_dir_scenes, "scene.json")

            # write JSON file
            with open(file_name, 'w') as outfile:
                outfile.write(data + '\n')

        return {'FINISHED'}

class OBJECT_OT_ExportUUSS(bpy.types.Operator):
    bl_idname = "export.uuss_export"
    bl_label = "Export UUSS"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):

        bpy.ops.export.uuss_data('INVOKE_DEFAULT')
            
        return {'FINISHED'}



def convert_shape2type(shape):
    node_type = "None"
    if shape == "rectangle":
        node_type = "US"
    elif shape == "parallelogram":
        node_type = "USVs"
    elif shape == "ellipse":
        node_type = "Series of USVs"
    elif shape == "ellipse_white":
        node_type = "Series of US"
    elif shape == "hexagon":
        node_type = "USVn"
    elif shape == "octagon_white":
        node_type = "Special Find"
    elif shape == "octagon":
        node_type = "Virtual Special Find"
    elif shape == "roundrectangle":
        node_type = "USD"
    return node_type

def write_UUSS_data(context, filepath, only_UUSS, header):
    print("running write some data...")
    
    f = open(filepath, 'w', encoding='utf-8')

    if  context.window_manager.export_tables_vars.table_type == 'US/USV':
        if header:
            f.write("Name; Description; Epoch; Type \n")
        for US in context.scene.em_list:
            if only_UUSS:
                if US.icon == "RESTRICT_INSTANCED_ON":
                    f.write("%s\t %s\t %s\t %s\n" % (US.name, US.description, US.epoch, convert_shape2type(US.shape)))
            else:
                f.write("%s\t %s\t %s\t %s\n" % (US.name, US.description, US.epoch, convert_shape2type(US.shape)))
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
            )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.

    # name: BoolProperty(
    #         name="Names of UUSS",
    #         description="This tool includes name",
    #         default=True,
    #         )

    # description: BoolProperty(
    #         name="Description",
    #         description="This tool includes description",
    #         default=True,
    #         )

    # epoch: BoolProperty(
    #         name="Epoch",
    #         description="This tool includes epoch",
    #         default=True,
    #         )

    # type_node: BoolProperty(
    #         name="Node type",
    #         description="This includes node type",
    #         default=True,
    #         )

    only_UUSS_with_proxies: BoolProperty(
            name="Only elements with proxies",
            description="Only elements with proxies",
            default=False,
            )

    header_line: BoolProperty(
            name="Header line",
            description="Header line with description of the columns",
            default=True,
            )

    def execute(self, context):
        return write_UUSS_data(context, self.filepath, self.only_UUSS_with_proxies, self.header_line)
        #return write_UUSS_data(context, self.filepath, self.name, self.description, self.epoch, self.type_node, self.only_UUSS_with_proxies, self.header_line)

# Only needed if you want to add into a dynamic menu
#def menu_func_export(self, context):
#    self.layout.operator(ExportCoordinates.bl_idname, text="Text Export Operator")

def createfolder(base_dir, foldername):
    
    if not base_dir:
        raise Exception("Set again the GraphML file path in the first panel above before to export")

    export_folder = os.path.join(base_dir, foldername)
    if not os.path.exists(export_folder):
        os.mkdir(export_folder)
        print('There is no '+ foldername +' folder. Creating one...')
    else:
        print('Found previously created '+foldername+' folder. I will use it')

    return export_folder
