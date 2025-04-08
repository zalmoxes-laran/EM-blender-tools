import bpy

from .functions import *
#from .epoch_manager import *

#from .s3Dgraphy import *
from .s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode  # Import diretto
from .s3Dgraphy.nodes.document_node import DocumentNode  # Import diretto
from .s3Dgraphy.nodes.property_node import PropertyNode  # Import diretto
from .s3Dgraphy.nodes.extractor_node import ExtractorNode  # Import diretto
from .s3Dgraphy.nodes.combiner_node import CombinerNode  # Import diretto
from .s3Dgraphy.nodes.epoch_node import EpochNode  # Import diretto


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

def populate_blender_lists_from_graph(context, graph):
    """
    Popola le liste di Blender con i dati dal grafo.
    
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
    
    # 2. Nodi documento
    for node in document_nodes:
        em_sources_index_ema = populate_document_node(scene, node, em_sources_index_ema)
    
    # 3. Nodi proprietà
    for node in property_nodes:
        em_properties_index_ema = populate_property_node(scene, node, em_properties_index_ema)
    
    # 4. Nodi estrattore
    for node in extractor_nodes:
        em_extractors_index_ema = populate_extractor_node(scene, node, em_extractors_index_ema)
    
    # 5. Nodi combinatore
    for node in combiner_nodes:
        em_combiners_index_ema = populate_combiner_node(scene, node, em_combiners_index_ema)
    
    # 6. Nodi epoca
    for node in epoch_nodes:
        em_epoch_list_ema = populate_epoch_node(scene, node, em_epoch_list_ema)
    
    # 7. Archi
    for edge in graph.edges:
        populate_edges(scene, edge, em_edges_index_ema)
        em_edges_index_ema += 1

def populate_reuse_US_table(scene, node, index, graph):
    survived_in_epoch = graph.get_connected_epoch_nodes_list_by_edge_type(node, "survive_in_epoch")
    #print(f"Per il nodo {node.name}:")

    if survived_in_epoch:
        #graph.print_connected_epoch_nodes_and_edge_types(node)
        for current_epoch in survived_in_epoch:
            scene.em_reused.add()
            em_item = scene.em_reused[-1]
            em_item.epoch = current_epoch.name
            em_item.em_element = node.name
            #print(f"Sto aggiungendo all'elenco dei reused il nodo {em_item.em_element} per l'epoca {em_item.epoch}")
            index += 1
            
    return index

# Update to the populate_stratigraphic_node function in populate_lists.py

def populate_stratigraphic_node(scene, node, index, graph):
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
    em_item.node_type = node.node_type  # Save the node type in the list

    # Set visibility status based on actual viewport visibility
    obj = bpy.data.objects.get(node.name)
    if obj:
        em_item.is_visible = not obj.hide_viewport
    else:
        em_item.is_visible = True
    
    first_epoch = graph.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")
    if not first_epoch: 
        graph.print_node_connections(node)
    em_item.epoch = first_epoch.name if first_epoch else ""
    
    return index + 1

def populate_document_node(scene, node, index):
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

def populate_property_node(scene, node, index):
    scene.em_properties_list.add()
    em_item = scene.em_properties_list[-1]
    em_item.name = node.name
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
    em_item.id_node = node.node_id
    em_item.url = node.value if node.value is not None else ""
    em_item.icon_url = "CHECKBOX_HLT" if node.value else "CHECKBOX_DEHLT"
    em_item.description = node.description
    return index + 1

def populate_extractor_node(scene, node, index):
    scene.em_extractors_list.add()
    em_item = scene.em_extractors_list[-1]
    em_item.name = node.name
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
    em_item.id_node = node.node_id
    em_item.url = node.source if node.source is not None else ""
    em_item.icon_url = "CHECKBOX_HLT" if node.source else "CHECKBOX_DEHLT"
    em_item.description = node.description
    return index + 1

def populate_combiner_node(scene, node, index):
    scene.em_combiners_list.add()
    em_item = scene.em_combiners_list[-1]
    em_item.name = node.name
    em_item.icon = check_objs_in_scene_and_provide_icon_for_list_element(node.name)
    em_item.id_node = node.node_id
    em_item.url = node.sources[0] if node.sources else ""
    em_item.icon_url = "CHECKBOX_HLT" if node.sources else "CHECKBOX_DEHLT"
    em_item.description = node.description
    return index + 1

def populate_epoch_node(scene, node, index):
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

def populate_edges(scene, edge, index):
    scene.edges_list.add()
    edge_item = scene.edges_list[index]
    edge_item.id_node = edge.edge_id
    edge_item.source = edge.edge_source
    edge_item.target = edge.edge_target
    edge_item.edge_type = edge.edge_type
    return index + 1

def clear_lists(context):
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