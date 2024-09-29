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

from .S3Dgraphy import *
from .S3Dgraphy.node import StratigraphicNode  # Import diretto

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

        #clear Blender Lists
        self._clear_lists(context)

        #retrieve graphml_path
        graphml_file = bpy.path.abspath(scene.EM_file)

        # Crea un'istanza dell'importatore
        importer = GraphMLImporter(graphml_file)

        # Esegui il parsing e ottieni il grafo
        graph = importer.parse()

        # Now populate the Blender lists from the graph
        self.populate_blender_lists_from_graph(context, graph)

        for reused in scene.em_reused:
            print(f"Reused {reused.em_element} in {reused.epoch}")

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

        # Inizializza gli indici delle liste
        em_list_index_ema = 0
        em_sources_index_ema = 0
        em_properties_index_ema = 0
        em_extractors_index_ema = 0
        em_combiners_index_ema = 0
        em_edges_index_ema = 0
        em_epoch_list_ema = 0
        em_reused_index_ema = 0

        # Popolamento delle liste
        for node in graph.nodes:
            if isinstance(node, StratigraphicNode):
                self._populate_stratigraphic_node(scene, node, em_list_index_ema, graph)
                em_list_index_ema += 1
                em_reused_index_ema = self._populate_reuse_US_table(scene, node, em_reused_index_ema, graph)
            elif isinstance(node, DocumentNode):
                em_sources_index_ema = self._populate_document_node(scene, node, em_sources_index_ema)
                em_sources_index_ema +=1
            elif isinstance(node, PropertyNode):
                em_properties_index_ema = self._populate_property_node(scene, node, em_properties_index_ema)
                em_properties_index_ema +=1
            elif isinstance(node, ExtractorNode):
                em_extractors_index_ema = self._populate_extractor_node(scene, node, em_extractors_index_ema)
                em_extractors_index_ema +=1
            elif isinstance(node, CombinerNode):
                em_combiners_index_ema = self._populate_combiner_node(scene, node, em_combiners_index_ema)
                em_combiners_index_ema +=1
            elif isinstance(node, EpochNode):
                em_epoch_list_ema = self._populate_epoch_node(scene, node, em_epoch_list_ema)
        for edge in graph.edges:
            self._populate_edges(scene, edge, em_edges_index_ema)

    def _populate_reuse_US_table(self, scene, node, index, graph):
        survived_in_epoch = graph.get_connected_epoch_node_by_edge_type(node, "survive_in_epoch")
        #print(f"Per il nodo {node.name}:")
        graph.print_connected_epoch_nodes_and_edge_types(node)

        if survived_in_epoch:
            scene.em_reused.add()
            em_item = scene.em_reused[-1]
            em_item.epoch = survived_in_epoch.name
            em_item.em_element = node.name
            return index +1
        return index

    def _populate_stratigraphic_node(self, scene, node, index, graph):
        scene.em_list.add()
        em_item = scene.em_list[-1]
        em_item.name = node.name
        em_item.description = node.description
        em_item.shape = node.attributes.get('shape', "")
        em_item.y_pos = node.attributes.get('y_pos', 0.0)
        em_item.fill_color = node.attributes.get('fill_color', "")
        em_item.border_style = node.attributes.get('border_style', "")
        em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
        em_item.id_node = node.node_id
        
        #em_item.epoch = node.epoch if node.epoch else ""
        #graph.print_connected_epoch_nodes_and_edge_types(node)
        first_epoch = graph.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")

        em_item.epoch = first_epoch.name if first_epoch else ""

        #print("Ho registrato l'epoca "+em_item.epoch+" per il nodo"+em_item.name)
        #em_item.epoch = graph.get_epochs_list_for_stratigraphicnode(node.node_id)
        
        return index + 1

    def _populate_document_node(self, scene, node, index):
        source_already_in_list = False
        for source_item in scene.em_sources_list:
            if source_item.name == node.name:
                source_already_in_list = True
                break

        if not source_already_in_list:
            scene.em_sources_list.add()
            em_item = scene.em_sources_list[-1]
            em_item.name = node.name
            em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
            em_item.id_node = node.node_id
            em_item.url = node.url if node.url is not None else ""
            em_item.icon_url = "CHECKBOX_HLT" if node.url else "CHECKBOX_DEHLT"
            em_item.description = node.description
            index += 1

        return index
    
    def _populate_property_node(self, scene, node, index):
        scene.em_properties_list.add()
        em_item = scene.em_properties_list[-1]
        em_item.name = node.name
        em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
        em_item.id_node = node.node_id
        em_item.url = node.value if node.value is not None else ""
        em_item.icon_url = "CHECKBOX_HLT" if node.value else "CHECKBOX_DEHLT"
        em_item.description = node.description
        return index + 1

    def _populate_extractor_node(self, scene, node, index):
        scene.em_extractors_list.add()
        em_item = scene.em_extractors_list[-1]
        em_item.name = node.name
        em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
        em_item.id_node = node.node_id
        em_item.url = node.source if node.source is not None else ""
        em_item.icon_url = "CHECKBOX_HLT" if node.source else "CHECKBOX_DEHLT"
        em_item.description = node.description
        return index + 1

    def _populate_combiner_node(self, scene, node, index):
        scene.em_combiners_list.add()
        em_item = scene.em_combiners_list[-1]
        em_item.name = node.name
        em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
        em_item.id_node = node.node_id
        em_item.url = node.sources[0] if node.sources else ""
        em_item.icon_url = "CHECKBOX_HLT" if node.sources else "CHECKBOX_DEHLT"
        em_item.description = node.description
        return index + 1

    def _populate_epoch_node(self, scene, node, index):
        scene.epoch_list.add()
        epoch_item = scene.epoch_list[-1]
        epoch_item.name = node.name
        epoch_item.id = node.node_id
        epoch_item.min_y = node.min_y
        epoch_item.max_y = node.max_y
        epoch_item.start_time = node.start_time
        epoch_item.end_time = node.end_time
        epoch_item.epoch_color = node.color
        epoch_item.epoch_RGB_color = hex_to_rgb(node.color)
        #print("il colore è:" +epoch_item.epoch_color)

        epoch_item.description = node.description
        return index + 1

    def _populate_edges(self, scene, edge, index):
        scene.edges_list.add()
        edge_item = scene.edges_list[index]
        edge_item.id_node = edge.edge_id
        edge_item.source = edge.edge_source
        edge_item.target = edge.edge_target
        edge_item.edge_type = edge.edge_type
        return index + 1

    def _clear_lists(self, context):
        # Clear existing lists in Blender
        EM_list_clear(context, "em_list")
        EM_list_clear(context, "em_reused")
        EM_list_clear(context, "em_sources_list")
        EM_list_clear(context, "em_properties_list")
        EM_list_clear(context, "em_extractors_list")
        EM_list_clear(context, "em_combiners_list")
        EM_list_clear(context, "edges_list")
        EM_list_clear(context, "epoch_list")
        
        #context.scene.em_list_index_ema = 0

        return None

    '''
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
    '''

    def find_node_element_by_id(self, context, node_id):
        tree = ET.parse(bpy.path.abspath(context.scene.EM_file))
        allnodes = tree.findall('.//{http://graphml.graphdrawing.org/xmlns}node')
        
        for node_element in allnodes:
            if node_element.attrib['id'] == node_id:
                return node_element
        return None

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

    def find_node_us_by_id(self, id_node):
        us_node = ""
        for us in bpy.context.scene.em_list:
            if id_node == us.id_node:
                us_node = us.name
        return us_node

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
