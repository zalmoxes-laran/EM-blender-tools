# landscape_system/populate_functions.py
"""
Funzioni per popolare le liste in modalità Landscape
Modifica le liste esistenti invece di duplicarle
"""

import bpy
from ..functions import check_objs_in_scene_and_provide_icon_for_list_element
from ..populate_lists import (
    get_connected_epoch_for_node, 
    populate_stratigraphic_node, 
    populate_document_node,
    populate_property_node,
    populate_extractor_node,
    populate_combiner_node,
    populate_epoch_node
)

def populate_lists_landscape_mode(context):
    """
    Popola tutte le liste in modalità Landscape con elementi da tutti i grafi
    """
    scene = context.scene
    
    # Verifica che siamo in modalità Landscape
    if not getattr(scene, 'landscape_mode_active', False):
        return
    
    print("🌍 Populating lists in Landscape mode...")
    
    # Ottieni tutti i grafi caricati
    all_graphs = get_all_loaded_graphs(context)
    if not all_graphs:
        print("❌ No graphs loaded for Landscape mode")
        return
    
    # Pulisci tutte le liste esistenti
    clear_all_lists(context)
    
    # Popola ogni lista con elementi da tutti i grafi
    populate_stratigraphy_list_landscape(context, all_graphs)
    populate_properties_list_landscape(context, all_graphs)
    populate_documents_list_landscape(context, all_graphs)
    populate_extractors_list_landscape(context, all_graphs)
    populate_combiners_list_landscape(context, all_graphs)
    populate_epochs_list_landscape(context, all_graphs)
    
    print(f"✅ Landscape mode: populated lists from {len(all_graphs)} graphs")

def get_all_loaded_graphs(context):
    """Ottiene tutti i grafi effettivamente caricati nel sistema"""
    scene = context.scene
    loaded_graphs = {}
    
    if not hasattr(scene, 'em_tools'):
        return loaded_graphs
    
    # Itera sui file GraphML registrati
    for graph_file in scene.em_tools.graphml_files:
        try:
            from ..s3Dgraphy import get_graph
            graph = get_graph(graph_file.name)
            
            if graph and hasattr(graph, 'nodes') and len(graph.nodes) > 0:
                graph_code = graph.attributes.get('graph_code', 'UNKNOWN')
                loaded_graphs[graph_code] = graph
                
        except Exception as e:
            print(f"❌ Error loading graph {graph_file.name}: {e}")
    
    return loaded_graphs

def clear_all_lists(context):
    """Pulisce tutte le liste principali"""
    scene = context.scene
    
    lists_to_clear = [
        'em_list',
        'em_properties_list', 
        'em_sources_list',
        'em_extractors_list',
        'em_combiners_list',
        'epoch_list',
        'em_reused'
    ]
    
    for list_name in lists_to_clear:
        if hasattr(scene, list_name):
            list_obj = getattr(scene, list_name)
            list_obj.clear()

def populate_stratigraphy_list_landscape(context, all_graphs):
    """Popola la lista unità stratigrafiche con elementi da tutti i grafi"""
    scene = context.scene
    
    for graph_code, graph in all_graphs.items():
        # Trova tutti i nodi stratigrafici
        stratigraphic_nodes = [
            node for node in graph.nodes 
            if hasattr(node, 'node_type') and 
            node.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs']
        ]
        
        for node in stratigraphic_nodes:
            item = scene.em_list.add()
            
            # Nome con prefisso grafo per Landscape
            item.name = f"[{graph_code}] {node.name}"
            
            # Icona basata sul nome originale (senza prefisso)
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
            
            # Altri attributi
            item.id_node = node.node_id
            item.description = getattr(node, 'description', '')
            item.node_type = getattr(node, 'node_type', 'US')
            
            # URL se disponibile
            if hasattr(node, 'source') and node.source:
                item.url = node.source
                item.icon_url = "CHECKBOX_HLT"
            else:
                item.url = ""
                item.icon_url = "CHECKBOX_DEHLT"
            
            # Epoca collegata
            connected_epoch = get_connected_epoch_for_node(graph, node)
            if connected_epoch:
                item.epoch = f"[{graph_code}] {connected_epoch}"
            else:
                item.epoch = ""

def populate_properties_list_landscape(context, all_graphs):
    """Popola la lista proprietà con elementi da tutti i grafi"""
    scene = context.scene
    
    for graph_code, graph in all_graphs.items():
        # Trova tutti i nodi proprietà
        property_nodes = [
            node for node in graph.nodes 
            if hasattr(node, 'node_type') and node.node_type == 'property'
        ]
        
        for node in property_nodes:
            item = scene.em_properties_list.add()
            
            # Nome con prefisso grafo
            item.name = f"[{graph_code}] {node.name}"
            
            # Icona basata sul nome originale
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
            
            # Altri attributi
            item.id_node = node.node_id
            item.description = getattr(node, 'description', '')
            
            # Valore della proprietà
            if hasattr(node, 'value'):
                item.url = str(node.value)
                item.icon_url = "CHECKBOX_HLT"
            else:
                item.url = ""
                item.icon_url = "CHECKBOX_DEHLT"

def populate_documents_list_landscape(context, all_graphs):
    """Popola la lista documenti con elementi da tutti i grafi"""
    scene = context.scene
    
    for graph_code, graph in all_graphs.items():
        # Trova tutti i nodi documento
        document_nodes = [
            node for node in graph.nodes 
            if hasattr(node, 'node_type') and node.node_type == 'document'
        ]
        
        for node in document_nodes:
            item = scene.em_sources_list.add()
            
            # Nome con prefisso grafo
            item.name = f"[{graph_code}] {node.name}"
            
            # Icona basata sul nome originale
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
            
            # Altri attributi
            item.id_node = node.node_id
            item.description = getattr(node, 'description', '')
            
            # URL del documento
            if hasattr(node, 'url') and node.url:
                item.url = node.url
                item.icon_url = "CHECKBOX_HLT"
            else:
                item.url = ""
                item.icon_url = "CHECKBOX_DEHLT"

def populate_extractors_list_landscape(context, all_graphs):
    """Popola la lista estrattori con elementi da tutti i grafi"""
    scene = context.scene
    
    for graph_code, graph in all_graphs.items():
        # Trova tutti i nodi estrattore
        extractor_nodes = [
            node for node in graph.nodes 
            if hasattr(node, 'node_type') and node.node_type == 'extractor'
        ]
        
        for node in extractor_nodes:
            item = scene.em_extractors_list.add()
            
            # Nome con prefisso grafo
            item.name = f"[{graph_code}] {node.name}"
            
            # Icona basata sul nome originale
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
            
            # Altri attributi
            item.id_node = node.node_id
            item.description = getattr(node, 'description', '')
            
            # URL dell'estrattore
            if hasattr(node, 'source') and node.source:
                item.url = node.source
                item.icon_url = "CHECKBOX_HLT"
            else:
                item.url = ""
                item.icon_url = "CHECKBOX_DEHLT"

def populate_combiners_list_landscape(context, all_graphs):
    """Popola la lista combinatori con elementi da tutti i grafi"""
    scene = context.scene
    
    for graph_code, graph in all_graphs.items():
        # Trova tutti i nodi combinatore
        combiner_nodes = [
            node for node in graph.nodes 
            if hasattr(node, 'node_type') and node.node_type == 'combiner'
        ]
        
        for node in combiner_nodes:
            item = scene.em_combiners_list.add()
            
            # Nome con prefisso grafo
            item.name = f"[{graph_code}] {node.name}"
            
            # Icona basata sul nome originale
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
            
            # Altri attributi
            item.id_node = node.node_id
            item.description = getattr(node, 'description', '')
            
            # Sources del combinatore
            if hasattr(node, 'sources') and node.sources:
                item.url = node.sources[0] if node.sources else ""
                item.icon_url = "CHECKBOX_HLT" if node.sources else "CHECKBOX_DEHLT"
            else:
                item.url = ""
                item.icon_url = "CHECKBOX_DEHLT"

def populate_epochs_list_landscape(context, all_graphs):
    """Popola la lista epoche con elementi da tutti i grafi"""
    scene = context.scene
    
    for graph_code, graph in all_graphs.items():
        # Trova tutti i nodi epoca
        epoch_nodes = [
            node for node in graph.nodes 
            if hasattr(node, 'node_type') and node.node_type == 'epoch'
        ]
        
        for node in epoch_nodes:
            item = scene.epoch_list.add()
            
            # Nome con prefisso grafo
            item.name = f"[{graph_code}] {node.name}"
            
            # ID del nodo
            item.id = node.node_id
            
            # Attributi dell'epoca
            item.min_y = getattr(node, 'min_y', 0.0)
            item.max_y = getattr(node, 'max_y', 0.0)
            item.start_time = getattr(node, 'start_time', "")
            item.end_time = getattr(node, 'end_time', "")
            item.description = getattr(node, 'description', '')
            
            # Colori dell'epoca
            if hasattr(node, 'color'):
                item.epoch_color = node.color
                item.epoch_RGB_color = hex_to_rgb(node.color)
            else:
                item.epoch_color = "#FFFFFF"
                item.epoch_RGB_color = (1.0, 1.0, 1.0)

def hex_to_rgb(hex_color):
    """Converte un colore hex in RGB normalizzato per Blender"""
    if not hex_color or not hex_color.startswith('#'):
        return (1.0, 1.0, 1.0)  # Bianco di default
    
    try:
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)
    except:
        return (1.0, 1.0, 1.0)  # Bianco di default in caso di errore

def populate_lists_single_mode(context):
    """Popola le liste in modalità single graph (chiamata dalla modalità normale)"""
    scene = context.scene
    
    # Disattiva temporaneamente la modalità Landscape per usare la logica standard
    was_landscape = getattr(scene, 'landscape_mode_active', False)
    if was_landscape:
        scene.landscape_mode_active = False
    
    try:
        # Usa la logica esistente per popolare da un singolo grafo
        from ..populate_lists import populate_blender_lists_from_graph, clear_lists
        from ..s3Dgraphy import get_active_graph
        
        # Pulisci le liste
        clear_lists(context)
        
        # Popola dal grafo attivo
        active_graph = get_active_graph()
        if active_graph:
            populate_blender_lists_from_graph(context, active_graph)
            print(f"✅ Single mode: populated from graph {active_graph.attributes.get('graph_code', 'UNKNOWN')}")
        else:
            print("❌ No active graph found for single mode")
            
    finally:
        # Ripristina lo stato Landscape se era attivo
        if was_landscape:
            scene.landscape_mode_active = True