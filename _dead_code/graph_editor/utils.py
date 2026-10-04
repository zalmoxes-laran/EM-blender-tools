"""
Utility functions for Graph Viewer
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
            print(f"   Selected UIList item: {item.name} (index {i})")
            return True
    
    print(f"   ✗ Item not found in UIList with name: '{human_name}'")
    return False

def get_active_graph(context):
    """
    Ottiene il grafo attivo basato sulla modalità.

    Returns:
        tuple: (graph, graph_name) o (None, None) se non trovato

    Comportamento:
    - 3D GIS mode: restituisce il grafo hardcodato "3dgis_graph"
    - EM Advanced mode: restituisce il grafo selezionato dall'utente
    """
    from s3dgraphy.multigraph import get_graph

    em_tools = context.scene.em_tools

    # ✅ Modalità 3D GIS: usa grafo hardcodato
    if not em_tools.mode_em_advanced:
        graph_name = "3dgis_graph"
        graph = get_graph(graph_name)
        if graph:
            return graph, graph_name
        else:
            print(f"Warning: 3D GIS graph '{graph_name}' not found")
            return None, None

    # ✅ Modalità EM Advanced: usa grafo attivo
    if em_tools.active_file_index >= 0 and em_tools.graphml_files:
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graphml.name)
        if graph:
            return graph, graphml.name
        else:
            print(f"Warning: Graph '{graphml.name}' not found")
            return None, None

    return None, None

def get_active_graph_code(context):
    """Ottiene il graph_code del grafo attivo (per i prefissi)"""
    em_tools = context.scene.em_tools

    # ✅ In modalità 3D GIS non usiamo prefissi
    if not em_tools.mode_em_advanced:
        return None

    # ✅ In modalità EM Advanced usa il grafo attivo
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
            print(f"   Found proxy by name: {obj.name}")
            return obj
    
    # Fallback: controlla anche la proprietà node_id (senza prefisso)
    for obj in bpy.data.objects:
        if obj.get('node_id') == node_id:
            print(f"   Found proxy by node_id property: {obj.name}")
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

    # Rimuovi prefisso dal nome
    human_name = remove_graph_prefix(proxy_obj.name, context)

    # ✅ Carica grafo usando la funzione centralizzata
    graph, graph_id = get_active_graph(context)
    if not graph:
        return None

    # ✅ Svuota cache se cambia grafo
    if _cached_graph_id != graph_id:
        _node_cache.clear()
        _cached_graph_id = graph_id
        if verbose:
            print(f"   Cache cleared for new graph: {graph_id}")

    # ✅ Controlla cache
    if human_name in _node_cache:
        if verbose:
            print(f"   Found in cache: '{human_name}' → '{_node_cache[human_name]}'")
        return _node_cache[human_name]

    # Cerca nel grafo (graph già caricato sopra)
    
    for node in graph.nodes:
        if node.name == human_name:
            # ✅ Salva in cache
            _node_cache[human_name] = node.node_id
            
            if verbose:
                print(f"   Found node: name='{node.name}', UUID='{node.node_id}' (cached)")
            
            return node.node_id
    
    if verbose:
        print(f"   ✗ Node not found with name: '{human_name}'")
    
    return None

def get_em_list_items(context):
    """Ottiene gli item della UIList filtrata - ✅ CLEAN VERSION"""
    return context.scene.em_tools.stratigraphy.units

def get_em_list_active_index(context):
    """Ottiene l'indice attivo della UIList - ✅ CLEAN VERSION"""
    return context.scene.em_tools.stratigraphy.units_index

def set_em_list_active_index(context, index):
    """Imposta l'indice attivo della UIList - ✅ CLEAN VERSION"""
    context.scene.em_tools.stratigraphy.units_index = index

def get_connection_rules():
    """
    Carica le regole di connessione dal datamodel delle connessioni di s3dgraphy.
    Returns: list di dict con type, label, description, allowed_connections

    Legge ``ConnectionsDatamodel`` (``s3dgraphy.edges``), cioè il JSON che è la
    fonte di verità. Prima importava ``s3dgraphy.graph.connection_rules``, che
    s3Dgraphy ha tolto il 2026-04-03 (d2eab12): l'ImportError veniva inghiottito
    e il graph editor riceveva una lista vuota, quindi filtri e contesto non
    trovavano nessun arco. I nomi comprendono i reverse e le grafie accettate.
    """
    try:
        from s3dgraphy.edges import get_connections_datamodel
        dm = get_connections_datamodel()
    except Exception as e:
        print(f"Warning: Could not load the s3dgraphy connections datamodel: {e}")
        return []
    return [{
        'type': name,
        'label': dm.get_label(name) or name,
        'description': dm.get_description(name),
        'allowed_connections': {
            'source': dm.get_allowed_sources(name),
            'target': dm.get_allowed_targets(name),
        },
    } for name in dm.get_all_edge_names()]

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

# Le relazioni stratigrafiche, per NOME DI RELAZIONE. Non sono le grafie: quelle
# le dice il datamodel (`spelling_of`, connections 1.6.20) e le aggiunge
# `with_spellings`. È l'UNICA lista: `properties.initialize_edge_filters` la
# importa da qui.
STRATIGRAPHIC_RELATIONS = (
    'is_before', 'is_after', 'has_same_time', 'changed_from',
    'overlies', 'is_overlain_by', 'abuts', 'is_abutted_by',
    'cuts', 'is_cut_by', 'fills', 'is_filled_by', 'rests_on',
    'bonded_to', 'equals',
)

# Usato SOLO quando s3dgraphy non ha `spellings()` (prima di connections 1.6.20,
# es. il wheel dev17 del manifest): è lo stesso fallback letterale che s3dgraphy
# tiene per un datamodel illeggibile. Col datamodel nuovo non viene letto.
# Da togliere quando il wheel pinnato sarà ≥ 1.6.20.
_SPELLINGS_BEFORE_1620 = {
    'bonded_to': ('is_bonded_to',),
    'equals': ('is_physically_equal_to',),
}

def with_spellings(names):
    """I nomi dati più ogni grafia che il datamodel accetta per la stessa
    relazione: ``with_spellings(['bonded_to']) == {'bonded_to', 'is_bonded_to'}``.

    Chiede a ``ConnectionsDatamodel.spellings()`` (s3dgraphy ≥ connections
    1.6.20): una terza grafia aggiunta in s3Dgraphy arriva qui senza toccare
    EMtools. Senza il metodo si usa ``_SPELLINGS_BEFORE_1620``.
    """
    out = set(names)
    try:
        from s3dgraphy.edges import get_connections_datamodel
        spellings = getattr(get_connections_datamodel(), 'spellings', None)
    except Exception:
        spellings = None
    for name in names:
        if spellings:
            out |= set(spellings(name))
        else:
            out |= set(_SPELLINGS_BEFORE_1620.get(name, ()))
    return out

def get_stratigraphic_edge_types():
    """Ottiene solo i tipi di edge stratigrafici (in ogni grafia accettata)"""
    all_types = get_edge_types()
    stratigraphic = with_spellings(STRATIGRAPHIC_RELATIONS)
    return [et for et in all_types if et['type'] in stratigraphic]

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