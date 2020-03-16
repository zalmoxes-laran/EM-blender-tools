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
                bpy.ops.export_scene.obj(filepath=str(export_file + '.obj'), use_selection=True, axis_forward='Y', axis_up='Z', path_mode='RELATIVE')
                proxy.select_set(False)

def export_rm(scene, export_folder, EMviq, nodes, format_file, edges):
    for ob in bpy.data.objects:
        if len(ob.EM_ep_belong_ob) == 0:
            pass
        if len(ob.EM_ep_belong_ob) == 1:
            ob_tagged = ob.EM_ep_belong_ob[0]
            for epoch in scene.epoch_list:
                if ob_tagged.epoch == epoch.name:

                    epochname1_var = epoch.name.replace(" ", "_")
                    epochname_var = epochname1_var.replace(".", "")
                    rm_folder = createfolder(export_folder, "rm")
                    export_sub_folder = createfolder(rm_folder, epochname_var)
                    ob.select_set(True)
                    #name = bpy.path.clean_name(ob.name)
                    export_file = os.path.join(export_sub_folder, ob.name)
                    if format_file == "obj":
                        bpy.ops.export_scene.obj(filepath=str(export_file + '.obj'), use_selection=True, axis_forward='Y', axis_up='Z', path_mode='RELATIVE')
                    if format_file == "gltf":
                        bpy.ops.export_scene.gltf(export_format='GLTF_SEPARATE', export_copyright="Extended Matrix", export_image_format='NAME', export_texture_dir="", export_texcoords=True, export_normals=True, export_draco_mesh_compression_enable=False, export_draco_mesh_compression_level=6, export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12, export_draco_generic_quantization=12, export_tangents=False, export_materials=True, export_colors=True, export_cameras=False, export_selected=True, export_extras=False, export_yup=True, export_apply=False, export_animations=False, export_frame_range=False, export_frame_step=1, export_force_sampling=True, export_nla_strips=False, export_def_bones=False, export_current_frame=False, export_skins=True, export_all_influences=False, export_morph=True, export_lights=False, export_displacement=False, will_save_settings=False, filepath=str(export_file), check_existing=False, filter_glob="*.glb;*.gltf")                    
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

                            exec(epochname_var + '_edge = []')
                            exec(epochname_var + '_edge.append(".")')
                            exec(epochname_var + '_edge.append("'+ epoch.name +'")')

                            exec('edges.append('+epochname_var + '_edge)')

                        else:
                            print("sure, it was defined.")

                        exec(epochname_var + '_urls.append("' + epochname_var +'/'+ ob.name + '.' + format_file +'")')
                    
                    ob.select_set(False)

        if len(ob.EM_ep_belong_ob) >= 2:
            for ob_tagged in ob.EM_ep_belong_ob:
                for epoch in scene.epoch_list:
                    if ob_tagged.epoch == epoch.name:
                        epochname1_var = epoch.name.replace(" ", "_")
                        epochname_var = epochname1_var.replace(".", "")
                        rm_folder = createfolder(export_folder, "rm")
                        export_sub_folder = createfolder(rm_folder, epochname_var)
                        ob.select_set(True)
                        #name = bpy.path.clean_name(ob.name)
                        export_file = os.path.join(export_sub_folder, ob.name)
                        if format_file == "obj":
                            bpy.ops.export_scene.obj(filepath=str(export_file + '.obj'), use_selection=True, axis_forward='Y', axis_up='Z', path_mode='RELATIVE')
                        if format_file == "gltf":
                            bpy.ops.export_scene.gltf(export_format='GLTF_SEPARATE', export_copyright="Extended Matrix", export_image_format='NAME', export_texture_dir="", export_texcoords=True, export_normals=True, export_draco_mesh_compression_enable=False, export_draco_mesh_compression_level=6, export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12, export_draco_generic_quantization=12, export_tangents=False, export_materials=True, export_colors=True, export_cameras=False, export_selected=True, export_extras=False, export_yup=True, export_apply=False, export_animations=False, export_frame_range=False, export_frame_step=1, export_force_sampling=True, export_nla_strips=False, export_def_bones=False, export_current_frame=False, export_skins=True, export_all_influences=False, export_morph=True, export_lights=False, export_displacement=False, will_save_settings=False, filepath=str(export_file), check_existing=False, filter_glob="*.glb;*.gltf")                    
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

                                exec(epochname_var + '_edge = []')
                                exec(epochname_var + '_edge.append(".")')
                                exec(epochname_var + '_edge.append("'+ epoch.name +'")')

                                exec('edges.append('+epochname_var + '_edge)')

                            else:
                                print("sure, it was defined.")
                            
                            exec(epochname_var + "_urls.append('shared/"+ ob.name + '.' + format_file +"')")
                        
                        ob.select_set(False)
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

        #selection = bpy.context.selected_objects
        bpy.ops.object.select_all(action='DESELECT')
        print(scene.EM_file)
        base_dir = os.path.dirname(scene.EM_file)
        print("la base_dir is:"+base_dir)
        
        if self.em_export_type == 'Proxies':
            proxies_folder = createfolder(base_dir, 'Proxies')
            export_proxies(scene, proxies_folder)

        if self.em_export_type == 'RM':
            #RM_folder = createfolder(base_dir, 'RM')
            nodes = None
            edges = None
            export_rm(scene, base_dir, False, nodes,
                      self.em_export_format, edges)

        if self.em_export_type == "EMviq":
            
            #setup json variables
            emviq_scene = {}
            scenegraph = {}
            nodes = {}
            edges = []
            
            emviq_scene['scenegraph'] = scenegraph
            export_folder = createfolder(base_dir, 'EMviq')
            proxies_folder = createfolder(export_folder, 'proxies')
            nodes, edges = export_rm(scene, export_folder, True, nodes, self.em_export_format, edges)
            export_proxies(scene, proxies_folder)

            scenegraph['nodes'] = nodes

            scenegraph['edges'] = edges

            # encode dict as JSON 
            data = json.dumps(emviq_scene, indent=4, ensure_ascii=True)

            #'/users/emanueldemetrescu/Desktop/'
            file_name = os.path.join(export_folder, "scene.json")

            # write JSON file
            with open(file_name, 'w') as outfile:
                outfile.write(data + '\n')

            em_file_4_emviq = os.path.join(export_folder, "em.graphml")

            shutil.copyfile(scene.EM_file, em_file_4_emviq)

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
    elif shape == "octagon":
        node_type = "Special Find"
    return node_type

def write_UUSS_data(context, filepath, only_UUSS, header):
    print("running write some data...")
    
    f = open(filepath, 'w', encoding='utf-8')

    if header:
        f.write("Name; Description; Epoch; Type \n")

    for US in context.scene.em_list:
        if only_UUSS:
            if US.icon == "RESTRICT_INSTANCED_ON":
                f.write("%s; %s; %s; %s\n" % (US.name, US.description, US.epoch, convert_shape2type(US.shape)))
        else:
            f.write("%s; %s; %s; %s\n" % (US.name, US.description, US.epoch, convert_shape2type(US.shape)))
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
            name="Only UUSS with proxies",
            description="Only UUSS with proxies",
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
