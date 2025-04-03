import bpy # type: ignore
from ..s3Dgraphy import load_graph, get_graph
from ..s3Dgraphy import remove_graph
from ..s3Dgraphy.nodes.group_node import GroupNode

from ..populate_lists import *
from ..functions import *
from ..functions import normalize_path, show_popup_message


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

        if self.graphml_index >= 0 and em_tools.graphml_files[self.graphml_index]:
            # Ottieni il file GraphML selezionato
            graphml = em_tools.graphml_files[self.graphml_index]

            # Verifica che il campo path sia valorizzato
            if not graphml.graphml_path:
                error_msg = "GraphML path is not specified."
                self.report({'ERROR'}, error_msg)
                show_popup_message(context, "Path Error", error_msg, 'ERROR')
                return {'CANCELLED'}

            print(f"Il file GraphML da caricare è {graphml.graphml_path}")
            # Usa normalize_path invece di bpy.path.abspath
            graphml_file = normalize_path(graphml.graphml_path)
            
            # Verifica che il file esista
            if not os.path.exists(graphml_file):
                error_msg = f"GraphML file not found: {graphml_file}"
                self.report({'ERROR'}, error_msg)
                show_popup_message(context, "File Error", error_msg, 'ERROR')
                return {'CANCELLED'}

            # Recupera gli altri percorsi (DosCo, XLSX, EMdb) e normalizzali
            dosco_dir = normalize_path(graphml.dosco_dir) if graphml.dosco_dir else ""
            xlsx_filepath = normalize_path(graphml.xlsx_filepath) if graphml.xlsx_filepath else ""
            emdb_filepath = normalize_path(graphml.emdb_filepath) if graphml.emdb_filepath else ""

            # Clear Blender Lists
            clear_lists(context)

            try:
                # Carica il grafo - l'ID verrà estratto dal file
                graph_id = load_graph(graphml_file, overwrite=True)
                print(f"Graph loaded successfully with ID: {graph_id}")
                
                # Ora ottieni il grafo utilizzando l'ID restituito
                graph_instance = get_graph(graph_id)

                if graph_instance is None:
                    error_msg = "Errore: il grafo non è stato caricato correttamente."
                    self.report({'ERROR'}, error_msg)
                    show_popup_message(context, "Graph Error", error_msg, 'ERROR')
                    return {'CANCELLED'}

                # Aggiorna il nome nella UI con l'ID effettivo del grafo
                graphml.name = graph_instance.graph_id
                
                # Aggiorna anche il codice del grafo se disponibile
                if 'graph_code' in graph_instance.attributes:
                    graphml.graph_code = graph_instance.attributes['graph_code']
                
                print(f"Updated display name to graph ID: {graph_instance.graph_id}")
                print(f"Graph code: {graphml.graph_code if hasattr(graphml, 'graph_code') else 'Not available'}")

                # Now populate the Blender lists from the graph
                populate_blender_lists_from_graph(context, graph_instance)

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


            except Exception as e:
                error_msg = f"Error loading graph: {e}"
                print(error_msg)
                self.report({'ERROR'}, str(e))
                show_popup_message(context, "Graph Loading Error", str(e), 'ERROR')
                return {'CANCELLED'}

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
    
classes = [
    EM_import_GraphML
    ]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
