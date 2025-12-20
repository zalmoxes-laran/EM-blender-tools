"""
Population Functions for Blender Lists
======================================

✅ CLEAN VERSION - No dual-sync, single path only
All functions now populate ONLY scene.em_tools.stratigraphy.* paths

This module contains functions to populate Blender UI lists from s3dgraphy graph nodes.
"""

import bpy # type: ignore
from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode

from .functions import (
    check_objs_in_scene_and_provide_icon_for_list_element,
    clean_value_for_ui
)


def populate_stratigraphic_node(scene, node, index, graph):
    """
    Popola la lista di unità stratigrafiche.
    
    ✅ CLEAN VERSION: Popola SOLO scene.em_tools.stratigraphy.units
    ✅ USA SEMPRE il nome pulito del nodo, senza prefisso
    """
    strat = scene.em_tools.stratigraphy
    
    strat.units.add()
    em_item = strat.units[-1]
    
    # ✅ Nome pulito (senza prefisso grafo)
    em_item.name = node.name
    em_item.description = node.description
    em_item.shape = node.attributes.get('shape', "")
    em_item.y_pos = node.attributes.get('y_pos', 0.0)
    em_item.fill_color = node.attributes.get('fill_color', "")
    em_item.border_style = node.attributes.get('border_style', "")
    em_item.id_node = node.node_id
    em_item.node_type = node.node_type
    
    # Icon con supporto prefisso grafo
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name, graph=graph)
    
    # Visibility dal proxy object
    from .operators.addon_prefix_helpers import get_proxy_from_node
    obj = get_proxy_from_node(node, graph=graph)
    if obj:
        em_item.is_visible = not obj.hide_viewport
    else:
        em_item.is_visible = True
    
    # Epoch
    first_epoch = graph.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")
    if not first_epoch: 
        graph.print_node_connections(node)
    em_item.epoch = first_epoch.name if first_epoch else ""
    
    return index + 1


def populate_reuse_US_table(scene, node, index, graph):
    """
    Popola la tabella dei riusi per un nodo.
    
    ✅ CLEAN VERSION: Popola SOLO scene.em_tools.stratigraphy.reused
    """
    strat = scene.em_tools.stratigraphy
    
    survived_in_epoch = graph.get_connected_epoch_nodes_list_by_edge_type(node, "survive_in_epoch")
    
    if survived_in_epoch:
        for current_epoch in survived_in_epoch:
            strat.reused.add()
            em_item = strat.reused[-1]
            em_item.epoch = current_epoch.name
            em_item.em_element = node.name
            index += 1
            
    return index


def populate_document_node(scene, node, index, graph=None):
    """
    Popola la lista dei documenti.
    
    ✅ MODIFICATO: Ora usa SEMPRE il nome pulito del nodo, senza prefisso.
    """
    source_already_in_list = False
    for source_item in scene.em_tools.em_sources_list:
        if source_item.id_node == node.node_id:
            source_already_in_list = True
            break

    if not source_already_in_list:
        scene.em_tools.em_sources_list.add()
        em_item = scene.em_tools.em_sources_list[-1]
        
        # ✅ Nome pulito
        em_item.name = node.name
        em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name, graph=graph)
        em_item.id_node = node.node_id
        em_item.url = clean_value_for_ui(getattr(node, 'url', ''))
        em_item.icon_url = "CHECKBOX_HLT" if node.url else "CHECKBOX_DEHLT"
        em_item.description = node.description
        index += 1

    return index


def populate_property_node(scene, node, index, graph=None):
    """Popola la lista delle proprietà"""
    scene.em_tools.em_properties_list.add()
    em_item = scene.em_tools.em_properties_list[-1]
    
    if hasattr(node, 'attributes') and 'original_name' in node.attributes:
        em_item.name = node.attributes['original_name']
    else:
        em_item.name = node.name
    
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name, graph=graph)
    em_item.id_node = node.node_id
    em_item.url = clean_value_for_ui(getattr(node, 'value', ''))
    em_item.icon_url = "CHECKBOX_HLT" if em_item.url else "CHECKBOX_DEHLT"
    em_item.description = node.description
    return index + 1


def populate_extractor_node(scene, node, index, graph=None):
    """Popola la lista degli estrattori"""
    scene.em_tools.em_extractors_list.add()
    em_item = scene.em_tools.em_extractors_list[-1]
    em_item.name = node.name
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name, graph=graph)
    em_item.id_node = node.node_id
    em_item.url = clean_value_for_ui(getattr(node, 'source', ''))
    em_item.icon_url = "CHECKBOX_HLT" if node.source else "CHECKBOX_DEHLT"
    em_item.description = node.description
    return index + 1


def populate_combiner_node(scene, node, index, graph=None):
    """Popola la lista dei combinatori"""
    scene.em_tools.em_combiners_list.add()
    em_item = scene.em_tools.em_combiners_list[-1]
    em_item.name = node.name
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name, graph=graph)
    em_item.id_node = node.node_id
    raw_url = node.sources[0] if node.sources else ""
    em_item.url = clean_value_for_ui(raw_url)
    em_item.icon_url = "CHECKBOX_HLT" if node.sources else "CHECKBOX_DEHLT"
    em_item.description = node.description
    return index + 1


def populate_epoch_node(scene, node, index, graph=None):
    """Popola la lista delle epoche usando il container centralizzato."""
    from .functions import hex_to_rgb

    epochs = scene.em_tools.epochs.list
    epochs.add()
    epoch_item = epochs[-1]
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
    """Popola la lista degli archi"""
    scene.em_tools.edges_list.add()
    edge_item = scene.em_tools.edges_list[index]
    edge_item.id_node = edge.edge_id
    edge_item.source = edge.edge_source
    edge_item.target = edge.edge_target
    edge_item.edge_type = edge.edge_type
    return index + 1


def clear_lists(context):
    """
    Pulisce tutte le liste in Blender.

    ✅ CLEAN VERSION: Usa EM_list_clear per gestire le liste centralizzate
    """
    from .functions import EM_list_clear

    EM_list_clear(context, "em_list")  # ✅ Pulisce scene.em_tools.stratigraphy.units
    EM_list_clear(context, "em_reused")  # ✅ Pulisce scene.em_tools.stratigraphy.reused
    EM_list_clear(context, "em_sources_list")
    EM_list_clear(context, "em_properties_list")
    EM_list_clear(context, "em_extractors_list")
    EM_list_clear(context, "em_combiners_list")
    EM_list_clear(context, "edges_list")
    EM_list_clear(context, "epoch_list")
    
    return None


def update_graph_statistics(context, graph, graphml_file_item):
    """
    Aggiorna le statistiche dei nodi nel grafo (conteggi cached).
    Chiamata durante l'import per aggiornare i counter nella UI.

    Args:
        context: Blender context
        graph: Istanza del grafo s3dgraphy
        graphml_file_item: GraphMLFileItem dove salvare i conteggi
    """
    if not graph or not graphml_file_item:
        return

    # Conta nodi stratigrafici
    stratigraphic_types = ['US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs']
    stratigraphic_count = 0
    for node_type in stratigraphic_types:
        stratigraphic_count += len(graph.get_nodes_by_type(node_type))

    # Conta altri tipi di nodi
    epoch_count = len(graph.get_nodes_by_type('EpochNode'))
    property_count = len(graph.get_nodes_by_type('property'))
    document_count = len(graph.get_nodes_by_type('document'))

    # Salva i conteggi nelle proprietà
    graphml_file_item.stratigraphic_count = stratigraphic_count
    graphml_file_item.epoch_count = epoch_count
    graphml_file_item.property_count = property_count
    graphml_file_item.document_count = document_count

    print(f"✅ Graph statistics updated: {stratigraphic_count} stratigraphic, {epoch_count} epochs, {property_count} properties, {document_count} documents")


def populate_blender_lists_from_graph(context, graph):
    """
    Popola tutte le liste Blender da un grafo s3dgraphy.

    ✅ CLEAN VERSION: Usa solo paths centralizzati
    """
    scene = context.scene

    # Counters
    em_list_index_ema = 0
    em_reused_index_ema = 0
    em_sources_index_ema = 0
    em_properties_index_ema = 0
    em_extractors_index_ema = 0
    em_combiners_index_ema = 0
    em_edges_index_ema = 0
    em_epoch_list_ema = 0

    # ✅ OPTIMIZED: Batch node filtering - 1 iteration instead of 14 queries
    # Get all nodes once and filter by type in a single pass - O(n) instead of O(14×n)
    stratigraphic_types = {'US', 'USVs', 'USVn', 'VSF', 'SF', 'USD', 'serSU', 'serUSVn', 'serUSVs'}

    stratigraphic_nodes = []
    document_nodes = []
    property_nodes = []
    extractor_nodes = []
    combiner_nodes = []
    epoch_nodes = []

    # Single pass through all nodes - O(n)
    for node in graph.nodes:
        if not hasattr(node, 'node_type'):
            continue

        node_type = node.node_type

        if node_type in stratigraphic_types:
            stratigraphic_nodes.append(node)
        elif node_type == 'document':
            document_nodes.append(node)
        elif node_type == 'property':
            property_nodes.append(node)
        elif node_type == 'extractor':
            extractor_nodes.append(node)
        elif node_type == 'combiner':
            combiner_nodes.append(node)
        elif node_type == 'EpochNode':
            epoch_nodes.append(node)

    # 1. Nodi stratigrafici
    for node in stratigraphic_nodes:
        if isinstance(node, StratigraphicNode):
            em_list_index_ema = populate_stratigraphic_node(scene, node, em_list_index_ema, graph)
            em_reused_index_ema = populate_reuse_US_table(scene, node, em_reused_index_ema, graph)

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
