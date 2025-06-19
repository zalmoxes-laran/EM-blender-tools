# name_conversion_utils.py
"""
Utilities per la conversione tra nomi display e nomi proxy
"""

def get_display_name(full_name):
    """
    Converte un nome completo (GT16.USM10) in nome display (USM10)
    Args:
        full_name (str): Nome completo con prefisso (es. "GT16.USM10")
    Returns:
        str: Nome senza prefisso (es. "USM10")
    """
    if "." in full_name:
        return full_name.split(".", 1)[1]
    return full_name

def get_proxy_name(display_name, graph_code):
    """
    Converte un nome display in nome proxy completo
    Args:
        display_name (str): Nome senza prefisso (es. "USM10")
        graph_code (str): Codice del grafo (es. "GT16")
    Returns:
        str: Nome completo (es. "GT16.USM10")
    """
    return f"{graph_code}.{display_name}"

def get_graph_code_from_name(full_name):
    """
    Estrae il codice grafo da un nome completo
    Args:
        full_name (str): Nome completo (es. "GT16.USM10")
    Returns:
        str: Codice grafo (es. "GT16") o None se non presente
    """
    if "." in full_name:
        return full_name.split(".", 1)[0]
    return None

def get_active_graph_code(context):
    """
    Ottiene il codice del grafo attualmente attivo
    Args:
        context: Contesto Blender
    Returns:
        str: Codice del grafo attivo o None
    """
    scene = context.scene
    
    # Cerca nei grafi caricati per trovare quello attivo
    from ..s3Dgraphy import get_active_graph
    active_graph = get_active_graph()
    
    if active_graph and hasattr(active_graph, 'attributes'):
        return active_graph.attributes.get('graph_code', 'UNKNOWN')
    
    # Fallback: cerca il primo grafo disponibile
    if hasattr(scene, 'em_tools') and scene.em_tools.graphml_files:
        for graphml in scene.em_tools.graphml_files:
            if graphml.is_active:  # Assumendo che ci sia un flag is_active
                # Estrai il codice dal path o dal nome
                return extract_code_from_path(graphml.graphml_path)
    
    return "UNKNOWN"

def extract_code_from_path(filepath):
    """
    Estrae il codice grafo dal percorso del file
    Args:
        filepath (str): Percorso del file GraphML
    Returns:
        str: Codice estratto o "UNKNOWN"
    """
    import os
    filename = os.path.basename(filepath)
    # Rimuovi estensione
    name_without_ext = os.path.splitext(filename)[0]
    
    # Cerca pattern come GT16, VDL14, etc.
    import re
    match = re.search(r'([A-Z]{2,}\d+)', name_without_ext)
    if match:
        return match.group(1)
    
    return "UNKNOWN"

def should_show_multigraph(context):
    """
    Determina se siamo in modalità multigraph
    Args:
        context: Contesto Blender
    Returns:
        bool: True se in modalità multigraph
    """
    scene = context.scene
    return getattr(scene, 'show_all_graphs', False)

def format_name_for_display(item_name, graph_code, is_multigraph=False):
    """
    Formatta il nome per la visualizzazione nelle liste
    Args:
        item_name (str): Nome dell'item (può essere con o senza prefisso)
        graph_code (str): Codice del grafo
        is_multigraph (bool): Se siamo in modalità multigraph
    Returns:
        str: Nome formattato per display
    """
    display_name = get_display_name(item_name)
    
    if is_multigraph:
        # In modalità multigraph, mostra il nome pulito
        # Il codice grafo sarà mostrato in una colonna separata
        return display_name
    else:
        # In modalità singolo grafo, mostra solo il nome pulito
        return display_name

def format_graph_code_for_display(item_name, fallback_code=""):
    """
    Estrae e formatta il codice grafo per la visualizzazione
    Args:
        item_name (str): Nome dell'item
        fallback_code (str): Codice di fallback se non trovato
    Returns:
        str: Codice grafo formattato
    """
    code = get_graph_code_from_name(item_name)
    return code if code else fallback_code