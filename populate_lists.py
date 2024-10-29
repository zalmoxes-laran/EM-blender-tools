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


def populate_blender_lists_from_graph(context, graph):
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
            populate_stratigraphic_node(scene, node, em_list_index_ema, graph)
            em_list_index_ema += 1
            em_reused_index_ema = populate_reuse_US_table(scene, node, em_reused_index_ema, graph)
        elif isinstance(node, DocumentNode):
            em_sources_index_ema = populate_document_node(scene, node, em_sources_index_ema)
            em_sources_index_ema +=1
        elif isinstance(node, PropertyNode):
            em_properties_index_ema = populate_property_node(scene, node, em_properties_index_ema)
            em_properties_index_ema +=1
        elif isinstance(node, ExtractorNode):
            em_extractors_index_ema = populate_extractor_node(scene, node, em_extractors_index_ema)
            em_extractors_index_ema +=1
        elif isinstance(node, CombinerNode):
            em_combiners_index_ema = populate_combiner_node(scene, node, em_combiners_index_ema)
            em_combiners_index_ema +=1
        elif isinstance(node, EpochNode):
            em_epoch_list_ema = populate_epoch_node(scene, node, em_epoch_list_ema)
    for edge in graph.edges:
        populate_edges(scene, edge, em_edges_index_ema)

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
    
    #em_item.epoch = node.epoch if node.epoch else ""
    #graph.print_connected_epoch_nodes_and_edge_types(node)
    first_epoch = graph.get_connected_epoch_node_by_edge_type(node, "has_first_epoch")

    em_item.epoch = first_epoch.name if first_epoch else ""

    #print("Ho registrato l'epoca "+em_item.epoch+" per il nodo"+em_item.name)
    #em_item.epoch = graph.get_epochs_list_for_stratigraphicnode(node.node_id)
    
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