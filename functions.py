import xml.etree.ElementTree as ET
import bpy
import os
import bpy.props as prop
from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty,
                       IntProperty
                       )

def settingsSwitch(self, context):
#    wm = bpy.context.window_manager
    layout = self.layout
    scene = context.scene
    sg_settings = scene.sg_settings    
    if bpy.scene.sg_settings.em_proxy_sync:
        scene.sg_settings.em_proxy_sync2 = False

    if bpy.scene.sg_settings.em_proxy_sync2:
        scene.sg_settings.em_proxy_sync = False

def check_if_current_obj_has_brother_inlist(obj_name):
    scene = bpy.context.scene
    for us_usv in scene.em_list:
        if us_usv.name == obj_name:
            is_brother = True
            return is_brother
    is_brother = False
    return is_brother

def EM_extract_node_name(node_element):
    is_d4 = False
    is_d5 = False
    node_y_pos = None
    nodeshape = None
    nodeurl = None
    nodedescription = None
    nodename = None
    for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
        attrib = subnode.attrib
        print(attrib)
        if attrib == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
            is_d4 = True
            nodeurl = subnode.text
        if attrib == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
            is_d5 = True
            nodedescription = subnode.text
            #print(nodedescription)
        if attrib == {'key': 'd6'}:
            for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                nodename = USname.text
#                print(nodename)
            for USshape in subnode.findall('.//{http://www.yworks.com/xml/graphml}Shape'):
                nodeshape = USshape.attrib['type']
#                print(nodeshape)
            for geometry in subnode.findall('./{http://www.yworks.com/xml/graphml}ShapeNode/{http://www.yworks.com/xml/graphml}Geometry'):
                node_y_pos = geometry.attrib['y']
    if not is_d4:
        nodeurl = '--None--'
    if not is_d5:
        nodedescription = '--None--'
    return nodename, nodedescription, nodeurl, nodeshape, node_y_pos 

def EM_check_node_type(node_element):
    id_node = str(node_element.attrib)
#    print(id_node)
    if "yfiles.foldertype" in id_node:
        tablenode = node_element.find('.//{http://www.yworks.com/xml/graphml}TableNode')
#        print(tablenode.attrib)
        if tablenode is not None:
#            print(' un nodo swimlane: ' + id_node)
            node_type = 'node_swimlane'
        else:
#            print(' un nodo group: ' + id_node)
            node_type = 'node_group'
    else:
#        print(' un semplice nodo: ' + id_node)
        node_type = 'node_simple'
    return node_type

def EM_check_node_us(node_element):
    US_nodes_list = ['rectangle', 'parallelogram', 'ellipse', 'hexagon', 'octagon']
    my_nodename, my_node_description, my_node_url, my_node_shape, my_node_y_pos = EM_extract_node_name(node_element)
#    print(my_node_shape)
    if my_node_shape in US_nodes_list:
        id_node_us = True
    else:
        id_node_us = False
    return id_node_us

def EM_list_clear(context):
    scene = context.scene
    scene.em_list.update()
    list_lenght = len(scene.em_list)
    for x in range(list_lenght):
        scene.em_list.remove(0)
    return

def epoch_list_clear(context):
    scene = context.scene
    scene.epoch_list.update()
    list_lenght = len(scene.epoch_list)
    for x in range(list_lenght):
        scene.epoch_list.remove(0)
    return

#Check the presence-absence of US against the GraphML
def EM_check_GraphML_Blender(node_name):
    data = bpy.data
    icon_check = 'CANCEL'
    for ob in data.objects:
        if ob.name == node_name:
            icon_check = 'FILE_TICK'
    return icon_check

def select_3D_obj(name):
    scene = bpy.context.scene
    bpy.ops.object.select_all(action="DESELECT")
    object_to_select = bpy.data.objects[name]
    object_to_select.select = True
    scene.objects.active = object_to_select
    
def update_icons(context):
    scene = context.scene
    for US in scene.em_list:
        US.icon = EM_check_GraphML_Blender(US.name)
    return

def select_list_element_from_obj_proxy(obj):
    scene = bpy.context.scene
    index_list = 0
    for i in scene.em_list:
        if obj.name == i.name:
            scene.em_list_index = index_list
        index_list += 1
        
        
def extract_epochs(node_element):
    geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
    y_start = float(geometry.attrib['y'])
    context = bpy.context
    scene = context.scene    
    epoch_list_clear(context)  
    epoch_list_index_ema = 0
    y_min = y_start
    y_max = y_start

    for row in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}Table/{http://www.yworks.com/xml/graphml}Rows/{http://www.yworks.com/xml/graphml}Row'):
        id_row = row.attrib['id']
        h_row = float(row.attrib['height'])

        scene.epoch_list.add()
        scene.epoch_list[epoch_list_index_ema].id = str(id_row)
        scene.epoch_list[epoch_list_index_ema].height = h_row
        y_min = y_max
        y_max += h_row
        scene.epoch_list[epoch_list_index_ema].min_y = y_min
        scene.epoch_list[epoch_list_index_ema].max_y = y_max        
        print(str(id_row))
        epoch_list_index_ema += 1        

    for nodelabel in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
        RowNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
        if RowNodeLabelModelParameter is not None:
            label_node = nodelabel.text
            id_node = str(RowNodeLabelModelParameter.attrib['id']) 
        else:
            id_node = "null"
            
        for i in range(len(scene.epoch_list)):
            id_key = scene.epoch_list[i].id
            if id_node == id_key:
                scene.epoch_list[i].name = str(label_node)

def add_sceneobj_to_epochs():
    scene = bpy.context.scene
    #deselect all objects
    selection_names = bpy.context.selected_objects
    bpy.ops.object.select_all(action='DESELECT')
    #looking through all objects
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            for USS in scene.em_list:
                if obj.name == USS.name:
                    #print("ho trovato un oggetto in scena chiamato "+ str(obj.name)+ " ed un nodo US chiamato: " + str(USS.name))
                    idx = 0
                    for i in scene.epoch_managers:
                        if i.name == USS.epoch:
                            #print("found "+str(USS.epoch)+ " corrispondende all'indice"+str(idx))
                            obj.select = True
                            bpy.ops.epoch_manager.add_to_group(group_idx=idx)
                            obj.select = False
                        idx +=1
                        
                        
                        
#------------------- qui funzioni per materiali------------------------------------------

def EM_mat_get_RGB_values(matname):
    if matname == "US":
        R = 0.328
        G = 0.033
        B = 0.033
    elif matname == "USVn":
         R = 0.031
         G = 0.191
         B = 0.026
    elif matname == "USVs":
        R = 0.018
        G = 0.275
        B = 0.799
    elif matname == "VSF" or matname == "SF":
        R = 0.799
        G = 0.753
        B = 0.347
    return R, G, B

def em_setup_mat_cycles(matname):
#    image = mat.texture_slots[0].texture.image
    R, G, B = EM_mat_get_RGB_values(matname)
    mat = bpy.data.materials[matname]
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    links = mat.node_tree.links
    nodes = mat.node_tree.nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (0, 0)
    mainNode = nodes.new('ShaderNodeBsdfDiffuse')
    mainNode.inputs['Color'].default_value = (R,G,B,0.5)
    mainNode.location = (-400, -50)
    mainNode.name = "diffuse"
#    colornode = nodes.new('ShaderNodeTexImage')
#    colornode.location = (-1100, -50)
        
#    links.new(colornode.outputs[0], mainNode.inputs[0])
    links.new(mainNode.outputs[0], output.inputs[0])

def em_setup_mat_bi(matname):
    R, G, B = EM_mat_get_RGB_values(matname)
    mat = bpy.data.materials[matname]
    mat.use_nodes = False
    mat.diffuse_color = (R,G,B)
    mat.use_transparency = True
    mat.alpha = 0.5
    
def check_material_presence(matname):
    mat_presence = False
    for mat in bpy.data.materials:
        if mat.name == matname:
            mat_presence = True
            return mat_presence
    return mat_presence
    
def consolidate_EM_material_presence(overwrite_mats):
    EM_mat_list = ['US', 'USVs', 'USVn', 'VSF', 'SF']
    for EM_mat_name in EM_mat_list:
        if not check_material_presence(EM_mat_name):
            EM_mat = bpy.data.materials.new(name=EM_mat_name)
            overwrite_mats = True
        if overwrite_mats == True:
            scene = bpy.context.scene
            if scene.render.engine == 'CYCLES':
                em_setup_mat_cycles(EM_mat_name)
            else:
                em_setup_mat_bi(EM_mat_name)
            
        
def set_EM_materials_using_EM_list(context):
    em_list_lenght = len(context.scene.em_list)
    print(str(em_list_lenght))
    counter = 0
    while counter < em_list_lenght:
        current_ob_em_list = context.scene.em_list[counter]
        #if ob.name == context.scene.em_list[counter].name:
        overwrite_mats = True
        consolidate_EM_material_presence(overwrite_mats)
        if current_ob_em_list.icon == 'FILE_TICK':
            current_ob_scene = context.scene.objects[current_ob_em_list.name]
            current_ob_scene.name
            print(current_ob_em_list.name + ' has symbol: ' +current_ob_em_list.shape)
            if current_ob_em_list.shape ==  'rectangle':
                ob_material_name = 'US'
            if current_ob_em_list.shape ==  'ellipse':
                ob_material_name = 'USVn'
            if current_ob_em_list.shape ==  'parallelogram':
                ob_material_name = 'USVs'
            if current_ob_em_list.shape ==  'hexagon':
                ob_material_name = 'USVn'
            if current_ob_em_list.shape ==  'octagon':
                ob_material_name = 'SF'
            #if current_ob_em_list.shape =  'rectangle':
            mat = bpy.data.materials[ob_material_name]
            current_ob_scene.data.materials.clear()
            current_ob_scene.data.materials.append(mat)
        counter += 1