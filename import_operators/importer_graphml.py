import bpy # type: ignore
from s3dgraphy import get_graph
from s3dgraphy import remove_graph
from s3dgraphy.nodes.group_node import GroupNode

from ..populate_lists import *
from ..functions import *
from ..functions import normalize_path, show_popup_message
from s3dgraphy.multigraph.multigraph import load_graph_from_file


class EM_import_GraphML(bpy.types.Operator):
    bl_idname = "import.em_graphml"
    bl_label = "Import EM (GraphML)"
    bl_description = "(SHIFT+F5) Load/reload this EM from disk and set it active"
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
                # ✅ OPTIMIZATION: Add progress bar for better UX during long operations
                wm = context.window_manager
                wm.progress_begin(0, 100)

                # Step 1: Load graph from file (0-30%)
                wm.progress_update(0)
                final_graph_id = load_graph_from_file(graphml_file, overwrite=True)
                print(f"Graph loaded with final ID: {final_graph_id}")
                wm.progress_update(30)

                # Ottieni l'istanza del grafo
                graph_instance = get_graph(final_graph_id)

                if graph_instance:

                    # Step 2: Connect paradata groups (30-40%)
                    # Nuova funzionalità per collegare PropertyNode dai ParadataNodeGroup
                    # Questa chiamata crea collegamenti diretti tra unità stratigrafiche e PropertyNode
                    # quando sono collegati attraverso un ParadataNodeGroup
                    print("\nApplicazione della funzionalità di collegamento PropertyNode da ParadataNodeGroup...")
                    try:
                        stats = graph_instance.connect_paradatagroup_propertynode_to_stratigraphic(verbose=False)
                        if stats["connections_created"] > 0:
                            print(f"Creati {stats['connections_created']} nuovi collegamenti diretti tra unità stratigrafiche e PropertyNode")
                        else:
                            print("Nessun nuovo collegamento creato")
                    except Exception as e:
                        print(f"AVVISO: Errore durante il collegamento PropertyNode: {str(e)}")
                        # Non interrompiamo l'esecuzione per questo errore
                    wm.progress_update(40)

                    # Aggiorna UI e continua con il popolamento
                    graphml.name = final_graph_id
                    # Aggiorna anche il codice del grafo se disponibile
                    if 'graph_code' in graph_instance.attributes:
                        graphml.graph_code = graph_instance.attributes['graph_code']
                    elif hasattr(graphml, 'graph_code'):  # Assicuriamoci che la proprietà esista
                        graphml.graph_code = "site_id"  # Valore di fallback

                    # Propagate import warnings from s3dgraphy to Blender UI property
                    if hasattr(graph_instance, 'warnings') and graph_instance.warnings:
                        graphml.import_warnings = "\n".join(graph_instance.warnings)
                        print(f"\n⚠️  {len(graph_instance.warnings)} import warning(s) detected:")
                        for w in graph_instance.warnings:
                            print(f"  - {w}")
                    else:
                        graphml.import_warnings = ""
                else: 
                    error_msg = f"Grafo non trovato con ID: {final_graph_id}"
                    self.report({'ERROR'}, error_msg)
                    show_popup_message(context, "Graph Error", error_msg, 'ERROR')
                    return {'CANCELLED'}
                                
                
                
                print(f"Aggiornato ID nell'interfaccia a: {graphml.name}")
                # Imposta esplicitamente gli indici a 0 prima di popolare
                strat = scene.em_tools.stratigraphy  # ✅ Nuovo
                strat.units_index = 0  # ✅ Nuovo path

                em_tools.epochs.list_index = 0
                
                
                
                if hasattr(scene, "em_sources_list_index"):
                    scene.em_tools.em_sources_list_index = 0
                if hasattr(scene, "em_properties_list_index"):
                    scene.em_tools.em_properties_list_index = 0
                if hasattr(scene, "em_extractors_list_index"):
                    scene.em_tools.em_extractors_list_index = 0
                if hasattr(scene, "em_combiners_list_index"):
                    scene.em_tools.em_combiners_list_index = 0


                # Step 3: Integrate external data (40-50%)
                # Integrazione di dati esterni PRIMA di popolare le liste
                em_settings = bpy.context.window_manager.em_addon_settings
                if em_settings.overwrite_url_with_dosco_filepath:
                    inspect_load_dosco_files_on_graph(graph_instance, dosco_dir)  # ← Nuova funzione
                wm.progress_update(50)

                # Step 4: Auto-import auxiliary files (50-70%)
                # ✅ IMPORTANTE: Auto-import dei file ausiliari PRIMA di popolare le liste
                # In questo modo il grafo viene completamente popolato (incluso DosCo)
                # e poi le liste vengono popolate una volta sola con tutti i dati
                from ..em_setup import auto_import_auxiliary_files
                imported, errors = auto_import_auxiliary_files(context, self.graphml_index)
                wm.progress_update(70)

                # Step 5: Populate Blender lists (70-85%)
                # ✅ ORA procedi con il popolamento delle liste (grafo completamente popolato)
                if getattr(scene, 'landscape_mode_active', False):
                    from ..landscape_system.populate_functions import populate_lists_landscape_mode
                    populate_lists_landscape_mode(context)
                else:
                    populate_blender_lists_from_graph(context, graph_instance)
                wm.progress_update(85)

                # Step 6: Update graph statistics (85-90%)
                # ✅ Aggiorna le statistiche del grafo (conteggi nodi per UI)
                from ..populate_lists import update_graph_statistics
                update_graph_statistics(context, graph_instance, graphml)
                wm.progress_update(90)

                # ✅ Usa nuovi paths centralizzati
                strat = scene.em_tools.stratigraphy
                ensure_valid_index(strat.units, "units_index", context, data_object=strat)
                ensure_valid_index(em_tools.epochs.list, "list_index", context, show_popup=False, data_object=em_tools.epochs)
                ensure_valid_index(scene.em_tools.em_sources_list, "em_sources_list_index", context, data_object=em_tools)
                ensure_valid_index(scene.em_tools.em_properties_list, "em_properties_list_index", context, data_object=em_tools)
                ensure_valid_index(scene.em_tools.em_extractors_list, "em_extractors_list_index", context, data_object=em_tools)
                ensure_valid_index(scene.em_tools.em_combiners_list, "em_combiners_list_index", context, data_object=em_tools)

                # verifica post importazione
                self.check_index_coherence(scene)

                #per aggiornare i nomi delle proprietà usando come prefisso in nome del nodo padre
                #self.newnames_forproperties_from_fathernodes(scene)
                # ho disabilitato questa funzione perchè non mi sembra utile. Se serve, si può riabilitare

                # Step 7: Create derived lists (90-95%)
                #crea liste derivate per lo streaming dei paradati
                # ✅ Usa nuovo path
                if strat.units_index >= 0 and strat.units_index < len(strat.units):
                    create_derived_lists(strat.units[strat.units_index])
                wm.progress_update(95)

                # Step 8: Material setup and final operations (95-100%)
                #setup dei materiali di scena dopo l'importazione del graphml
                self.post_import_material_setup(context)

                bpy.ops.epoch_manager.update_us_list

                bpy.ops.activity.refresh_list(graphml_index=self.graphml_index)
                wm.progress_update(100)

                # ✅ End progress bar
                wm.progress_end()

                if imported > 0:
                    self.report({'INFO'}, f"GraphML loaded + {imported} auxiliary file(s) auto-imported")
                elif errors > 0:
                    self.report({'WARNING'}, f"GraphML loaded but {errors} auxiliary import(s) failed")


            except Exception as e:
                # ✅ Ensure progress bar is closed on error
                wm = context.window_manager
                wm.progress_end()

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
        tree = ET.parse(bpy.path.abspath(context.scene.em_tools.EM_file))
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
        strat = scene.em_tools.stratigraphy  # ✅ Nuovo
        # Se la lista è vuota, imposta indice a -1
        if len(strat.units) == 0:
            strat.units_index = -1
            return
        # Altrimenti verifica che l'indice sia valido
        try:
            node_send = strat.units[strat.units_index]
        except IndexError as error:
            strat.units_index = 0
            node_send = strat.units[strat.units_index]

    def post_import_material_setup(self, context):
        current_mode = context.scene.em_tools.proxy_display_mode
        
        if current_mode == "EM":
            bpy.ops.emset.emmaterial()
        elif current_mode == "Epochs":
            bpy.ops.emset.epochmaterial()
        elif current_mode == "Properties":
            # Mantieni Properties attivo dopo import
            if hasattr(context.scene, 'property_values') and context.scene.property_values:
                try:
                    bpy.ops.visual.apply_colors()
                except:
                    pass  # Fallback sicuro

    def newnames_forproperties_from_fathernodes(self, scene):
        poly_property_counter = 1
        strat = scene.em_tools.stratigraphy  # ✅ Nuovo
        for property in scene.em_tools.em_properties_list:
            node_list = []

            for edge in scene.em_tools.edges_list:
                if edge.target == property.id_node:
                    for node in strat.units:
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
        strat = bpy.context.scene.em_tools.stratigraphy  # ✅ Nuovo
        for us in strat.units:
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
