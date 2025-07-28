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
    
    # Fallback: usa active_file_index invece di cercare is_active
    if hasattr(scene, 'em_tools') and scene.em_tools.graphml_files and scene.em_tools.active_file_index >= 0:
        try:
            # Ottieni il file GraphML attivo usando active_file_index
            active_file = scene.em_tools.graphml_files[scene.em_tools.active_file_index]
            
            # Se ha già un graph_code definito, usalo
            if hasattr(active_file, 'graph_code') and active_file.graph_code not in ["site_id", "MISSINGCODE", ""]:
                return active_file.graph_code
            
            # Altrimenti estrai il codice dal path
            return extract_code_from_path(active_file.graphml_path)
            
        except (IndexError, AttributeError):
            # Se l'indice è fuori range o ci sono altri problemi
            pass
    
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
    import re
    
    if not filepath:
        return "UNKNOWN"
        
    filename = os.path.basename(filepath)
    # Rimuovi estensione
    name_without_ext = os.path.splitext(filename)[0]
    
    # Cerca pattern come GT16, VDL14, etc. all'inizio del nome
    pattern = r'^([A-Z]{2,4}\d{1,4})'
    match = re.match(pattern, name_without_ext.upper())
    
    if match:
        return match.group(1)
    
    # Fallback: prova a trovare pattern nel nome completo
    pattern2 = r'([A-Z]{2,4}\d{1,4})'
    matches = re.findall(pattern2, name_without_ext.upper())
    
    if matches:
        return matches[0]
    
    return "UNKNOWN"

def should_show_multigraph(context):
    """
    Controlla se siamo in modalità multigraph
    Args:
        context: Contesto Blender  
    Returns:
        bool: True se in modalità multigraph
    """
    scene = context.scene
    return getattr(scene, 'show_all_graphs', False)

def get_loaded_graphs_count(context):
    """
    Ottiene il numero di grafi caricati
    Args:
        context: Contesto Blender
    Returns:
        int: Numero di grafi caricati
    """
    from ..s3Dgraphy import get_all_graphs
    
    all_graphs = get_all_graphs()
    return len(all_graphs) if all_graphs else 0

def format_name_for_display(full_name, fallback_name, is_multigraph):
    """
    Formatta un nome per la visualizzazione in base alla modalità
    Args:
        full_name (str): Nome completo (es. "GT16.USM10")  
        fallback_name (str): Nome di fallback se full_name è vuoto
        is_multigraph (bool): True se in modalità multigraph
    Returns:
        str: Nome formattato per il display
    """
    name = full_name or fallback_name
    
    if is_multigraph:
        # In modalità multigraph, mostra i nomi completi
        return name
    else:
        # In modalità singolo grafo, mostra solo la parte dopo il punto
        return get_display_name(name)

def format_graph_code_for_display(full_name, active_graph_code):
    """
    Estrae il codice grafo per la visualizzazione
    Args:
        full_name (str): Nome completo (es. "GT16.USM10")
        active_graph_code (str): Codice del grafo attivo
    Returns:
        str: Codice grafo o None
    """
    code = get_graph_code_from_name(full_name)
    return code if code and code != active_graph_code else None