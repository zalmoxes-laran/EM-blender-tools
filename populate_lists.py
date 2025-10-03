# populate_lists.py
# VERSIONE REFACTORED - Rimossi prefissi manuali, delegati alle funzioni helper

import bpy # type: ignore

from .functions import *
#from .epoch_manager import *

#from s3dgraphy import *
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode  # Import diretto
from s3dgraphy.nodes.document_node import DocumentNode  # Import diretto
from s3dgraphy.nodes.property_node import PropertyNode  # Import diretto
from s3dgraphy.nodes.extractor_node import ExtractorNode  # Import diretto
from s3dgraphy.nodes.combiner_node import CombinerNode  # Import diretto
from s3dgraphy.nodes.epoch_node import EpochNode  # Import diretto

def clean_value_for_ui(value):
    """Clean any value to be safe for Blender UI (always returns string)."""
    import pandas as pd
    
    if value is None or pd.isna(value):
        return ""
    
    # Convert to string and clean
    str_value = str(value).strip()
    
    # Handle specific bad values
    if str_value.lower() in ['nan', 'null', 'none']:
        return ""
        
    return str_value

def get_connected_epoch_for_node(graph, node):
    """
    Trova l'epoca collegata a un nodo.
    """
    # Accedi all'ID originale tramite gli attributi
    node_id_to_check = node.attributes.get('original_id', node.node_id)
    
    for edge in graph.edges:
        # Controlla prima gli attributi per l'ID originale della sorgente
        edge_source = edge.attributes.get('original_source_id', edge.edge_source)
        
        if edge_source == node_id_to_check and edge.edge_type in ['has_first_epoch', 'survive_in_epoch']:
            target_node = graph.find_node_by_id(edge.edge_target)
            if target_node and hasattr(target_node, 'node_type') and target_node.node_type == 'epoch':
                return target_node.name
    return None

def hex_to_rgb(value):
    """Convert hex color to RGB with gamma correction"""
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
    return tuple(fin)

def populate_blender_lists_from_graph(context, graph):
    """
    Popola le liste di Blender con i dati dal grafo.
    Delega alla funzione specifica in base alla modalità.
    """
    # Check if in 3D GIS mode or Advanced EM mode
    scene = context.scene
    em_settings = bpy.context.window_manager.em_addon_settings if hasattr(bpy.context.window_manager, 'em_addon_settings') else None
    
    if em_settings and hasattr(em_settings, 'em_mode_selection'):
        if em_settings.em_mode_selection == 'OP3':  # 3D GIS mode
            # Use 3D GIS specific population logic
            print("Populating lists in 3D GIS mode")
            # TODO: implement 3D GIS specific population if different
            populate_lists_for_advanced_em(context, graph)
        else:  # Advanced EM modes
            populate_lists_for_advanced_em(context, graph)
    else:
        # Default to Advanced EM
        populate_lists_for_advanced_em(context, graph)

def populate_lists_for_advanced_em(context, graph):
    """
    Popola le liste per Advanced EM.
    
    ✅ MODIFICATO: Ora passa il parametro graph a tutte le funzioni populate_*
    
    Args:
        context: Il contesto Blender
        graph: L'istanza del grafo
    """
    scene = context.scene
    
    # Memorizza il codice del grafo per riferimenti futuri
    graph_code = graph.attributes.get('graph_code')

    # Inizializza gli indici delle liste
    em_list_index_ema = 0
    em_sources_index_ema = 0
    em_properties_index_ema = 0
    em_extractors_index_ema = 0
    em_combiners_index_ema = 0
    em_edges_index_ema = 0
    em_epoch_list_ema = 0
    em_reused_index_ema = 0
    
    # Classifica i nodi per tipo
    stratigraphic_nodes = []
    document_nodes = []
    property_nodes = []
    extractor_nodes = []
    combiner_nodes = []
    epoch_nodes = []
    
    for node in graph.nodes:
        if hasattr(node, 'node_type'):
            if node.node_type in ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs']:
                stratigraphic_nodes.append(node)
            elif node.node_type == "document":
                document_nodes.append(node)
            elif node.node_type == "property":
                property_nodes.append(node)
            elif node.node_type == "extractor":
                extractor_nodes.append(node)
            elif node.node_type == "combiner":
                combiner_nodes.append(node)
            elif node.node_type == "epoch":
                epoch_nodes.append(node)
    
    # Popola le liste con i nodi classificati
    
    # 1. Nodi stratigrafici
    for node in stratigraphic_nodes:
        if isinstance(node, StratigraphicNode):
            em_list_index_ema = populate_stratigraphic_node(scene, node, em_list_index_ema, graph)
            em_reused_index_ema = populate_reuse_US_table(scene, node, em_reused_index_ema, graph)
    
    # ✅ MODIFICATO: passa il graph a tutte le funzioni
    # 2. Nodi documento
    for node in document_nodes:
        em_sources_index_ema = populate_document_node(scene, node, em_sources_index_ema, graph)
    
    # 3. Nodi proprietà
    for node in property_nodes:
        em_properties_index_ema = populate_property_node(scene, node, em_properties_index_ema, graph)
    
    # 4. Nodi estrattore
    for node in extractor_nodes:
        em_extractors_index_ema = populate_extractor_node(scene, node, em_extractors_index_ema, graph)
    
    # 5. Nodi combinatore
    for node in combiner_nodes:
        em_combiners_index_ema = populate_combiner_node(scene, node, em_combiners_index_ema, graph)
    
    # 6. Nodi epoca
    for node in epoch_nodes:
        em_epoch_list_ema = populate_epoch_node(scene, node, em_epoch_list_ema, graph)
    
    # 7. Archi
    for edge in graph.edges:
        populate_edges(scene, edge, em_edges_index_ema)
        em_edges_index_ema += 1

def populate_reuse_US_table(scene, node, index, graph):
    """
    Popola la tabella dei riusi per un nodo.
    Già corretto - usa nomi puliti.
    """
    survived_in_epoch = graph.get_connected_epoch_nodes_list_by_edge_type(node, "survive_in_epoch")
    
    if survived_in_epoch:
        for current_epoch in survived_in_epoch:
            scene.em_reused.add()
            em_item = scene.em_reused[-1]
            em_item.epoch = current_epoch.name
            em_item.em_element = node.name  # ✅ Nome pulito
            index += 1
            
    return index

def populate_stratigraphic_node(scene, node, index, graph):
    """
    Popola la lista di unità stratigrafiche.
    
    ✅ MODIFICATO: Ora usa SEMPRE il nome pulito del nodo, senza prefisso.
                  Passa il grafo a check_objs_in_scene_and_provide_icon_for_list_element.
    """
    scene.em_list.add()
    em_item = scene.em_list[-1]
    
    # ✅ USA SEMPRE IL NOME PULITO (senza prefisso)
    em_item.name = node.name
    
    em_item.description = node.description
    em_item.shape = node.attributes.get('shape', "")
    em_item.y_pos = node.attributes.get('y_pos', 0.0)
    em_item.fill_color = node.attributes.get('fill_color', "")
    em_item.border_style = node.attributes.get('border_style', "")
    
    # ✅ MODIFICATO: passa anche il grafo per gestire il prefisso
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name, graph=graph)
    
    em_item.id_node = node.node_id
    em_item.node_type = node.node_type

    # ✅ MODIFICATO: usa la funzione helper per trovare il proxy
    from .operators.addon_prefix_helpers import get_proxy_from_node
    obj = get_proxy_from_node(node, graph=graph)
    if obj:
        em_item.is_visible = not obj.hide_viewport
    else:
        em_item.is_visible = True
    
    first_epoch = graph.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")
    if not first_epoch: 
        graph.print_node_connections(node)
    em_item.epoch = first_epoch.name if first_epoch else ""
    
    return index + 1

def populate_document_node(scene, node, index, graph=None):
    """
    Popola la lista dei documenti.
    
    ✅ MODIFICATO: Ora usa SEMPRE il nome pulito del nodo, senza prefisso.
    
    Args:
        scene: Blender scene
        node: Document node
        index: Current index
        graph: Graph instance (optional, for icon check)
    """
    source_already_in_list = False
    for source_item in scene.em_sources_list:
        if source_item.id_node == node.node_id:
            source_already_in_list = True
            break

    if not source_already_in_list:
        scene.em_sources_list.add()
        em_item = scene.em_sources_list[-1]
        
        # ✅ USA SEMPRE IL NOME PULITO (rimosso il blocco che aggiungeva il prefisso)
        em_item.name = node.name
        
        # ✅ MODIFICATO: passa il grafo per gestire il prefisso nella ricerca icona
        em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name, graph=graph)
        em_item.id_node = node.node_id
        em_item.url = clean_value_for_ui(getattr(node, 'url', ''))
        em_item.icon_url = "CHECKBOX_HLT" if node.url else "CHECKBOX_DEHLT"
        em_item.description = node.description
        index += 1

    return index

def populate_property_node(scene, node, index, graph=None):
    """
    Popola la lista delle proprietà.
    
    ✅ MODIFICATO: Aggiunto supporto per graph parameter.
    
    Args:
        scene: Blender scene
        node: Property node
        index: Current index
        graph: Graph instance (optional, for icon check)
    """
    scene.em_properties_list.add()
    em_item = scene.em_properties_list[-1]
    
    # ✅ GIÀ CORRETTO: usa il nome pulito
    if hasattr(node, 'attributes') and 'original_name' in node.attributes:
        em_item.name = node.attributes['original_name']
    else:
        em_item.name = node.name
    
    # ✅ MODIFICATO: passa il grafo
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name, graph=graph)
    em_item.id_node = node.node_id
    em_item.url = clean_value_for_ui(getattr(node, 'value', ''))
    em_item.icon_url = "CHECKBOX_HLT" if em_item.url else "CHECKBOX_DEHLT"
    em_item.description = node.description
    return index + 1

def populate_extractor_node(scene, node, index, graph=None):
    """
    Popola la lista degli estrattori.
    
    ✅ MODIFICATO: Ora usa SEMPRE il nome pulito del nodo, senza prefisso.
    
    Args:
        scene: Blender scene
        node: Extractor node
        index: Current index
        graph: Graph instance (optional, for icon check)
    """
    scene.em_extractors_list.add()
    em_item = scene.em_extractors_list[-1]
    
    # ✅ USA SEMPRE IL NOME PULITO (rimosso il blocco che aggiungeva il prefisso)
    em_item.name = node.name
    
    # ✅ MODIFICATO: passa il grafo
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name, graph=graph)
    em_item.id_node = node.node_id
    em_item.url = clean_value_for_ui(getattr(node, 'source', ''))
    em_item.icon_url = "CHECKBOX_HLT" if node.source else "CHECKBOX_DEHLT"
    em_item.description = node.description
    return index + 1

def populate_combiner_node(scene, node, index, graph=None):
    """
    Popola la lista dei combinatori.
    
    ✅ MODIFICATO: Aggiunto supporto per graph parameter.
    
    Args:
        scene: Blender scene
        node: Combiner node
        index: Current index
        graph: Graph instance (optional, for icon check)
    """
    scene.em_combiners_list.add()
    em_item = scene.em_combiners_list[-1]
    
    # ✅ GIÀ CORRETTO: usa il nome pulito
    em_item.name = node.name
    
    # ✅ MODIFICATO: passa il grafo
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name, graph=graph)
    em_item.id_node = node.node_id
    raw_url = node.sources[0] if node.sources else ""
    em_item.url = clean_value_for_ui(raw_url)
    em_item.icon_url = "CHECKBOX_HLT" if node.sources else "CHECKBOX_DEHLT"
    em_item.description = node.description
    return index + 1

def populate_epoch_node(scene, node, index, graph=None):
    """
    Popola la lista delle epoche.
    
    ✅ GIÀ CORRETTO: usa il nome pulito, nessuna modifica necessaria.
    """
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
    epoch_item.description = node.description
    return index + 1

def populate_edges(scene, edge, index):
    """
    Popola la lista degli archi.
    Nessuna modifica necessaria.
    """
    scene.edges_list.add()
    edge_item = scene.edges_list[index]
    edge_item.id_node = edge.edge_id
    edge_item.source = edge.edge_source
    edge_item.target = edge.edge_target
    edge_item.edge_type = edge.edge_type
    return index + 1

def clear_lists(context):
    """
    Pulisce tutte le liste in Blender.
    Nessuna modifica necessaria.
    """
    # Clear existing lists in Blender
    EM_list_clear(context, "em_list")
    EM_list_clear(context, "em_reused")
    EM_list_clear(context, "em_sources_list")
    EM_list_clear(context, "em_properties_list")
    EM_list_clear(context, "em_extractors_list")
    EM_list_clear(context, "em_combiners_list")
    EM_list_clear(context, "edges_list")
    EM_list_clear(context, "epoch_list")
    
    return None