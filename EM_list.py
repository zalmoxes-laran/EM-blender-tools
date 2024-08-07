import bpy # type: ignore
import xml.etree.ElementTree as ET
import os
import bpy.props as prop # type: ignore


#from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, BoolVectorProperty, PointerProperty

from bpy.props import (BoolProperty, # type: ignore
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       CollectionProperty,
                       IntProperty,
                       PointerProperty,
                       FloatVectorProperty,
                       )

from bpy.types import ( # type: ignore
        AddonPreferences,
        PropertyGroup,
        )

from .functions import *
from .epoch_manager import *

from .s3Dgraphy import *
from .s3Dgraphy.node import StratigraphicNode  # Import diretto



#### da qui si definiscono le funzioni e gli operatori
class EM_listitem_OT_to3D(bpy.types.Operator):
    bl_idname = "listitem.toobj"
    bl_label = "Use element's name from the list above to rename selected 3D object"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty() # type: ignore

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None:
            pass
        else:
            return (obj.type in ['MESH'])

    def execute(self, context):
        scene = context.scene
        item_name_picker_cmd = "scene."+self.list_type+"[scene."+self.list_type+"_index]"
        item = eval(item_name_picker_cmd)
        context.active_object.name = item.name
        update_icons(context, self.list_type)
        if self.list_type == "em_list":
            if scene.proxy_display_mode == "EM":
                bpy.ops.emset.emmaterial()
            else:
                bpy.ops.emset.epochmaterial()
        return {'FINISHED'}

class EM_update_icon_list(bpy.types.Operator):
    bl_idname = "list_icon.update"
    bl_label = "Update only the icons"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty() # type: ignore

    def execute(self, context):
        if self.list_type == "all":
            lists = ["em_list","epoch_list","em_sources_list","em_properties_list","em_extractors_list","em_combiners_list","em_v_sources_list","em_v_properties_list","em_v_extractors_list","em_v_combiners_list"]
            for single_list in lists:
                update_icons(context, single_list)
        else:
            update_icons(context, self.list_type)
        return {'FINISHED'}

class EM_select_list_item(bpy.types.Operator):
    bl_idname = "select.listitem"
    bl_label = "Select element in the list above from a 3D proxy"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty() # type: ignore

    def execute(self, context):
        scene = context.scene
        obj = context.object
        select_list_element_from_obj_proxy(obj, self.list_type)
        return {'FINISHED'}

class EM_select_from_list_item(bpy.types.Operator):
    bl_idname = "select.fromlistitem"
    bl_label = "Select 3D obj from the list above"
    bl_options = {"REGISTER", "UNDO"}

    list_type: StringProperty() # type: ignore

    def execute(self, context):
        scene = context.scene
        list_type_cmd = "scene."+self.list_type+"[scene."+self.list_type+"_index]"
        list_item = eval(list_type_cmd)
        select_3D_obj(list_item.name)
        return {'FINISHED'}

class EM_not_in_matrix(bpy.types.Operator):
    bl_idname = "notinthematrix.material"
    bl_label = "Helper for proxies visualization"
    bl_description = "Apply a custom material to proxies not yet present in the matrix"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        EM_mat_list = ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD']
        EM_mat_name = "mat_NotInTheMatrix"
        R = 1.0
        G = 0.0
        B = 1.0
        if not check_material_presence(EM_mat_name):
            newmat = bpy.data.materials.new(EM_mat_name)
            em_setup_mat_cycles(EM_mat_name,R,G,B)

        for ob in bpy.data.objects:
            if ob.type == 'MESH':
                if ob.data.materials:
                    if ob.material_slots[0].material.name in EM_mat_list or ob.material_slots[0].material.name.startswith('ep_'):
                        matrix_mat = True
                    else:
                        matrix_mat = False
                    not_in_matrix = True
                    for item in context.scene.em_list:
                        if item.name == ob.name:
                            not_in_matrix = False
                    if matrix_mat and not_in_matrix:
                        ob.data.materials.clear()
                        notinmatrix_mat = bpy.data.materials[EM_mat_name]
                        ob.data.materials.append(notinmatrix_mat)

        return {'FINISHED'}

class EM_import_GraphML(bpy.types.Operator):
    bl_idname = "import.em_graphml"
    bl_label = "Import the EM GraphML"
    bl_description = "Import the EM GraphML"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        #setup scene variable
        scene = context.scene

        #execute import
        self.import_graphml(context)

        #ora esplora tutte le liste per cercare tutti i nodi rectangle e white_ellipse che NON sono connessi ad un continuity node in modo tale da dargli continuità fino all'ultima epoca dello swimlane
        self.find_and_add_us_nodes_without_continuity(context)

        # verifica post importazione: controlla che il contatore della lista delle UUSS sia nel range (può succedere di ricaricare ed avere una lista più corta di UUSS). In caso di necessità porta a 0 l'indice
        self.check_index_coherence(scene)
        
        # Integrazione di dati esterni: aggiunta dei percorsi effettivi di documenti estrattori e combiners dal DosCo
        em_settings = bpy.context.window_manager.em_addon_settings
        if em_settings.overwrite_url_with_dosco_filepath:
            inspect_load_dosco_files()
        
        #per aggiornare i nomi delle proprietà usando come prefisso in nome del nodo padre
        self.newnames_forproperties_from_fathernodes(scene)
        
        #crea liste derivate per lo streaming dei paradati
        create_derived_lists(scene.em_list[scene.em_list_index])
        
        #setup dei materiali di scena dopo l'importazione del graphml
        self.post_import_material_setup(context)

        return {'FINISHED'}
    

    def populate_blender_lists_from_graph(self, context, graph):
        scene = context.scene
        
        # Clear existing lists in Blender
        EM_list_clear(context, "em_list")
        
        for node in graph.nodes:
            if isinstance(node, StratigraphicNode):
                scene.em_list.add()
                em_item = scene.em_list[-1]
                em_item.name = node.name
                em_item.description = node.description
                em_item.shape = node.shape
                em_item.y_pos = node.y_pos
                em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
                em_item.id_node = node.node_id
                



    def import_graphml(self, context):
        scene = context.scene
        graphml_file = bpy.path.abspath(scene.EM_file)
        tree = ET.parse(graphml_file)
        
        # Clear existing lists in Blender
        EM_list_clear(context, "em_list")
        EM_list_clear(context, "em_reused")
        EM_list_clear(context, "em_sources_list")
        EM_list_clear(context, "em_properties_list")
        EM_list_clear(context, "em_extractors_list")
        EM_list_clear(context, "em_combiners_list")
        
        allnodes = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node')

        # Initialize an empty graph
        graph = Graph()

        #futura funzione
        #self.read_edge_db(graph, tree)
        # Parse edges first
        self.read_edge_db(context,tree)


        # Parse nodes and add them to the graph
        for node_element in allnodes:
            if self._check_node_type(node_element) == 'node_simple':
                if self.EM_check_node_us(node_element):
                    nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor, borderstyle = self.EM_extract_node_name(node_element)
                    
                    # Create a new StratigraphicNode and add to the graph
                    stratigraphic_node = StratigraphicNode(
                        node_id=self.getnode_id(node_element),
                        name=nodename,
                        description=nodedescription,
                        shape=nodeshape,
                        y_pos=float(node_y_pos),
                        fill_color=fillcolor,
                        border_style=borderstyle,
                        stratigraphic_type = convert_shape2type(nodeshape, borderstyle)[0]
                    )
                    graph.add_node(stratigraphic_node)

                '''
                elif self.EM_check_node_document(node_element):
                    source_already_in_list = False
                    source_number = 2
                    src_nodename, src_node_id, src_node_description, src_nodeurl, subnode_is_document = self.EM_extract_document_node(node_element)
                    src_nodename_safe = src_nodename
                    if em_sources_index_ema > 0: 
                        for source_item in scene.em_sources_list:
                            if source_item.name == src_nodename:
                                source_already_in_list = True
                                #finding the node in the edges list
                                for id_doc_node in scene.edges_list:
                                    if id_doc_node.target == src_node_id:
                                        id_doc_node.target = source_item.id_node

                    if not source_already_in_list:
                        #src_nodename = src_nodename+"_"+str(source_number)
                        #source_number +=1
                        scene.em_sources_list.add()
                        scene.em_sources_list[em_sources_index_ema].name = src_nodename
                        scene.em_sources_list[em_sources_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(src_nodename_safe)
                        scene.em_sources_list[em_sources_index_ema].id_node = src_node_id
                        scene.em_sources_list[em_sources_index_ema].url = src_nodeurl
                        if src_nodeurl == "":
                            scene.em_sources_list[em_sources_index_ema].icon_url = "CHECKBOX_DEHLT"
                        else:
                            scene.em_sources_list[em_sources_index_ema].icon_url = "CHECKBOX_HLT"
                        scene.em_sources_list[em_sources_index_ema].description = src_node_description
                        em_sources_index_ema += 1
                elif self.EM_check_node_property(node_element):
                    pro_nodename, pro_node_id, pro_node_description, pro_nodeurl, subnode_is_property = self.EM_extract_property_node(node_element)
                    scene.em_properties_list.add()
                    scene.em_properties_list[em_properties_index_ema].name = pro_nodename
                    scene.em_properties_list[em_properties_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(pro_nodename)
                    scene.em_properties_list[em_properties_index_ema].id_node = pro_node_id
                    scene.em_properties_list[em_properties_index_ema].url = pro_nodeurl
                    if pro_nodeurl == "":
                        scene.em_properties_list[em_properties_index_ema].icon_url = "CHECKBOX_DEHLT"
                    else:
                        scene.em_properties_list[em_properties_index_ema].icon_url = "CHECKBOX_HLT"
                    scene.em_properties_list[em_properties_index_ema].description = pro_node_description
                    em_properties_index_ema += 1
                elif self.EM_check_node_extractor(node_element):
                    ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_extractor = self.EM_extract_extractor_node(node_element)
                    scene.em_extractors_list.add()
                    scene.em_extractors_list[em_extractors_index_ema].name = ext_nodename
                    scene.em_extractors_list[em_extractors_index_ema].id_node = ext_node_id                   
                    scene.em_extractors_list[em_extractors_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(ext_nodename)
                    scene.em_extractors_list[em_extractors_index_ema].url = ext_nodeurl
                   #print(ext_nodeurl)
                    if ext_nodeurl == "":
                        scene.em_extractors_list[em_extractors_index_ema].icon_url = "CHECKBOX_DEHLT"
                    else:
                        scene.em_extractors_list[em_extractors_index_ema].icon_url = "CHECKBOX_HLT"
                    scene.em_extractors_list[em_extractors_index_ema].description = ext_node_description
                    em_extractors_index_ema += 1
                elif self.EM_check_node_combiner(node_element):
                    ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_combiner = self.EM_extract_combiner_node(node_element)
                    scene.em_combiners_list.add()
                    scene.em_combiners_list[em_combiners_index_ema].name = ext_nodename
                    scene.em_combiners_list[em_combiners_index_ema].id_node = ext_node_id                   
                    scene.em_combiners_list[em_combiners_index_ema].icon = check_objs_in_scene_and_provide_icon_for_list_element(ext_nodename)
                    scene.em_combiners_list[em_combiners_index_ema].url = ext_nodeurl
                   #print(ext_nodeurl)
                    if ext_nodeurl == "":
                        scene.em_combiners_list[em_combiners_index_ema].icon_url = "CHECKBOX_DEHLT"
                    else:
                        scene.em_combiners_list[em_combiners_index_ema].icon_url = "CHECKBOX_HLT"
                    scene.em_combiners_list[em_combiners_index_ema].description = ext_node_description
                    em_combiners_index_ema += 1
                else:
                    pass
                    '''

        #porzione di codice per estrarre le continuità
        for node_element in allnodes:
            if self._check_node_type(node_element) == 'node_simple': # The node is not a group or a swimlane
                if self.EM_check_node_continuity(node_element):
                    #print("found continuity node")
                    EM_us_target, continuity_y = self.get_edge_target(tree, node_element)
                    #print(EM_us_target+" has y value: "+str(continuity_y))
                    for EM_item in bpy.context.scene.em_list:
                        if EM_item.icon == "RESTRICT_INSTANCED_OFF":
                            if EM_item.name == EM_us_target:
                                for ep_i in range(len(scene.epoch_list)):
                                    #print("epoca "+epoch.name+" : min"+str(epoch.min_y)+" max: "+str(epoch.max_y)+" minore di "+str(continuity_y)+" e "+ str(epoch.min_y) +" minore di "+str(EM_item.y_pos))
                                    if scene.epoch_list[ep_i].max_y > continuity_y and scene.epoch_list[ep_i].max_y < EM_item.y_pos:
                                        #print("found")
                                        scene.em_reused.add()
                                        scene.em_reused[em_reused_index].epoch = scene.epoch_list[ep_i].name
                                        scene.em_reused[em_reused_index].em_element = EM_item.name
                                    #print("All'epoca "+scene.em_reused[em_reused_index].epoch+ " appartiene : "+ scene.em_reused[em_reused_index].em_element)
                                        em_reused_index += 1
        

        # Now populate the Blender lists from the graph
        self.populate_blender_lists_from_graph(context, graph)

        return {'FINISHED'}


    def find_and_add_us_nodes_without_continuity(self, context):
        scene = context.scene
        em_reused_index = len(scene.em_reused)

        # Scorri tutti i nodi US (rectangle) e serie di US (white_ellipse)
        for em_item in scene.em_list:
            if em_item.shape in ["rectangle", "white_ellipse"]:
                has_continuity = False

                # Scorri tutti gli archi per vedere se sono collegati a questo US
                for edge in scene.edges_list:
                    if edge.source == em_item.id_node:
                        target_node_element = self.find_node_element_by_id(context, edge.target)
                        if target_node_element and self.EM_check_node_continuity(target_node_element):
                            has_continuity = True
                            break

                # Se il nodo non ha continuità, aggiungilo a em_reused per tutte le epoche pertinenti
                if not has_continuity:
                    current_epoch = em_item.epoch
                    current_epoch_index = None

                    # Trova l'indice dell'epoca corrente
                    for ep_i, epoch in enumerate(scene.epoch_list):
                        if epoch.name == current_epoch:
                            current_epoch_index = ep_i
                            break

                    # Aggiungi il nodo a em_reused per tutte le epoche dalla corrente fino alla prima
                    if current_epoch_index is not None:
                        for ep_i in range(current_epoch_index, -1, -1):
                            scene.em_reused.add()
                            scene.em_reused[em_reused_index].epoch = scene.epoch_list[ep_i].name
                            scene.em_reused[em_reused_index].em_element = em_item.name
                            em_reused_index += 1

    def find_node_element_by_id(self, context, node_id):
        tree = ET.parse(bpy.path.abspath(context.scene.EM_file))
        allnodes = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node')
        
        for node_element in allnodes:
            if node_element.attrib['id'] == node_id:
                return node_element
        return None



    def extract_epochs(self, node_element):
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

    def read_edge_db(self, context, tree):
        alledges = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}edge')
        scene = context.scene
        EM_list_clear(context, "edges_list")  # Assumendo che EM_list_clear() sia ora un metodo
        em_list_index_ema = 0

        for edge in alledges:
            scene.edges_list.add()
            edge_item = scene.edges_list[em_list_index_ema]
            edge_item.id_node = str(edge.attrib['id'])
            edge_item.source = str(edge.attrib['source'])
            edge_item.target = str(edge.attrib['target'])
            edge_item.edge_type = self.EM_extract_edge_type(edge)  # Assumendo che EM_extract_edge_type() sia un altro metodo integrato
            em_list_index_ema += 1

    def EM_extract_edge_type(self, edge_element):
        edge_type = "Empty"
        for subedge in edge_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            #print(subedge.attrib)
            attrib1 = subedge.attrib
            #print(subnode.tag)
            if attrib1 == {'key': 'd10'}:
                type_vocab={}
                for property in subedge.findall('.//{http://www.yworks.com/xml/graphml}LineStyle'):
                    type_vocab = property.attrib #json.loads(property.attrib)
                    #print(type_vocab["type"])
                    edge_type = self.check_if_empty(type_vocab["type"])
                    
        return edge_type  

    def _check_node_type(self, node_element):
        id_node = str(node_element.attrib)
        if "yfiles.foldertype" in id_node:
            tablenode = node_element.find('.//{http://www.yworks.com/xml/graphml}TableNode')
            if tablenode is not None:
                return 'node_swimlane'
            else:
                return 'node_group'
        else:
            return 'node_simple'
    
    # UUSS NODE
    def EM_check_node_us(self, node_element):
        US_nodes_list = ['rectangle', 'parallelogram',
                        'ellipse', 'hexagon', 'octagon', 'roundrectangle']
        my_nodename, my_node_description, my_node_url, my_node_shape, my_node_y_pos, my_node_fill_color, my_node_border_style = self.EM_extract_node_name(node_element)
        if my_node_shape in US_nodes_list:
            id_node_us = True
        else:
            id_node_us = False
        return id_node_us
    
    def EM_extract_node_name(self, node_element):
        is_d4 = False
        is_d5 = False
        node_y_pos = None
        nodeshape = None
        nodeurl = None
        nodedescription = None
        nodename = None
        fillcolor = None
        borderstyle = None

        for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
            attrib = subnode.attrib
            if attrib == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
                is_d4 = True
                nodeurl = subnode.text
            if attrib == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                is_d5 = True
                nodedescription = self.clean_comments(subnode.text)
            if attrib == {'key': 'd6'}:
                for USname in subnode.findall('.//{http://www.yworks.com/xml/graphml}NodeLabel'):
                    nodename = self.check_if_empty(USname.text)
                for fill_color in subnode.findall('.//{http://www.yworks.com/xml/graphml}Fill'):
                    fillcolor = fill_color.attrib['color']
                for border_style in subnode.findall('.//{http://www.yworks.com/xml/graphml}BorderStyle'):
                    borderstyle = border_style.attrib['color']
                for USshape in subnode.findall('.//{http://www.yworks.com/xml/graphml}Shape'):
                    nodeshape = USshape.attrib['type']
                for geometry in subnode.findall('./{http://www.yworks.com/xml/graphml}ShapeNode/{http://www.yworks.com/xml/graphml}Geometry'):
                #for geometry in subnode.findall('./{http://www.yworks.com/xml/graphml}Geometry'):
                    node_y_pos = geometry.attrib['y']
        if not is_d4:
            nodeurl = ''
        if not is_d5:
            nodedescription = ''
        return nodename, nodedescription, nodeurl, nodeshape, node_y_pos, fillcolor, borderstyle     
    
    # DOCUMENT NODE
    def EM_check_node_document(self, node_element):
        try:
            src_nodename, src_node_id, src_node_description, src_nodeurl, subnode_is_document = self.EM_extract_document_node(node_element)
        except TypeError as e:
            subnode_is_document = False
        return subnode_is_document

    def EM_extract_document_node(self, node_element):
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
                        node_description = self.clean_comments(subnode.text)
            if not is_d4:
                nodeurl = ''
            if not is_d5:
                nodedescription = ''
            return nodename, node_id, node_description, nodeurl, subnode_is_document
    
    # PROPERTY NODE
    def EM_check_node_property(self, node_element):
        try:
            pro_nodename, pro_node_id, pro_node_description, pro_nodeurl, subnode_is_property = self.EM_extract_property_node(node_element)
        except UnboundLocalError as e:
            subnode_is_property = False
        return subnode_is_property

    def EM_extract_property_node(self, node_element):
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
                        nodename = self.check_if_empty(USname.text)
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
                        node_description = self.clean_comments(subnode.text)

            if not is_d4:
                nodeurl = ''
            if not is_d5:
                nodedescription = ''        
        return nodename, node_id, node_description, nodeurl, subnode_is_property

    # EXTRACTOR NODE
    def EM_check_node_extractor(self, node_element):
        try:
            ext_nodename, ext_node_id, ext_node_description, ext_nodeurl, subnode_is_extractor = self.EM_extract_extractor_node(node_element)
        except TypeError as e:
            subnode_is_extractor = False
        return subnode_is_extractor
    
    def EM_extract_extractor_node(self, node_element):

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
                        nodename = self.check_if_empty(USname.text)
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
                            nodeurl = self.check_if_empty(subnode.text)
                    if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                        is_d5 = True
                        node_description = self.clean_comments(self.check_if_empty(subnode.text))

            if not is_d4:
                nodeurl = ''
            if not is_d5:
                nodedescription = ''
            return nodename, node_id, node_description, nodeurl, subnode_is_extractor

    # COMBINER NODE
    def EM_check_node_combiner(self, node_element):
        try:
            com_nodename, com_node_id, com_node_description, com_nodeurl, subnode_is_combiner = self.EM_extract_combiner_node(node_element)
        except TypeError as e:
            subnode_is_combiner = False
        return subnode_is_combiner

    def EM_extract_combiner_node(self, node_element):
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
                        nodename = self.check_if_empty(USname.text)
                    if nodename.startswith("C."):
                        subnode_is_combiner = True
                            
            for subnode in node_element.findall('.//{http://graphml.graphdrawing.org/xmlns}data'):
                attrib1 = subnode.attrib                        
                if subnode_is_combiner is True:

                    if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd4'}:
                        if subnode.text is not None:
                            is_d4 = True
                            nodeurl = self.check_if_empty(subnode.text)
                    if attrib1 == {'{http://www.w3.org/XML/1998/namespace}space': 'preserve', 'key': 'd5'}:
                        is_d5 = True
                        node_description = self.clean_comments(self.check_if_empty(subnode.text))

            if not is_d4:
                nodeurl = ''
            if not is_d5:
                nodedescription = ''
            return nodename, node_id, node_description, nodeurl, subnode_is_combiner

    #CONTINUITY NODE
    def EM_check_node_continuity(self, node_element):
        id_node_continuity = False
        my_node_description, my_node_y_pos = self.EM_extract_continuity(node_element)
        if my_node_description == "_continuity":
            id_node_continuity = True

        return id_node_continuity

    def EM_extract_continuity(self, node_element):
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
            nodedescription = ''
        return nodedescription, node_y_pos 
    
    # GESTIONE EDGES
    def get_edge_target(self, tree, node_element):
        alledges = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}edge')
        id_node = self.getnode_id(node_element)
        EM_us_target = "" 
        node_y_pos = 0.0
        
        for edge in alledges:
            id_node_edge_source = self.getnode_edge_source(edge) 
            if id_node_edge_source == id_node:
                my_continuity_node_description, node_y_pos = self.EM_extract_continuity(node_element)
                id_node_edge_target = self.getnode_edge_target(edge)
                EM_us_target = self.find_node_us_by_id(id_node_edge_target)
                #print("edge with id: "+ self.getnode_id(edge)+" with target US_node "+ id_node_edge_target+" which is the US "+ EM_us_target)
        #print("edge with id: "+ self.getnode_id(edge)+" with target US_node "+ id_node_edge_target+" which is the US "+ EM_us_target)
        return EM_us_target, node_y_pos

    # SEMPLICI FUNZIONI PER ESTRARRE DATI PUNTUALI
    def getnode_id(self, node_element):
        id_node = str(node_element.attrib['id'])
        return id_node

    def getnode_edge_target(self, node_element):
        id_node_edge_target = str(node_element.attrib['target'])
        return id_node_edge_target

    def getnode_edge_source(self, node_element):
        id_node_edge_source = str(node_element.attrib['source'])
        return id_node_edge_source

    def find_node_us_by_id(self, id_node):
        us_node = ""
        for us in bpy.context.scene.em_list:
            if id_node == us.id_node:
                us_node = us.name
        return us_node

    def check_if_empty(self, name):
        if name == None:
            name = ""
        return name

    # FUNZIONE PER ELIMINARE COMMENTI NELLE DESCRIZIONI DEI NODI (laddove ci siano)
    def clean_comments(self, multiline_str):
        newstring = ""
        for line in multiline_str.splitlines():
            if line.startswith("«") or line.startswith("#"):
                pass
            else:
                newstring = newstring+line+" "
        return newstring    
    
    def check_index_coherence(self, scene):
        try:
            node_send = scene.em_list[scene.em_list_index]
        except IndexError as error:
            scene.em_list_index = 0
            node_send = scene.em_list[scene.em_list_index]

    def post_import_material_setup(self, context):
        if context.scene.proxy_display_mode == "EM":
            bpy.ops.emset.emmaterial()
        else:
            bpy.ops.emset.epochmaterial()

    def newnames_forproperties_from_fathernodes(self, scene):
        poly_property_counter = 1
        for property in scene.em_properties_list:
            node_list = []

            for edge in scene.edges_list:
                if edge.target == property.id_node:
                    for node in scene.em_list:
                        if edge.source == node.id_node:
                            node_list.append(node.name)
                            break # Interrompe il ciclo una volta trovata la corrispondenza
            #una volta fatto un pass generale è il momento di cambiare la label alla property
            if len(node_list) == 1:
                property.name = node_list[0] + "." + property.name
            elif len(node_list) > 1:
                property.name = "poly"+ str(poly_property_counter)+"." + property.name
                poly_property_counter +=1


#SETUP MENU
#####################################################################

classes = [
    EM_listitem_OT_to3D,
    EM_update_icon_list,
    EM_select_from_list_item,
    EM_import_GraphML,
    EM_select_list_item,
    EM_not_in_matrix
    ]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
