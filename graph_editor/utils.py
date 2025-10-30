"""
Utility functions for Graph Editor
Handles prefix management and data access helpers
"""

import bpy
import json
import os
from pathlib import Path

def sync_ui_list(context, human_name):
    """
    Sincronizza UIList usando item.name.
    
    Args:
        human_name: nome human-readable tipo "USM2193"
    """
    em_list = get_em_list_items(context)
    
    if not em_list:
        print(f"   ✗ em_list is empty")
        return False
    
    print(f"   sync_ui_list: searching for name='{human_name}'")
    
    # ✅ Cerca per item.name
    for i, item in enumerate(em_list):
        if item.name == human_name:
            set_em_list_active_index(context, i)
            print(f"   ✓ Selected UIList item: {item.name} (index {i})")
            return True
    
    print(f"   ✗ Item not found in UIList with name: '{human_name}'")
    return False

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
        return f"{graph_code}.{node_id}"  # ✅ Usa punto, non underscore
    return node_id

def remove_graph_prefix(prefixed_name, context):
    """Rimuove il prefisso del grafo dal nome"""
    graph_code = get_active_graph_code(context)
    if graph_code and prefixed_name.startswith(f"{graph_code}."):
        # ✅ Rimuove "AAC." lasciando "USM2193"
        return prefixed_name[len(graph_code) + 1:]
    return prefixed_name

def find_proxy_by_node_id(node_id, context):
    """Trova il proxy 3D corrispondente a un node_id (SENZA prefisso)"""
    # ✅ Aggiungi il prefisso per cercare l'oggetto
    prefixed_name = add_graph_prefix(node_id, context)
    
    print(f"   Looking for proxy: '{prefixed_name}' (from node_id: '{node_id}')")
    
    # Cerca negli oggetti della scena
    for obj in bpy.data.objects:
        if obj.name == prefixed_name:
            print(f"   ✓ Found proxy by name: {obj.name}")
            return obj
    
    # Fallback: controlla anche la proprietà node_id (senza prefisso)
    for obj in bpy.data.objects:
        if obj.get('node_id') == node_id:
            print(f"   ✓ Found proxy by node_id property: {obj.name}")
            return obj
    
    print(f"   ✗ Proxy not found for node_id: {node_id}")
    return None

# ✅ Cache globale (viene svuotata quando cambia grafo)
_node_cache = {}
_cached_graph_id = None

def find_node_id_from_proxy(proxy_obj, context, verbose=False):
    """
    Ottiene il node_id (UUID) da un oggetto proxy (con cache).
    """
    global _node_cache, _cached_graph_id
    
    from s3dgraphy import get_graph
    
    # Rimuovi prefisso dal nome
    human_name = remove_graph_prefix(proxy_obj.name, context)
    
    # Carica grafo
    em_tools = context.scene.em_tools
    if em_tools.active_file_index < 0 or not em_tools.graphml_files:
        return None
    
    graphml = em_tools.graphml_files[em_tools.active_file_index]
    graph_id = graphml.name
    
    # ✅ Svuota cache se cambia grafo
    if _cached_graph_id != graph_id:
        _node_cache.clear()
        _cached_graph_id = graph_id
        if verbose:
            print(f"   Cache cleared for new graph: {graph_id}")
    
    # ✅ Controlla cache
    if human_name in _node_cache:
        if verbose:
            print(f"   ✓ Found in cache: '{human_name}' → '{_node_cache[human_name]}'")
        return _node_cache[human_name]
    
    # Cerca nel grafo
    graph = get_graph(graph_id)
    if not graph:
        return None
    
    for node in graph.nodes:
        if node.name == human_name:
            # ✅ Salva in cache
            _node_cache[human_name] = node.node_id
            
            if verbose:
                print(f"   ✓ Found node: name='{node.name}', UUID='{node.node_id}' (cached)")
            
            return node.node_id
    
    if verbose:
        print(f"   ✗ Node not found with name: '{human_name}'")
    
    return None

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
    Returns: list di dict con le regole di connessione
    """
    try:
        # ✅ Import diretto da s3dgraphy (già caricato all'import)
        from s3dgraphy.graph import connection_rules
        return connection_rules
    except ImportError as e:
        print(f"⚠️  Could not import connection_rules from s3dgraphy: {e}")
        return []

def get_edge_types():
    """
    Ottiene tutti i tipi di edge disponibili da s3dgraphy.
    Returns: list di dict con type, label, description
    """
    rules = get_connection_rules()
    
    edge_types = []
    for rule in rules:
        edge_types.append({
            'type': rule['type'],
            'label': rule.get('label', rule['type']),
            'description': rule.get('description', ''),
            'allowed_sources': rule['allowed_connections']['source'],
            'allowed_targets': rule['allowed_connections']['target']
        })
    
    print(f"   Loaded {len(edge_types)} edge types from s3dgraphy")
    return edge_types

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