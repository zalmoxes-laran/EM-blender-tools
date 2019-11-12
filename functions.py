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

def menu_func(self, context):
    self.layout.separator()

### #### #### #### #### #### #### #### ####
##### functions to switch menus in UI  ####
### #### #### #### #### #### #### #### ####

def sync_Switch_em(self, context):
#    wm = bpy.context.window_manager
    #layout = self.layout
    scene = context.scene
    em_settings = scene.em_settings
    if scene.em_settings.em_proxy_sync is True:
        scene.em_settings.em_proxy_sync2 = False
        scene.em_settings.em_proxy_sync2_zoom = False
    return

def sync_update_epoch_soloing(self, context):
    scene = context.scene
    soling = False
    for epoch in scene.epoch_list:
        if epoch.epoch_soloing is True:
            soloing_epoch = epoch
            soloing = True
    if soloing is True:
        for epoch in scene.epoch_list:
            if epoch is not soloing_epoch:
                pass
    return

def sync_Switch_proxy(self, context):
#    wm = bpy.context.window_manager
    #layout = self.layout
    scene = context.scene
    em_settings = scene.em_settings
    if scene.em_settings.em_proxy_sync2 is True:
        scene.em_settings.em_proxy_sync = False
    return

## #### #### #### #### #### #### #### #### #### #### ####
##### Functions to check properties of scene objects ####
## #### #### #### #### #### #### #### #### #### #### ####

def check_if_current_obj_has_brother_inlist(obj_name, list_element):
    scene = bpy.context.scene
    for element_list in list_element:
        if element_list.name == obj_name:
            is_brother = True
            return is_brother
    is_brother = False
    return is_brother

def select_3D_obj(name):
    scene = bpy.context.scene
    bpy.ops.object.select_all(action="DESELECT")
    object_to_select = bpy.data.objects[name]
    object_to_select.select_set(True)
    bpy.context.view_layer.objects.active = object_to_select

def select_list_element_from_obj_proxy(obj):
    scene = bpy.context.scene
    index_list = 0
    for i in scene.em_list:
        if obj.name == i.name:
            scene.em_list_index = index_list
        index_list += 1

def select_sourcelist_element_from_obj_proxy(obj):
    scene = bpy.context.scene
    index_list = 0
    for i in scene.em_sources_list:
        if obj.name == i.name:
            scene.em_sources_list_index = index_list
        index_list += 1

## diverrà deprecata !
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
                    for i in scene.epoch_list:
                        if i.name == USS.epoch:
                            #print("found "+str(USS.epoch)+ " corrispondende all'indice"+str(idx))
                            obj.select_set(True)
                            bpy.ops.epoch_manager.add_to_group(group_em_idx=idx)
                            obj.select_set(False)
                        idx +=1
                        
                        
### #### #### #### #### #### #### #### #### #### ####
#### Functions to extract data from GraphML file ####
### #### #### #### #### #### #### #### #### #### ####

def get_edge_target(tree, node_element):
    alledges = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}edge')
    id_node = getnode_id(node_element)
    EM_us_target = "" 
    node_y_pos = 0.0
    
    for edge in alledges:
        id_node_edge_source = getnode_edge_source(edge) 
        if id_node_edge_source == id_node:
            my_continuity_node_description, node_y_pos = EM_extract_continuity(node_element)
            id_node_edge_target = getnode_edge_target(edge)
            EM_us_target = find_node_us_by_id(id_node_edge_target)
            #print("edge with id: "+ getnode_id(edge)+" with target US_node "+ id_node_edge_target+" which is the US "+ EM_us_target)
    #print("edge with id: "+ getnode_id(edge)+" with target US_node "+ id_node_edge_target+" which is the US "+ EM_us_target)
    return EM_us_target, node_y_pos

def getnode_id(node_element):
    id_node = str(node_element.attrib['id'])
    return id_node

def getnode_edge_target(node_element):
    id_node_edge_target = str(node_element.attrib['target'])
    #print(id_node_edge_target)
    return id_node_edge_target

def getnode_edge_source(node_element):
    id_node_edge_source = str(node_element.attrib['source'])
    #print(id_node_edge_source)
    return id_node_edge_source

def find_node_us_by_id(id_node):
    us_node = ""
    for us in bpy.context.scene.em_list:
        if id_node == us.id_node:
            us_node = us.name
    return us_node

def EM_extract_document_node(node_element):

    is_d4 = False
    is_d5 = False
    node_id = node_element.attrib['id']
    if len(node_id) > 2:
        subnode_is_document = False
        nodeurl = " "
        nodename = " "
        node_description = " "
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib1 = subnode.attrib
            #print(subnode.tag)
            if attrib1 == {'key': 'd6'}:
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = USname.text
                for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}Property'):
                    attrib2 = nodetype.attrib
                    if attrib2 == {'class': 'com.yworks.yfiles.bpmn.view.DataObjectTypeEnum', 'name': 'com.yworks.bpmn.dataObjectType', 'value': 'DATA_OBJECT_TYPE_PLAIN'}:
                        subnode_is_document = True

        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib1 = subnode.attrib                        
            if subnode_is_document is True:

                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:

                    is_d4 = True
                    nodeurl = subnode.text
                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                    is_d5 = True
                    node_description = subnode.text

        if not is_d4:
            nodeurl = '--None--'
        if not is_d5:
            nodedescription = '--None--'
        return nodename, node_id, node_description, nodeurl, subnode_is_document

def EM_extract_node_name(node_element):
    is_d4 = False
    is_d5 = False
    node_y_pos = None
    nodeshape = None
    nodeurl = None
    nodedescription = None
    nodename = None
    fillcolor = None
    for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
        attrib = subnode.attrib
        #print(attrib)
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
            for fill_color in subnode.findall('.//{http://www.yworks.com/xml/graphml}Fill'):
                fillcolor = fill_color.attrib['color']
#                print(nodename)
            for USshape in subnode.findall('.//{http://www.yworks.com/xml/graphml}Shape'):
                nodeshape = USshape.attrib['type']
#                print(nodeshape)
            for geometry in subnode.findall('./{http://www.yworks.com/xml/graphml}ShapeNode/{http://www.yworks.com/xml/graphml}Geometry'):
            #for geometry in subnode.findall('./{http://www.yworks.com/xml/graphml}Geometry'):
                node_y_pos = geometry.attrib['y']
    if not is_d4:
        nodeurl = '--None--'
    if not is_d5:
        nodedescription = '--None--'
    return nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor 

def EM_extract_continuity(node_element):
    is_d5 = False
    node_y_pos = 0.0
    nodedescription = None
    for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
        attrib = subnode.attrib
        #print(attrib)
        if attrib == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
            is_d5 = True
            nodedescription = subnode.text
            #print(nodedescription)
        if attrib == {'key': 'd6'}:
            for geometry in subnode.findall('./{http://www.yworks.com/xml/graphml}SVGNode/{http://www.yworks.com/xml/graphml}Geometry'):
                node_y_pos = float(geometry.attrib['y'])
                #print("il valore y di nodo "+ str(nodedescription) +" = "+str(node_y_pos))
    if not is_d5:
        nodedescription = '--None--'
    return nodedescription, node_y_pos 


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
    my_nodename, my_node_description, my_node_url, my_node_shape, my_node_y_pos, my_node_fill_color = EM_extract_node_name(node_element)
#    print(my_node_shape)
    if my_node_shape in US_nodes_list:
        id_node_us = True
    else:
        id_node_us = False
    return id_node_us

def EM_check_node_continuity(node_element):
    id_node_continuity = False
    my_node_description, my_node_y_pos = EM_extract_continuity(node_element)
    if my_node_description == "_continuity":
        id_node_continuity = True
        #print("found node continuity")
    else:
        id_node_continuity = False
    return id_node_continuity

def EM_list_clear(context):
    scene = context.scene
    scene.em_list.update()
    list_lenght = len(scene.em_list)
    for x in range(list_lenght):
        scene.em_list.remove(0)
    return

def EM_reused_list_clear(context):
    scene = context.scene
    scene.em_reused.update()
    list_lenght = len(scene.em_reused)
    for x in range(list_lenght):
        scene.em_reused.remove(0)
    return

def epoch_list_clear(context):
    scene = context.scene
    scene.epoch_list.update()
    list_lenght = len(scene.epoch_list)
    for x in range(list_lenght):
        scene.epoch_list.remove(0)
    return

def sources_list_clear(context):
    scene = context.scene
    scene.em_sources_list.update()
    list_lenght = len(scene.em_sources_list)
    for x in range(list_lenght):
        scene.em_sources_list.remove(0)
    return


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
        #print(str(id_row))
        epoch_list_index_ema += 1        

    for nodelabel in node_element.findall('./{http://graphml.graphdrawing.org/xmlns}data/{http://www.yworks.com/xml/graphml}TableNode/{http://www.yworks.com/xml/graphml}NodeLabel'):
        RowNodeLabelModelParameter = nodelabel.find('.//{http://www.yworks.com/xml/graphml}RowNodeLabelModelParameter')
        if RowNodeLabelModelParameter is not None:
            label_node = nodelabel.text
            id_node = str(RowNodeLabelModelParameter.attrib['id'])
            # read the color of the epoch from the title of the row, if no color is provided, a default color is used
            if 'backgroundColor' in nodelabel.attrib:
                e_color = str(nodelabel.attrib['backgroundColor'])
                #print(e_color)
            else:
                e_color = "#BCBCBC"
            #print(e_color)
        else:
            id_node = "null"
            
        for i in range(len(scene.epoch_list)):
            id_key = scene.epoch_list[i].id
            if id_node == id_key:
                scene.epoch_list[i].name = str(label_node)
                scene.epoch_list[i].epoch_color = e_color
                scene.epoch_list[i].epoch_RGB_color = hex_to_rgb(e_color)

## #### #### #### #### #### #### #### #### #### #### #### ####
#### Check the presence-absence of US against the GraphML ####
## #### #### #### #### #### #### #### #### #### #### #### ####

def EM_check_GraphML_Blender(node_name):
    data = bpy.data
    icon_check = 'RESTRICT_INSTANCED_ON'
    for ob in data.objects:
        if ob.name == node_name:
            icon_check = 'RESTRICT_INSTANCED_OFF'
    return icon_check

def update_icons(context):
    scene = context.scene
    for US in scene.em_list:
        US.icon = EM_check_GraphML_Blender(US.name)
    return

## #### #### #### #### #### #### #### ####                       
 #### General functions for materials ####
## #### #### #### #### #### #### #### ####

def update_display_mode(self, context):
    if bpy.context.scene.proxy_display_mode == "EM":
        bpy.ops.emset.emmaterial()
    if bpy.context.scene.proxy_display_mode == "Periods":
        bpy.ops.emset.epochmaterial()

def em_setup_mat_cycles(matname, R, G, B):
    scene = bpy.context.scene
    mat = bpy.data.materials[matname]
    mat.diffuse_color[0] = R
    mat.diffuse_color[1] = G
    mat.diffuse_color[2] = B
    mat.show_transparent_back = False
    mat.use_backface_culling = True
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    mat.use_backface_culling = True
    mat.blend_method = scene.proxy_blend_mode
    links = mat.node_tree.links
    nodes = mat.node_tree.nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (0, 0)
    mainNode = nodes.new('ShaderNodeBsdfDiffuse')
    mainNode.inputs['Color'].default_value = (R,G,B,scene.proxy_display_alpha)
    mainNode.location = (-800, 50)
    mainNode.name = "diffuse"
    mixNode = nodes.new('ShaderNodeMixShader')
    mixNode.location = (-400,-50)
    transpNode = nodes.new('ShaderNodeBsdfTransparent')
    transpNode.location = (-800,-200)
    mixNode.name = "mixnode"
    mixNode.inputs[0].default_value = scene.proxy_display_alpha

    links.new(mainNode.outputs[0], mixNode.inputs[1])
    links.new(transpNode.outputs[0], mixNode.inputs[2])
    links.new(mixNode.outputs[0], output.inputs[0])
    
def check_material_presence(matname):
    mat_presence = False
    for mat in bpy.data.materials:
        if mat.name == matname:
            mat_presence = True
            return mat_presence
    return mat_presence

#  #### #### #### #### #### #### ####
#### Functions materials for EM  ####
#  #### #### #### #### #### #### ####

def consolidate_EM_material_presence(overwrite_mats):
    EM_mat_list = ['US', 'USVs', 'USVn', 'VSF', 'SF']
    for EM_mat_name in EM_mat_list:
        if not check_material_presence(EM_mat_name):
            EM_mat = bpy.data.materials.new(name=EM_mat_name)
            overwrite_mats = True
        if overwrite_mats == True:
            scene = bpy.context.scene
            R, G, B = EM_mat_get_RGB_values(EM_mat_name)
            em_setup_mat_cycles(EM_mat_name,R,G,B)

def set_EM_materials_using_EM_list(context):
    em_list_lenght = len(context.scene.em_list)
    #print(str(em_list_lenght))
    counter = 0
    while counter < em_list_lenght:
        current_ob_em_list = context.scene.em_list[counter]
        overwrite_mats = True
        consolidate_EM_material_presence(overwrite_mats)
        if current_ob_em_list.icon == 'RESTRICT_INSTANCED_OFF':
            current_ob_scene = context.scene.objects[current_ob_em_list.name]
            current_ob_scene.name
            ob_material_name = 'US'
            #print(current_ob_em_list.name + ' has symbol: ' +current_ob_em_list.shape)
            if current_ob_em_list.shape == 'rectangle':
                ob_material_name = 'US'
            if current_ob_em_list.shape == 'ellipse_white':
                ob_material_name = 'US'
                #print("found ellipse white")
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

def proxy_shader_mode_function(self, context):
    scene = context.scene
    if scene.proxy_shader_mode is True:
        scene.proxy_blend_mode = "ADD"
    else:
        scene.proxy_blend_mode = "BLEND"
    update_display_mode(self, context)

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

def hex_to_rgb(value):
    gamma = 2.2
    value = value.lstrip('#')
    lv = len(value)
    fin = list(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))
    r = pow(fin[0] / 255, gamma)
    g = pow(fin[1] / 255, gamma)
    b = pow(fin[2] / 255, gamma)
    fin.clear()
    fin.append(r)
    fin.append(g)
    fin.append(b)
    #fin.append(1.0)
    return tuple(fin)

# #### #### #### #### #### ####
#### materials for epochs  ####
# #### #### #### #### #### ####

def consolidate_epoch_material_presence(matname):
    if not check_material_presence(matname):
        epoch_mat = bpy.data.materials.new(name=matname)
    else:
        epoch_mat = bpy.data.materials[matname]
    return epoch_mat

def set_epoch_materials(context):
    scene = context.scene 
    mat_prefix = "ep_"
    for epoch in scene.epoch_list:
        matname = mat_prefix + epoch.name
        mat = consolidate_epoch_material_presence(matname)
        R = epoch.epoch_RGB_color[0]
        G = epoch.epoch_RGB_color[1]
        B = epoch.epoch_RGB_color[2]
        em_setup_mat_cycles(matname,R,G,B)
        for em_element in scene.em_list:
            if em_element.icon == "RESTRICT_INSTANCED_OFF":
                if em_element.epoch == epoch.name:
                    #print(em_element.name + " element is in epoch "+epoch.name)
                    obj = bpy.data.objects[em_element.name]
                    obj.data.materials.clear()
                    obj.data.materials.append(mat)
