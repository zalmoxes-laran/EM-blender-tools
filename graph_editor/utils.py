"""
Utility functions for Graph Editor
Handles prefix management and data access helpers
"""

import bpy
import json
import os
from pathlib import Path

def get_active_graph_code(context):
    """Ottiene il graph_code del grafo attivo"""
    em_tools = context.scene.em_tools
    if em_tools.active_file_index >= 0 and em_tools.graphml_files:
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        return graphml.graph_code
    return None

def add_graph_prefix(node_id, context):
    """Aggiunge il prefisso del grafo attivo al node_id"""
    graph_code = get_active_graph_code(context)
    if graph_code:
        return f"{graph_code}_{node_id}"
    return node_id

def remove_graph_prefix(prefixed_name, context):
    """Rimuove il prefisso del grafo dal nome"""
    graph_code = get_active_graph_code(context)
    if graph_code and prefixed_name.startswith(f"{graph_code}_"):
        return prefixed_name[len(graph_code) + 1:]
    return prefixed_name

def find_proxy_by_node_id(node_id, context):
    """Trova il proxy 3D corrispondente a un node_id"""
    prefixed_name = add_graph_prefix(node_id, context)
    
    # Cerca negli oggetti della scena
    for obj in bpy.data.objects:
        if obj.name == prefixed_name:
            return obj
        # Fallback: controlla anche la proprietà node_id
        if obj.get('node_id') == node_id:
            return obj
    
    return None

def find_node_id_from_proxy(proxy_obj, context):
    """Ottiene il node_id da un oggetto proxy"""
    # Prova con proprietà node_id
    if 'node_id' in proxy_obj:
        return proxy_obj['node_id']
    
    # Prova rimuovendo il prefisso dal nome
    node_id = remove_graph_prefix(proxy_obj.name, context)
    return node_id

def get_em_list_items(context):
    """Ottiene gli item della UIList filtrata"""
    return context.scene.em_list

def get_em_list_active_index(context):
    """Ottiene l'indice attivo della UIList"""
    return context.scene.em_list_index

def set_em_list_active_index(context, index):
    """Imposta l'indice attivo della UIList"""
    context.scene.em_list_index = index

def get_connection_rules():
    """
    Carica le regole di connessione da s3dgraphy.
    Returns: dict con le regole di connessione
    """
    try:
        # Import s3dgraphy per accedere ai connection_rules
        from s3dgraphy.graph import connection_rules
        return connection_rules
    except ImportError:
        print("⚠️  Could not import connection_rules from s3dgraphy")
        return []

def get_edge_types():
    """
    Ottiene tutti i tipi di edge disponibili da s3dgraphy.
    Returns: list di dict con type, label, description
    """
    rules = get_connection_rules()
    return [
        {
            'type': rule['type'],
            'label': rule.get('label', rule['type']),
            'description': rule.get('description', ''),
            'allowed_sources': rule['allowed_connections']['source'],
            'allowed_targets': rule['allowed_connections']['target']
        }
        for rule in rules
    ]

def get_stratigraphic_edge_types():
    """Ottiene solo i tipi di edge stratigrafici"""
    all_types = get_edge_types()
    stratigraphic_keywords = [
        'is_before', 'is_after', 'has_same_time', 'changed_from',
        'overlies', 'is_overlain_by', 'abuts', 'is_abutted_by',
        'cuts', 'is_cut_by', 'fills', 'is_filled_by', 'rests_on',
        'is_bonded_to', 'is_physically_equal_to'
    ]
    return [et for et in all_types if et['type'] in stratigraphic_keywords]

def get_paradata_edge_types():
    """Ottiene solo i tipi di edge per paradata"""
    all_types = get_edge_types()
    paradata_keywords = [
        'has_property', 'has_data_provenance', 'extracted_from',
        'combines', 'has_documentation', 'is_in_paradata_nodegroup',
        'has_paradata_nodegroup'
    ]
    return [et for et in all_types if et['type'] in paradata_keywords]

def get_model_edge_types():
    """Ottiene solo i tipi di edge per modelli 3D"""
    all_types = get_edge_types()
    model_keywords = [
        'has_representation_model', 'has_semantic_shape', 'has_linked_resource'
    ]
    return [et for et in all_types if et['type'] in model_keywords]