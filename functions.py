import xml.etree.ElementTree as ET
import bpy
import os
import shutil
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

def is_reconstruction_us(node):
    is_rec = False
    if node.shape in ["parallelogram", "ellipse", "hexagon", "octagon"]:
        is_rec = True

    return is_rec

### #### #### #### #### #### #### #### ####
##### functions to switch menus in UI  ####
### #### #### #### #### #### #### #### ####

def sync_Switch_em(self, context):
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
    scene = context.scene
    em_settings = scene.em_settings
    if scene.em_settings.em_proxy_sync2 is True:
        scene.em_settings.em_proxy_sync = False
    return

## #### #### #### #### #### #### #### #### #### #### ####
##### Functions to check properties of scene objects ####
## #### #### #### #### #### #### #### #### #### #### ####

def check_if_current_obj_has_brother_inlist(obj_name, list_type):
    scene = bpy.context.scene
    list_cmd = ("scene."+ list_type)
    for element_list in eval(list_cmd):
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

def select_list_element_from_obj_proxy(obj, list_type):
    scene = bpy.context.scene
    index_list = 0
    list_cmd = ("scene."+ list_type)
    list_index_cmd = ("scene."+ list_type+"_index = index_list")
    for i in eval(list_cmd):
        if obj.name == i.name:
            exec(list_index_cmd)
            pass
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

def EM_extract_combiner_node(node_element):

    is_d4 = False
    is_d5 = False
    node_id = node_element.attrib['id']
    if len(node_id) > 2:
        subnode_is_combiner = False
        nodeurl = " "
        nodename = " "
        node_description = " "
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib1 = subnode.attrib
            #print(subnode.tag)
            if attrib1 == {'key': 'd6'}:
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = check_if_empty(USname.text)
                if nodename.startswith("C."):
                    subnode_is_combiner = True
                    #print(nodename)
                # for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}SVGContent'):
                #     attrib2 = nodetype.attrib
                #     if attrib2 == {'refid': '3'}:
                #         subnode_is_combiner = True
                        
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib1 = subnode.attrib                        
            if subnode_is_combiner is True:

                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
                    if subnode.text is not None:
                        is_d4 = True
                        nodeurl = check_if_empty(subnode.text)
                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                    is_d5 = True
                    node_description = clean_comments(check_if_empty(subnode.text))

        if not is_d4:
            nodeurl = '--None--'
        if not is_d5:
            nodedescription = '--None--'
        return nodename, node_id, node_description, nodeurl, subnode_is_combiner

def EM_extract_extractor_node(node_element):

    is_d4 = False
    is_d5 = False
    node_id = node_element.attrib['id']
    if len(node_id) > 2:
        subnode_is_extractor = False
        nodeurl = " "
        nodename = " "
        node_description = " "
        is_document = False
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib1 = subnode.attrib
            #print(subnode.tag)
            if attrib1 == {'key': 'd6'}:
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = check_if_empty(USname.text)
                if nodename.startswith("D."):
                    for elem in bpy.context.scene.em_sources_list:
                        if nodename == elem.name:
                            is_document = True
                    if not is_document:
                        #print(f"il nodo non è un documento e si chiama: {nodename}")
                        subnode_is_extractor = True
                # for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}SVGContent'):
                #     attrib2 = nodetype.attrib
                #     if attrib2 == {'refid': '1'}:
                #         subnode_is_extractor = True
                        
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib1 = subnode.attrib                        
            if subnode_is_extractor is True:

                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
                    if subnode.text is not None:
                        is_d4 = True
                        nodeurl = check_if_empty(subnode.text)
                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                    is_d5 = True
                    node_description = clean_comments(check_if_empty(subnode.text))

        if not is_d4:
            nodeurl = '--None--'
        if not is_d5:
            nodedescription = '--None--'
        return nodename, node_id, node_description, nodeurl, subnode_is_extractor

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
                    if subnode.text is not None:
                        is_d4 = True
                        nodeurl = subnode.text
                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                    is_d5 = True
                    node_description = clean_comments(subnode.text)
        if not is_d4:
            nodeurl = '--None--'
        if not is_d5:
            nodedescription = '--None--'
        return nodename, node_id, node_description, nodeurl, subnode_is_document

def check_if_empty(name):
    if name == None:
        name = "--None--"
    return name

def EM_extract_property_node(node_element):
    is_d4 = False
    is_d5 = False
    node_id = node_element.attrib['id']
    if len(node_id) > 2:
        subnode_is_property = False
        nodeurl = " "
        nodename = " "
        node_description = " "
        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib1 = subnode.attrib
            if attrib1 == {'key': 'd6'}:
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = check_if_empty(USname.text)
                for nodetype in subnode.findall('.//{http://www.yworks.com/xml/graphml}Property'):
                    attrib2 = nodetype.attrib
                    if attrib2 == {'class': 'com.yworks.yfiles.bpmn.view.BPMNTypeEnum', 'name': 'com.yworks.bpmn.type', 'value': 'ARTIFACT_TYPE_ANNOTATION'}:
                        subnode_is_property = True

        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib1 = subnode.attrib                        
            if subnode_is_property is True:

                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
                    if subnode.text is not None:
                        is_d4 = True
                        nodeurl = subnode.text
                if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                    is_d5 = True
                    node_description = clean_comments(subnode.text)

        if not is_d4:
            nodeurl = '--None--'
        if not is_d5:
            nodedescription = '--None--'        


    return nodename, node_id, node_description, nodeurl, subnode_is_property

def clean_comments(text_to_clean):
    clean_text = text_to_clean.split("##")[0].replace("\n","")
    return clean_text

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
        if attrib == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
            is_d4 = True
            nodeurl = subnode.text
        if attrib == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
            is_d5 = True
            nodedescription = clean_comments(subnode.text)
        if attrib == {'key': 'd6'}:
            for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                nodename = check_if_empty(USname.text)
            for fill_color in subnode.findall('.//{http://www.yworks.com/xml/graphml}Fill'):
                fillcolor = fill_color.attrib['color']
            for USshape in subnode.findall('.//{http://www.yworks.com/xml/graphml}Shape'):
                nodeshape = USshape.attrib['type']
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
    if "yfiles.foldertype" in id_node:
        tablenode = node_element.find('.//{http://www.yworks.com/xml/graphml}TableNode')
        if tablenode is not None:
            #print(' un nodo swimlane: ' + id_node)
            node_type = 'node_swimlane'
        else:
            #print(' un nodo group: ' + id_node)
            node_type = 'node_group'
    else:
        #print(' un semplice nodo: ' + id_node)
        node_type = 'node_simple'
    return node_type

def EM_check_node_us(node_element):
    US_nodes_list = ['rectangle', 'parallelogram',
                     'ellipse', 'hexagon', 'octagon', 'roundrectangle']
    my_nodename, my_node_description, my_node_url, my_node_shape, my_node_y_pos, my_node_fill_color = EM_extract_node_name(node_element)
    #print(my_node_shape)
    if my_node_shape in US_nodes_list:
        id_node_us = True
    else:
        id_node_us = False
    return id_node_us

def EM_check_node_document(node_element):
    try:
        src_nodename, src_node_id, src_node_description, src_nodeurl, subnode_is_document = EM_extract_document_node(node_element)
    except TypeError as e:
        subnode_is_document = False
        #print(f"Huston abbiamo un problema {e} al nodo {node_element}")
    return subnode_is_document

def EM_check_node_property(node_element):
    try:
        pro_nodename, pro_node_id, pro_node_description, pro_nodeurl, subnode_is_property = EM_extract_property_node(node_element)
    except UnboundLocalError as e:
        subnode_is_property = False
    return subnode_is_property

def EM_check_node_extractor(node_element):
    try:
        ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_extractor = EM_extract_extractor_node(node_element)
    except TypeError as e:
        subnode_is_extractor = False
    return subnode_is_extractor

def EM_check_node_combiner(node_element):
    try:
        com_nodename, com_node_id, com_node_description, com_nodeurl, subnode_is_combiner = EM_extract_combiner_node(node_element)
    except TypeError as e:
        subnode_is_combiner = False
    return subnode_is_combiner

def EM_check_node_continuity(node_element):
    id_node_continuity = False
    my_node_description, my_node_y_pos = EM_extract_continuity(node_element)
    if my_node_description == "_continuity":
        id_node_continuity = True
        #print("found node continuity")
    else:
        id_node_continuity = False
    return id_node_continuity

def EM_list_clear(context, list_type):
    scene = context.scene
    list_cmd1 = "scene."+list_type+".update()"
    list_cmd2 = "len(scene."+list_type+")"
    list_cmd3 = "scene."+list_type+".remove(0)"
    eval(list_cmd1)
    list_lenght = eval(list_cmd2)
    for x in range(list_lenght):
        eval(list_cmd3)
    return

def extract_epochs(node_element):
    geometry = node_element.find('.//{http://www.yworks.com/xml/graphml}Geometry')
    y_start = float(geometry.attrib['y'])
    context = bpy.context
    scene = context.scene    
    EM_list_clear(context, "epoch_list")  
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

def read_edge_db(context, tree):
    alledges = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}edge')
    scene = context.scene
    EM_list_clear(context, "edges_list")
    em_list_index_ema = 0

    for edge in alledges:
        #print(str(edge.attrib['id']))
        scene.edges_list.add()
        scene.edges_list[em_list_index_ema].id_node = str(edge.attrib['id'])
        scene.edges_list[em_list_index_ema].source = str(edge.attrib['source'])#getnode_edge_source(edge)
        scene.edges_list[em_list_index_ema].target = str(edge.attrib['target'])#getnode_edge_target(edge)
        #print(scene.edges_list[em_list_index_ema].id_node)
        #print(scene.edges_list[em_list_index_ema].target)
        em_list_index_ema += 1
    return

def stream_properties(self, context):
    scene = context.scene
    if scene.prop_paradata_streaming_mode:
        #print("qui ci arrivo")
        selected_property_node = scene.em_v_properties_list[scene.em_v_properties_list_index]
        #print("il nodo che voglio inseguire: "+selected_property_node.name)
        is_combiner = create_derived_combiners_list(selected_property_node)
        if not is_combiner:
            create_derived_extractors_list(selected_property_node)
    else:
        for v_list_property in scene.em_v_properties_list:
            is_combiner = create_derived_combiners_list(v_list_property)
            if not is_combiner:
                create_derived_extractors_list(v_list_property)       

        create_derived_extractors_list(scene.em_v_properties_list[scene.em_v_properties_list_index])

    return

def stream_combiners(self, context):
    scene = context.scene
    if scene.comb_paradata_streaming_mode:
        create_derived_extractors_list(scene.em_v_combiners_list[scene.em_v_combiners_list_index])
    else:
        pass
    return

def stream_extractors(self, context):
    scene = context.scene
    if scene.extr_paradata_streaming_mode:
        create_derived_sources_list(scene.em_v_extractors_list[scene.em_v_extractors_list_index])
    else:
        pass
    return

def create_derived_lists(node):
    context = bpy.context
    scene = context.scene
    prop_index = 0
    EM_list_clear(context, "em_v_properties_list")

    is_property = False

    # pass degli edges
    for edge_item in scene.edges_list:
        #print("arco id: "+edge_item.id_node)
        #controlliamo se troviamo edge che parte da lui
        if edge_item.source == node.id_node:
            # pass delle properties
            for property_item in scene.em_properties_list:
                #controlliamo se troviamo una proprietà di arrivo compatibile con l'edge
                if edge_item.target == property_item.id_node:
                   # print("trovato nodo: "+ node.name+" con proprieta: "+ property_item.name)
                    scene.em_v_properties_list.add()
                    scene.em_v_properties_list[prop_index].name = property_item.name
                    scene.em_v_properties_list[prop_index].description = property_item.description
                    scene.em_v_properties_list[prop_index].url = property_item.url
                    scene.em_v_properties_list[prop_index].id_node = property_item.id_node
                    prop_index += 1
                    is_property = True
                    #if not scene.prop_paradata_streaming_mode:
                        
    if is_property:
        if scene.prop_paradata_streaming_mode:
            #print("qui ci arrivo")
            selected_property_node = scene.em_v_properties_list[scene.em_v_properties_list_index]
            #print("il nodo che voglio inseguire: "+selected_property_node.name)
            is_combiner = create_derived_combiners_list(selected_property_node)
            if not is_combiner:
                create_derived_extractors_list(selected_property_node)
        else:
            for v_list_property in scene.em_v_properties_list:
                is_combiner = create_derived_combiners_list(v_list_property)
                if not is_combiner:
                    create_derived_extractors_list(v_list_property)                

    else:
        EM_list_clear(context, "em_v_extractors_list")
        EM_list_clear(context, "em_v_sources_list")
        EM_list_clear(context, "em_v_combiners_list")

    #print("property: "+ str(prop_index))     
    return

def create_derived_combiners_list(passed_property_item):
    context = bpy.context
    scene = context.scene
    comb_index = 0
    is_combiner = False
    EM_list_clear(context, "em_v_combiners_list")

    #print("La proprieta: "+passed_property_item.name+" ha id_nodo: "+passed_property_item.id_node)
    #scene.em_v_combiners_list_index = 0

    for edge_item in scene.edges_list:
        #print(property_item.id_node)
        #controlliamo se troviamo un edge che parte da questa proprietà
        if edge_item.source == passed_property_item.id_node:
            #print("trovato arco in uscita dalla proprietà "+property_item.name+" con id: "+property_item.id_node)
            # una volta trovato l'edge, faccio un pass degli estrattori 
            for combiner_item in scene.em_combiners_list:
                # controlliamo se troviamo un estrattore di arrivo compatibile con l'edge
                if edge_item.target == combiner_item.id_node:
                    #print("trovato estrattore: "+ combiner_item.name+ " per la proprietà: "+ passed_property_item.name)
                    scene.em_v_combiners_list.add()
                    scene.em_v_combiners_list[comb_index].name = combiner_item.name
                    scene.em_v_combiners_list[comb_index].description = combiner_item.description
                    scene.em_v_combiners_list[comb_index].url = combiner_item.url
                    scene.em_v_combiners_list[comb_index].id_node = combiner_item.id_node
                    # trovato l'estrattore connesso ora riparto dal pass degli edges
                    is_combiner = True
                    #if not scene.extr_paradata_streaming_mode:
                    comb_index += 1
    if is_combiner:
        if scene.comb_paradata_streaming_mode:
            #print("qui ci arrivo")
            selected_combiner_node = scene.em_v_combiners_list[scene.em_v_combiners_list_index]
            #selected_property_node = scene.em_v_properties_list[0]
            #print("il nodo che voglio inseguire: "+selected_combiner_node.name)
            create_derived_sources_list(selected_combiner_node)
        else:
            for v_list_combiner in scene.em_v_combiners_list:
                create_derived_sources_list(v_list_combiner)

    else:
        EM_list_clear(context, "em_v_sources_list")
        EM_list_clear(context, "em_v_extractors_list")

   # print("combiners: "+ str(comb_index))

    return is_combiner

def create_derived_extractors_list(passed_property_item):
    context = bpy.context
    scene = context.scene
    extr_index = 0
    is_extractor = False
    EM_list_clear(context, "em_v_extractors_list")

   # print("La proprieta: "+passed_property_item.name+" ha id_nodo: "+passed_property_item.id_node)
    #scene.em_v_extractors_list_index = 0

    for edge_item in scene.edges_list:
        #print(property_item.id_node)
        #controlliamo se troviamo un edge che parte da questa proprietà
        if edge_item.source == passed_property_item.id_node:
            #print("trovato arco in uscita dalla proprietà "+property_item.name+" con id: "+property_item.id_node)
            # una volta trovato l'edge, faccio un pass degli estrattori 
            for extractor_item in scene.em_extractors_list:
                # controlliamo se troviamo un estrattore di arrivo compatibile con l'edge
                if edge_item.target == extractor_item.id_node:
                   # print("trovato estrattore: "+ extractor_item.name+ " per la proprietà: "+ passed_property_item.name)
                    scene.em_v_extractors_list.add()
                    scene.em_v_extractors_list[extr_index].name = extractor_item.name
                    scene.em_v_extractors_list[extr_index].description = extractor_item.description
                    scene.em_v_extractors_list[extr_index].url = extractor_item.url
                    scene.em_v_extractors_list[extr_index].id_node = extractor_item.id_node
                    # trovato l'estrattore connesso ora riparto dal pass degli edges
                    is_extractor = True
                    #if not scene.extr_paradata_streaming_mode:
                    extr_index += 1
    if is_extractor:
        if scene.extr_paradata_streaming_mode:
            #print("qui ci arrivo")
            selected_extractor_node = scene.em_v_extractors_list[scene.em_v_extractors_list_index]
            #selected_property_node = scene.em_v_properties_list[0]
           # print("il nodo che voglio inseguire: "+selected_extractor_node.name)
            create_derived_sources_list(selected_extractor_node)
        else:
            for v_list_extractor in scene.em_v_extractors_list:
                create_derived_sources_list(v_list_extractor)

    else:
        EM_list_clear(context, "em_v_sources_list")

    #print("extractors: "+ str(extr_index))

def create_derived_sources_list(passed_extractor_item):
    context = bpy.context
    scene = context.scene
    sour_index = 0
    EM_list_clear(context, "em_v_sources_list")
    #print("passed_extractor_item: "+passed_extractor_item.name+" con id: "+passed_extractor_item.id_node)
    for edge_item in scene.edges_list:
        
        #controlliamo se troviamo un edge che parte da questo estrattore
        if edge_item.source == passed_extractor_item.id_node:
            #print("TROVATO arco in uscita ("+edge_item.id_node+")  dall'estrattore: "+passed_extractor_item.id_node+" e che porta al nodo: "+edge_item.target)
            # una volta trovato l'edge, faccio un pass delle sources
            for source_item in scene.em_sources_list:
                #print(source_item.id_node+ " con nome: "+source_item.name)
                # controlliamo se troviamo un estrattore di arrivo compatibile con l'edge
                if edge_item.target == source_item.id_node:
                    #print("trovato nodo source: "+source_item.name+" che parte dall'estrattore: "+passed_extractor_item.name)
                    scene.em_v_sources_list.add()
                    scene.em_v_sources_list[sour_index].name = source_item.name
                    scene.em_v_sources_list[sour_index].description = source_item.description
                    scene.em_v_sources_list[sour_index].url = source_item.url
                    scene.em_v_sources_list[sour_index].id_node = source_item.id_node
                    sour_index += 1

    #print("sources: "+ str(sour_index))

def switch_paradata_lists(self, context):
    scene = context.scene
    if scene.paradata_streaming_mode:
        #print("sto lanciano dil comando again")
        node = scene.em_list[scene.em_list_index]
        create_derived_lists(node)

    if scene.em_list[scene.em_list_index].icon_db == 'DECORATE_KEYFRAME':
        index_to_find = 0
        while index_to_find < len(scene.emdb_list):
            if scene.emdb_list[index_to_find].name == scene.em_list[scene.em_list_index].name:
                print("Ho trovato il record giusto")
                scene.emdb_list_index = index_to_find
            index_to_find +=1
    return

## #### #### #### #### #### #### #### #### #### #### #### ####
#### Check the presence-absence of US against the GraphML ####
## #### #### #### #### #### #### #### #### #### #### #### ####

def check_objs_in_scene_and_provide_icon_for_list_element(list_element_name):
    data = bpy.data
    icon_check = 'RESTRICT_INSTANCED_ON'
    for ob in data.objects:
        if ob.name == list_element_name:
            icon_check = 'RESTRICT_INSTANCED_OFF'
    return icon_check

def update_icons(context,list_type):
    scene = context.scene
    list_path = "scene."+list_type
    for element in eval(list_path):
        element.icon = check_objs_in_scene_and_provide_icon_for_list_element(element.name)
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
    mat.use_backface_culling = False
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
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
    EM_mat_list = ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD']
    for EM_mat_name in EM_mat_list:
        if not check_material_presence(EM_mat_name):
            EM_mat = bpy.data.materials.new(name=EM_mat_name)
            overwrite_mats = True
        if overwrite_mats == True:
            scene = bpy.context.scene
            R, G, B = EM_mat_get_RGB_values(EM_mat_name)
            em_setup_mat_cycles(EM_mat_name,R,G,B)

def set_materials_using_EM_list(context):
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
            if current_ob_em_list.shape == 'rectangle':
                ob_material_name = 'US'
            if current_ob_em_list.shape == 'ellipse_white':
                ob_material_name = 'US'
            if current_ob_em_list.shape ==  'ellipse':
                ob_material_name = 'USVn'
            if current_ob_em_list.shape ==  'parallelogram':
                ob_material_name = 'USVs'
            if current_ob_em_list.shape ==  'hexagon':
                ob_material_name = 'USVn'
            if current_ob_em_list.shape ==  'octagon':
                ob_material_name = 'VSF'
            if current_ob_em_list.shape ==  'octagon_white':
                ob_material_name = 'SF'
            if current_ob_em_list.shape == 'roundrectangle':
                ob_material_name = 'USD'
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
    elif matname == "VSF":
        #errati su articolo five steps
        #R = 0.694
        #G = 0.623
        #B = 0.380
        R = 0.439
        G = 0.346
        B = 0.119
    elif matname == "SF":
        #errati su articolo five steps
        #R = 0.847
        #G = 0.741
        #B = 0.188
        R = 0.686
        G = 0.508
        B = 0.029
    elif matname == "USD":
        R = 0.549
        G = 0.103
        B = 0.000
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

def set_materials_using_epoch_list(context):
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


class OBJECT_OT_CenterMass(bpy.types.Operator):
    bl_idname = "center.mass"
    bl_label = "Center Mass"
    bl_options = {"REGISTER", "UNDO"}

    center_to: StringProperty()

    def execute(self, context):
    #        bpy.ops.object.select_all(action='DESELECT')
        if self.center_to == "mass":
            selection = context.selected_objects
            # translate objects in SCS coordinate
            for obj in selection:
                obj.select_set(True)
                bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS')
        elif self.center_to == "cursor":
            ob_active = context.active_object
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR')

        return {'FINISHED'}


class OBJECT_OT_labelonoff(bpy.types.Operator):
    bl_idname = "label.onoff"
    bl_label = "Label on / off"
    bl_options = {"REGISTER", "UNDO"}

    onoff: BoolProperty()

    def execute(self, context):
        selection = context.selected_objects
        for obj in selection:
            obj.select_set(True)
            obj.show_name = self.onoff
        return {'FINISHED'}


#############################################
## funzioni per esportare obj e textures 
#############################################

def get_principled_node(mat):
    for node in mat.node_tree.nodes:
        if node.name == 'Principled BSDF':
            return node

def get_connected_input_node(node, input_link):
    node_input = node.inputs[input_link].links[0].from_node
    return node_input

def extract_image_paths_from_mat(ob, mat):
    node = get_principled_node(mat)
    relevant_input_links = ['Base Color', 'Roughness', 'Metallic', 'Normal']
    found_paths = []
    image_path = ''
    context = bpy.context
    for input_link in relevant_input_links:
        if node.inputs[input_link].is_linked:
            node_input = get_connected_input_node(node, input_link)
            if node_input.type == 'TEX_IMAGE':
                image_path = node_input.image.filepath_from_user() 
                found_paths.append(image_path)
            else:
                # in case of normal map
                if input_link == 'Normal' and node_input.type == 'NORMAL_MAP':
                    if node_input.inputs['Color'].is_linked:
                        node_input_input = get_connected_input_node(node_input, 'Color')
                        image_path = node_input_input.image.filepath_from_user() 
                        found_paths.append(image_path)
                    else:
                        found_paths.append('None')
                        emviq_error_record_creator(ob, "missing image node", mat, input_link)

                else:
                    found_paths.append('None')
                    emviq_error_record_creator(ob, "missing image node", mat, input_link)
                                      
        else:
            found_paths.append('None')
            emviq_error_record_creator(ob, "missing image node", mat, input_link)
    
    return found_paths

def emviq_error_record_creator(ob, description, mat, tex_type):
    scene = bpy.context.scene
    scene.emviq_error_list.add()
    ultimorecord = len(scene.emviq_error_list)-1
    scene.emviq_error_list[ultimorecord].name = ob.name
    scene.emviq_error_list[ultimorecord].description = description
    scene.emviq_error_list[ultimorecord].material = mat.name
    scene.emviq_error_list[ultimorecord].texture_type = tex_type


def copy_tex_ob(ob, destination_path):
    # remove old mtl files
    mtl_file = os.path.join(destination_path, ob.name+".mtl")
    os.remove(mtl_file)
    #creating a new custom mtl file
    f = open(mtl_file, 'w', encoding='utf-8')     
    for mat in ob.material_slots:
        f.write("%s %s\n" % ("newmtl", mat.material.name))
        image_file_path = extract_image_paths_from_mat(ob, mat.material)
        number_type = 0
        for current_file_path in image_file_path:
            if current_file_path != 'None':
                current_path_splitted = os.path.split(current_file_path)
                suffix = set_tex_type_name(number_type)
                current_image_file = os.path.splitext(current_path_splitted[1])
                #current_image_file_with_suffix = (current_image_file[0] + '_' + suffix + current_image_file[1])
                current_image_file_with_suffix = (mat.name + '_' + suffix + current_image_file[1])
                if number_type == 0:
                    f.write("%s %s\n" % ("map_Kd", current_image_file_with_suffix))
                destination_file = os.path.join(destination_path, current_image_file_with_suffix)
                shutil.copyfile(current_file_path, destination_file)
            number_type += 1
    f.close()

def set_tex_type_name(number_type):
    if number_type == 0:
        string_type = 'ALB'
    if number_type == 1:
        string_type = 'ROU'
    if number_type == 2:
        string_type = 'MET'
    if number_type == 3:
        string_type = 'NOR'
    return string_type

def substitue_with_custom_mtl(ob, export_sub_folder):
    mtl_file = os.path.join(export_sub_folder+ob.name+".mtl")
    os.remove(mtl_file)
    f = open(mtl_file, 'w', encoding='utf-8')
    for mat in ob.material_slots:
        f.write("%s %s\n" % ("newmtl", mat.material.name))
        f.write("%s %s\n" % ("map_Kd", mat.material.name+"_ALB"))
        mat.material.name


    f.close() 

#create_collection

class em_create_collection(bpy.types.Operator):
    bl_idname = "create.collection"
    bl_label = "Create Collection"
    bl_description = "Create Collection"
    bl_options = {'REGISTER', 'UNDO'}

    def create_collection(target_collection):
        context = bpy.context
        if bpy.data.collections.get(target_collection) is None:
            currentCol = bpy.context.blend_data.collections.new(name= target_collection)
            bpy.context.scene.collection.children.link(currentCol)
        else:
            currentCol = bpy.data.collections.get(target_collection)
        return currentCol