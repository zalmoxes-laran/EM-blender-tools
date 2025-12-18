# EMtools/icons_manager.py
import bpy # type: ignore
import bpy.utils.previews # type: ignore
import os
import logging

log = logging.getLogger(__name__)

# Dizionario globale per le icone
icon_collections = {}

def get_icons_dir():
    """Ottieni il percorso della cartella icons"""
    return os.path.join(os.path.dirname(__file__), "icons")

def load_icons():
    """Carica tutte le icone dell'estensione (lazy loading)"""
    global icon_collections
    
    if "emtools_icons" in icon_collections:
        return icon_collections["emtools_icons"]
    
    # Crea una nuova collezione di icone
    pcoll = bpy.utils.previews.new()
    
    # Path alla cartella icons
    icons_dir = get_icons_dir()
    
    # Lista delle icone disponibili (aggiungi qui le nuove)
    icon_files = {
        "show_all_proxies": "show_all_proxies.png",
        "show_all_proxies_off": "show_all_proxies_off.png",
        "show_all_RMs": "show_all_RMs.png",
        "show_all_RMs_off": "show_all_RMs_off.png",
        "show_all_special_finds": "show_all_special_finds.png",
        "show_all_special_finds_off": "show_all_special_finds_off.png",
        "heriverse_logo_tight": "Heriverse_LOGO_tight_BW_bold.png",
        "combiner": "combiner.png",
        "extractor": "extractor.png",
        "document": "document.png",
        "property": "property.png",
        "pyarchinit": "pyarchinit.png",
        "em_no_publish": "em_no_publish.png",
        "em_publish": "em_publish.png",
        "em_logo": "em_logo_small.png",
        "EMdb_logo": "EMdb_logo.png",
    }
    
    # Carica ogni icona che esiste
    loaded_count = 0
    for icon_name, filename in icon_files.items():
        icon_path = os.path.join(icons_dir, filename)
        if os.path.exists(icon_path):
            try:
                pcoll.load(icon_name, icon_path, 'IMAGE')
                loaded_count += 1
                log.debug(f"Icona caricata: {icon_name}")
            except Exception as e:
                log.warning(f"Errore nel caricare l'icona {icon_name}: {e}")
        else:
            log.warning(f"Icona non trovata: {icon_path}")
    
    icon_collections["emtools_icons"] = pcoll
    log.info(f"Caricate {loaded_count} icone EMtools")
    return pcoll

def get_custom_icon(icon_name):
    """
    Ottieni l'icon_value per icone personalizzate
    
    Args:
        icon_name (str): Nome dell'icona personalizzata
    
    Returns:
        int: icon_value per icon_value= parameter, o 0 se non trovata
    """
    try:
        icons = load_icons()
        if icon_name in icons:
            return icons[icon_name].icon_id
        return 0
    except Exception as e:
        log.error(f"Errore nell'ottenere icon_value per '{icon_name}': {e}")
        return 0

def get_builtin_icon(icon_name, fallback='FILE_BLANK'):
    """
    Ottieni nome icona built-in come fallback
    
    Args:
        icon_name (str): Nome dell'icona (ignorato, usa fallback)
        fallback (str): Nome icona Blender built-in
    
    Returns:
        str: Nome icona per icon= parameter
    """
    return fallback

def is_icon_available(icon_name):
    """Verifica se un'icona personalizzata è disponibile"""
    try:
        icons = load_icons()
        return icon_name in icons
    except:
        return False

def list_available_icons():
    """Ottieni lista delle icone disponibili (per debug)"""
    try:
        icons = load_icons()
        return list(icons.keys())
    except:
        return []

def draw_operator_with_icon(layout, operator_id, icon_name, 
                           text="", fallback_icon='FILE_BLANK', **kwargs):
    """
    Helper per disegnare operator con icona personalizzata o fallback
    
    Args:
        layout: Layout Blender
        operator_id (str): ID dell'operatore
        icon_name (str): Nome icona personalizzata
        text (str): Testo del bottone
        fallback_icon (str): Icona Blender di fallback
        **kwargs: Altri parametri per operator()
    
    Returns:
        operator: L'operatore creato
    """
    custom_icon_id = get_custom_icon(icon_name)
    
    if custom_icon_id != 0:
        # Usa icona personalizzata
        return layout.operator(operator_id, text=text, 
                             icon_value=custom_icon_id, **kwargs)
    else:
        # Usa icona built-in come fallback
        return layout.operator(operator_id, text=text, 
                             icon=fallback_icon, **kwargs)

def draw_label_with_icon(layout, text, icon_name, fallback_icon='INFO'):
    """
    Helper per disegnare label con icona personalizzata o fallback
    
    Args:
        layout: Layout Blender
        text (str): Testo del label
        icon_name (str): Nome icona personalizzata
        fallback_icon (str): Icona Blender di fallback
    
    Returns:
        label: Il label creato
    """
    custom_icon_id = get_custom_icon(icon_name)
    
    if custom_icon_id != 0:
        # Usa icona personalizzata
        return layout.label(text=text, icon_value=custom_icon_id)
    else:
        # Usa icona built-in come fallback
        return layout.label(text=text, icon=fallback_icon)

def unload_icons():
    """Rimuovi tutte le icone dalla memoria"""
    global icon_collections

    try:
        for key, pcoll in list(icon_collections.items()):
            try:
                bpy.utils.previews.remove(pcoll)
                log.debug(f"Removed preview collection: {key}")
            except Exception as e:
                log.warning(f"Error removing preview collection {key}: {e}")

        icon_collections.clear()
        log.info("Icone EMtools scaricate dalla memoria")
    except Exception as e:
        log.error(f"Errore nello scaricare le icone: {e}")

# Backward compatibility functions (deprecate, ma funzionano)
def get_icon_value(icon_name):
    """DEPRECATO: Usa get_custom_icon() invece"""
    return get_custom_icon(icon_name)

def get_icon(icon_name, fallback='FILE_BLANK'):
    """DEPRECATO: Usa get_custom_icon() e get_builtin_icon() invece"""
    custom_id = get_custom_icon(icon_name)
    return custom_id if custom_id != 0 else fallback

# Funzioni shortcut per icone specifiche (aggiungi quando necessario)
def icon_show_all_proxies():
    """Shortcut per l'icona show_all_proxies"""
    return get_custom_icon("show_all_proxies")

def icon_em_logo():
    """Shortcut per l'icona del logo EM (quando disponibile)"""
    return get_custom_icon("em_logo")

def icon_node_us():
    """Shortcut per l'icona nodo US (quando disponibile)"""
    return get_custom_icon("node_us")

def icon_node_usm():
    """Shortcut per l'icona nodo USM (quando disponibile)"""
    return get_custom_icon("node_usm")

# Test e debug functions
def test_icons():
    """Testa il caricamento delle icone (per debug)"""
    print("=== Test Icone EMtools ===")
    print(f"Cartella icone: {get_icons_dir()}")
    print(f"Cartella esiste: {os.path.exists(get_icons_dir())}")
    
    icons = load_icons()
    available = list_available_icons()
    
    print(f"Icone caricate: {len(available)}")
    for icon_name in available:
        icon_id = get_custom_icon(icon_name)
        print(f"  - {icon_name}: ID={icon_id}")
    
    print("=== Fine Test ===")

def print_debug_info():
    """Stampa informazioni di debug sulle icone"""
    print("=== Debug Icone EMtools ===")
    print(f"Collections attive: {len(icon_collections)}")
    print(f"Icone disponibili: {list_available_icons()}")
    print(f"Cartella icons: {get_icons_dir()}")
    
    icons_dir = get_icons_dir()
    if os.path.exists(icons_dir):
        files = [f for f in os.listdir(icons_dir) if f.endswith('.png')]
        print(f"File PNG nella cartella: {files}")
    else:
        print("Cartella icons non trovata!")
    print("=== Fine Debug ===")

# Funzioni di registrazione Blender
def register():
    """Registra il modulo icons_manager"""
    try:
        # Carica le icone all'avvio
        load_icons()
        log.info("Icons manager registrato con successo")
    except Exception as e:
        log.error(f"Errore nella registrazione icons manager: {e}")

def unregister():
    """Disregistra il modulo icons_manager"""
    try:
        # Scarica le icone alla chiusura
        unload_icons()
        log.info("Icons manager disregistrato con successo")
    except Exception as e:
        log.error(f"Errore nella disregistrazione icons manager: {e}")

# Se questo file viene eseguito direttamente (per test)
if __name__ == "__main__":
    test_icons()
