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

from .S3Dgraphy import load_graph, get_graph

from .populate_lists import *

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
    bl_label = "Import EM (GraphML)"
    bl_description = "Load/reload this EM from disk and set it active"
    bl_options = {"REGISTER", "UNDO"}

    # Aggiungiamo una proprietà per passare l'indice del file GraphML selezionato
    graphml_index: bpy.props.IntProperty() # type: ignore

    def execute(self, context):
        # Setup scene variable

        scene = context.scene
        em_tools = scene.em_tools

        # Recupera il file GraphML selezionato tramite l'indice
        #if self.graphml_index >= 0 and self.graphml_index < len(em_tools):
        #    graphml = em_tools.graphml_files[self.graphml_index]

        if self.graphml_index >= 0 and em_tools.graphml_files[self.graphml_index]:
            # Ottieni il file GraphML selezionato
            graphml = em_tools.graphml_files[self.graphml_index]



            # Verifica che il campo path sia valorizzato
            if not graphml.graphml_path:
                self.report({'ERROR'}, "GraphML path is not specified.")
                return {'CANCELLED'}

            print(f"Il file GraphML da caricare è {graphml.graphml_path}")
            graphml_file = bpy.path.abspath(graphml.graphml_path)

            # Define a unique graph_id, e.g., based on the file name
            graph_id = os.path.splitext(os.path.basename(graphml_file))[0]
            graphml.name = graph_id

            # Recupera gli altri percorsi (DosCo, XLSX, EMdb)
            dosco_dir = graphml.dosco_dir
            xlsx_filepath = graphml.xlsx_filepath
            emdb_filepath = graphml.emdb_filepath


            # Clear Blender Lists
            clear_lists(context)

            # Rimuovi il grafo esistente se presente
            try:
                remove_graph(graph_id)
                print(f"Existing graph '{graph_id}' removed successfully.")
            except KeyError:
                print(f"No existing graph with ID '{graph_id}' found to remove.")

            try:
                # Carica il grafo con overwrite=True
                load_graph(graphml_file, graph_id=graph_id, overwrite=True)
                print(f"Graph '{graph_id}' loaded successfully.")
            except ValueError as e:
                print(f"Error loading graph: {e}")
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}

            # Ora ottieni il grafo utilizzando `get_graph(graph_id)`
            graph_instance = get_graph(graph_id)

            if graph_instance is None:
                self.report({'ERROR'}, "Errore: il grafo non è stato caricato correttamente.")
                return {'CANCELLED'}

            # Now populate the Blender lists from the graph
            populate_blender_lists_from_graph(context, graph_instance)

            #for reused in scene.em_reused:
            #    print(f"Reused {reused.em_element} in {reused.epoch}")

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

            bpy.ops.epoch_manager.update_us_list

            bpy.ops.activity.refresh_list(graphml_index=self.graphml_index)

            # After loading the graph
            #scene.em_graph = graph  # Replace 'loaded_graph' with your graph variable

            # Stampa tutti gli archi di tipo 'is_grouped_in'
            #\self.print_groups_and_contents(graph_instance)

        return {'FINISHED'}
            
    def print_groups_and_contents(self, graph):
        """
        Stampa tutti i gruppi nel grafo e i nodi contenuti in essi,
        elencando l'ID, il nome e la descrizione di ciascun nodo.
        """
        for node in graph.nodes:
            if isinstance(node, GroupNode):
                print(f"Gruppo ID: {node.node_id}, Nome: {node.name}, Descrizione: {node.description}")
                print("Nodi contenuti:")
                # Trova tutti gli archi di tipo 'is_grouped_in' con target su questo gruppo
                for edge in graph.edges:
                    if edge.edge_type == "is_grouped_in" and edge.edge_target == node.node_id:
                        # Ottieni il nodo sorgente (nodo contenuto nel gruppo)
                        contained_node = graph.find_node_by_id(edge.edge_source)
                        if contained_node:
                            print(f"  Nodo ID: {contained_node.node_id}, Nome: {contained_node.name}, Descrizione: {contained_node.description}")
                print("------")


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
