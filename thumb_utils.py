# thumb_utils.py
"""
Sistema di gestione thumbnails per EM-Tools
Gestisce cache locale, generazione thumbnails e preview collections
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import bpy
import bpy.utils.previews
from PIL import Image, ImageOps

# Collezione globale per le preview
preview_collections = {}

# Cache per evitare loop infiniti nel caricamento thumbnails
_cached_us_thumbs = {}  # {us_node_id: [(doc_key, name, desc, icon_id, i), ...]}
_last_us_id = None
_last_resource_folder = None

_resolved_paths_cache = {}  # {raw_path: resolved_absolute_path}

def resolve_resource_folder(resource_folder_path: str, verbose: bool = False) -> str:
    """
    Risolve correttamente la resource_folder sia che sia assoluta o relativa.
    ✅ CON CACHE per evitare di risolvere lo stesso path ripetutamente.
    
    Args:
        resource_folder_path: Path che può essere:
            - Assoluto: "/path/completo/Resources"
            - Relativo Blender: "//Resources" o "//../Resources" (relativo al .blend)
            - Relativo semplice: "Resources" o "../Resources"
        verbose: Se True, stampa i log di debug (default: False)
    
    Returns:
        Path assoluto risolto correttamente, o None se impossibile
    """
    global _resolved_paths_cache
    
    if not resource_folder_path:
        return None
    
    # Pulisci solo spazi, NON normalizzare ancora!
    resource_folder_path = resource_folder_path.strip()
    
    # ✅ CHECK CACHE: se già risolto, ritorna subito
    if resource_folder_path in _resolved_paths_cache:
        return _resolved_paths_cache[resource_folder_path]
    
    # Se è già assoluto (non inizia con // e non contiene ..), ritorna
    if os.path.isabs(resource_folder_path) and not resource_folder_path.startswith("//"):
        result = os.path.normpath(resource_folder_path)
        if verbose:
            print(f"✓ Path assoluto: {result}")
        _resolved_paths_cache[resource_folder_path] = result
        return result
    
    # Se inizia con //, lascia che bpy.path.abspath lo risolva
    # IMPORTANTE: NON normalizzare prima, o perdi il ".." in "//../"
    if resource_folder_path.startswith("//"):
        resolved = bpy.path.abspath(resource_folder_path)
        # SOLO ORA normalizza il risultato
        result = os.path.normpath(resolved)
        if verbose:
            print(f"✓ Path relativo Blender: {resource_folder_path} → {result}")
        
        # Verifica che il path esista
        if os.path.exists(result):
            _resolved_paths_cache[resource_folder_path] = result
            return result
        else:
            if verbose:
                print(f"⚠️ Path risolto non esiste: {result}")
            _resolved_paths_cache[resource_folder_path] = None
            return None
    
    # Path relativo semplice (senza //)
    blend_path = bpy.data.filepath
    if not blend_path:
        if verbose:
            print("⚠️ File .blend non salvato, impossibile risolvere path relativi senza //")
        return None
    
    blend_dir = os.path.dirname(blend_path)
    # Risolvi il path relativo rispetto alla directory del .blend
    absolute_path = os.path.join(blend_dir, resource_folder_path)
    result = os.path.normpath(absolute_path)
    if verbose:
        print(f"✓ Path relativo: {resource_folder_path} → {result}")
    
    # Verifica che il path esista
    if os.path.exists(result):
        _resolved_paths_cache[resource_folder_path] = result
        return result
    else:
        if verbose:
            print(f"⚠️ Path risolto non esiste: {result}")
        _resolved_paths_cache[resource_folder_path] = None
        return None

def em_thumbs_root(resource_folder_path: str = None) -> Path:
    """
    Restituisce la cartella thumbnails per una resource_folder specifica.
    ✅ NUOVO: Hash basato sul path RELATIVO per portabilità cross-PC OneDrive.
    Se due file ausiliari usano la stessa resource_folder, condividono le thumbs.
    
    Args:
        resource_folder_path: Path relativo (//Resources) o assoluto della resource_folder.
                             Se None, usa cartella temporanea.
    
    Returns:
        Path alla cartella thumbs specifica per questa resource_folder
    """
    blend_path = bpy.data.filepath
    
    # Se non c'è resource_folder, usa temp
    if not resource_folder_path:
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "EM_thumbs_temp"
        temp_dir.mkdir(exist_ok=True)
        return temp_dir
    
    # ✅ CHIAVE: Usa il path RELATIVO ORIGINALE per l'hash (non quello assoluto)
    # Questo garantisce che lo stesso path relativo generi lo stesso hash su PC diversi
    path_for_hash = resource_folder_path.strip()
    
    # Normalizza solo i separatori per consistenza cross-platform
    path_for_hash = path_for_hash.replace('\\', '/')
    
    # Genera hash dal path relativo
    path_hash = hashlib.md5(path_for_hash.encode('utf-8')).hexdigest()[:8]
    
    # Estrai nome cartella dal path relativo
    if path_for_hash.startswith('//'):
        folder_name = os.path.basename(path_for_hash.lstrip('/'))
    else:
        folder_name = os.path.basename(os.path.normpath(path_for_hash))
    
    # Se la cartella è vuota, usa un default
    if not folder_name:
        folder_name = "Resources"
    
    unique_name = f"{folder_name}_{path_hash}"
    
    # Crea thumbs vicino al .blend (o in temp se non salvato)
    if blend_path:
        blend_dir = os.path.dirname(blend_path)
        thumbs_dir = os.path.join(blend_dir, "EM_thumbs", unique_name)
    else:
        import tempfile
        thumbs_dir = os.path.join(tempfile.gettempdir(), "EM_thumbs", unique_name)
    
    # Crea la directory
    os.makedirs(thumbs_dir, exist_ok=True)
    
    return Path(thumbs_dir)

def get_thumbs_path_display(resource_folder_path: str = None) -> str:
    """
    Ritorna una stringa user-friendly per mostrare il path della cartella thumbs nella UI.
    
    Returns:
        Stringa formattata per la UI (es. ".../EM_thumbs/Resources_abc12345")
    """
    if not resource_folder_path:
        return "[Not configured]"
    
    try:
        thumbs_root = em_thumbs_root(resource_folder_path)
        
        # Mostra solo le ultime 2-3 parti del path per brevità
        parts = Path(thumbs_root).parts
        if len(parts) >= 3:
            display = f".../{'/'.join(parts[-3:])}"
        else:
            display = str(thumbs_root)
        
        return display
    except Exception as e:
        return f"[Error: {str(e)}]"

def get_file_hash(file_path: str) -> str:
    """Genera hash SHA1 per il file (per naming cache)"""
    hash_sha1 = hashlib.sha1()
    try:
        with open(file_path, "rb") as f:
            # Leggi in chunks per file grandi
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha1.update(chunk)
        return hash_sha1.hexdigest()
    except (IOError, OSError):
        # Fallback usando solo il path
        hash_sha1.update(file_path.encode('utf-8'))
        return hash_sha1.hexdigest()


def get_thumb_path(file_path: str, thumbs_root: Path) -> Path:
    """Genera percorso per thumbnail usando bucket hash structure"""
    file_hash = get_file_hash(file_path)
    # Crea struttura bucket: ab/cd/hash.png
    bucket_path = thumbs_root / file_hash[:2] / file_hash[2:4]
    bucket_path.mkdir(parents=True, exist_ok=True)
    return bucket_path / f"{file_hash}.png"


def load_index_json(thumbs_root: Path) -> Dict:
    """Carica l'indice JSON dalla cache"""
    index_path = thumbs_root / "index.json"
    if index_path.exists():
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    return {
        "version": 1,
        "items": {}
    }


def save_index_json(thumbs_root: Path, index_data: Dict):
    """Salva l'indice JSON nella cache"""
    index_path = thumbs_root / "index.json"
    try:
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Errore salvando index.json: {e}")


def generate_thumbnail(src_path: str, thumb_path: Path, size: Tuple[int, int] = (256, 256)) -> bool:
    """Genera thumbnail da file immagine/documento"""
    try:
        src_path = bpy.path.abspath(src_path)
        
        if not os.path.exists(src_path):
            print(f"File sorgente non trovato: {src_path}")
            return False
        
        # Estensioni supportate
        ext = os.path.splitext(src_path)[1].lower()
        
        if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tga']:
            # Immagini dirette
            with Image.open(src_path) as img:
                # Converti in RGB se necessario
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Ridimensiona mantenendo aspect ratio
                img_resized = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
                img_resized.save(thumb_path, 'PNG', quality=90)
                return True
        
        elif ext == '.pdf':
            # Per PDF usa preview della prima pagina
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(src_path)
                page = doc[0]
                mat = fitz.Matrix(1.0, 1.0)  # Scala 1:1
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("ppm")
                
                import io
                with Image.open(io.BytesIO(img_data)) as img:
                    img_resized = ImageOps.fit(img, size, Image.Resampling.LANCZOS)
                    img_resized.save(thumb_path, 'PNG', quality=90)
                doc.close()
                return True
            except ImportError:
                print("PyMuPDF non disponibile per PDF thumbnails")
                return create_placeholder_thumb(thumb_path, "PDF", size)

        else:
            # File non supportato - crea placeholder
            return create_placeholder_thumb(thumb_path, ext.upper(), size)
            
    except Exception as e:
        print(f"Errore generando thumbnail per {src_path}: {e}")
        return create_placeholder_thumb(thumb_path, "ERR", size)


def create_placeholder_thumb(thumb_path: Path, text: str, size: Tuple[int, int] = (256, 256)) -> bool:
    """Crea thumbnail placeholder per file non supportati"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Crea immagine placeholder
        img = Image.new('RGB', size, color=(100, 100, 100))
        draw = ImageDraw.Draw(img)
        
        # Tenta di usare font predefinito
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except (IOError, OSError):
            font = ImageFont.load_default()
        
        # Testo centrato
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2
        
        draw.text((x, y), text, fill=(200, 200, 200), font=font)
        
        img.save(thumb_path, 'PNG')
        return True
        
    except Exception as e:
        print(f"Errore creando placeholder: {e}")
        return False


def has_doc_thumbs() -> bool:
    """
    Verifica se esistono thumbnails disponibili per la resource_folder corrente.
    Controlla:
    1. Se c'è un file ausiliario attivo con resource_folder configurata
    2. Se esiste la cartella thumbs per quella resource_folder
    3. Se l'indice contiene almeno una thumbnail
    
    Returns:
        bool: True se ci sono thumbs disponibili, False altrimenti
    """
    try:
        scene = bpy.context.scene
        em_tools = scene.em_tools
        
        # Controlla se c'è un GraphML caricato
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            return False
        
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        
        # Controlla se c'è un file ausiliario attivo
        if not graphml.auxiliary_files or graphml.active_auxiliary_index < 0:
            return False
        
        aux_file = graphml.auxiliary_files[graphml.active_auxiliary_index]
        
        # Controlla se la resource_folder è configurata
        if not aux_file.resource_folder:
            return False
        
        # ✅ USA resolve_resource_folder
        resource_folder = resolve_resource_folder(aux_file.resource_folder)
        
        if not resource_folder or not os.path.exists(resource_folder):
            print(f"⚠️ Resource folder non trovata: {aux_file.resource_folder} → {resource_folder}")
            return False
        
        # Calcola thumbs_root per questa resource_folder
        thumbs_root = em_thumbs_root(resource_folder)
        
        # Carica l'indice
        index_data = load_index_json(thumbs_root)
        
        # Controlla se ci sono items nell'indice
        items = index_data.get("items", {})
        
        if not items:
            return False
        
        # Verifica che almeno una thumbnail esista fisicamente
        for doc_key, item_data in items.items():
            thumb_rel_path = item_data.get("thumb", "")
            if thumb_rel_path:
                thumb_abs_path = thumbs_root / thumb_rel_path
                if thumb_abs_path.exists():
                    return True
        
        return False
        
    except Exception as e:
        print(f"Errore in has_doc_thumbs(): {e}")
        import traceback
        traceback.print_exc()
        return False


# thumb_utils.py - AGGIUNGI QUESTE VARIABILI GLOBALI ALL'INIZIO DEL FILE

# Cache per evitare loop infiniti nel caricamento thumbnails
_cached_us_thumbs = {}  # {us_node_id: [(doc_key, name, desc, icon_id, i), ...]}
_last_us_id = None
_last_resource_folder = None

# ... resto del codice ...

def reload_doc_previews_for_us(us_node_id: str) -> List[Tuple[str, str, str, int, int]]:
    """
    Carica preview filtrate per una specifica US.
    IMPORTANTE: Usa il thumbs_root corretto basato sulla resource_folder.
    ✅ CON CACHE per evitare loop infiniti
    """
    global preview_collections, _cached_us_thumbs, _last_us_id, _last_resource_folder
    
    if not us_node_id:
        return []
    
    try:
        scene = bpy.context.scene
        em_tools = scene.em_tools
        
        # Verifica che ci sia un GraphML attivo
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            return []
        
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        
        # Verifica che ci sia un file ausiliario attivo con resource_folder
        if not graphml.auxiliary_files or graphml.active_auxiliary_index < 0:
            return []
        
        aux_file = graphml.auxiliary_files[graphml.active_auxiliary_index]
        
        if not aux_file.resource_folder:
            return []
                
        # ✅ Usa verbose=True solo se stiamo caricando per la prima volta (non in cache)
        cache_key_temp = f"{us_node_id}_{aux_file.resource_folder}"
        is_first_load = cache_key_temp not in _cached_us_thumbs
        resource_folder = resolve_resource_folder(aux_file.resource_folder, verbose=is_first_load)  
              
        if not resource_folder or not os.path.exists(resource_folder):
            print(f"⚠️ Resource folder non valida: {aux_file.resource_folder}")
            return []
        
        # ✅ CACHE CHECK: Se US e resource_folder non sono cambiati, restituisci cache
        cache_key = f"{us_node_id}_{resource_folder}"
        if cache_key in _cached_us_thumbs:
            # print(f"✓ Usando cache per US {us_node_id[:8]}... ({len(_cached_us_thumbs[cache_key])} thumbs)")
            return _cached_us_thumbs[cache_key]
        
        # Se siamo qui, dobbiamo ricaricare (US cambiato o primo caricamento)
        print(f"🔄 Caricamento thumbnails per US {us_node_id[:8]}...")
        
        thumbs_root = em_thumbs_root(resource_folder)
        
        # Ottieni il grafo
        from s3dgraphy import get_graph
        graph = get_graph(graphml.name)
        
        if not graph:
            return []
        
        # Trova DocumentNode collegati a questa US
        us_document_ids = set()
        for edge in graph.edges:
            if edge.edge_source == us_node_id and edge.edge_type == "generic_connection":
                us_document_ids.add(edge.edge_target)
        
        if not us_document_ids:
            # Nessun documento, salva lista vuota in cache
            _cached_us_thumbs[cache_key] = []
            return []
        
        # Inizializza preview collection se necessario
        if "doc_previews" not in preview_collections:
            pcoll = bpy.utils.previews.new()
            preview_collections["doc_previews"] = pcoll
        else:
            pcoll = preview_collections["doc_previews"]
        
        # Carica indice
        index_data = load_index_json(thumbs_root)
        
        enum_items = []
        i = 0
        
        # Per ogni DocumentNode dell'US, cerca la sua thumbnail
        for doc_id in us_document_ids:
            doc_node = graph.find_node_by_id(doc_id)
            if not doc_node:
                continue
            
            # Trova LinkNode collegati a questo DocumentNode
            for edge in graph.edges:
                if edge.edge_source == doc_id and edge.edge_type == "has_linked_resource":
                    link_node = graph.find_node_by_id(edge.edge_target)
                    
                    if link_node and hasattr(link_node, 'node_type') and link_node.node_type.lower() == 'link':
                        file_url = ''
                        if hasattr(link_node, 'data') and isinstance(link_node.data, dict):
                            file_url = link_node.data.get('url', '')
                        
                        if not file_url:
                            continue
                        
                        # Risoluzione path
                        if os.path.isabs(file_url):
                            file_path = file_url
                        else:
                            file_path = os.path.join(resource_folder, file_url)
                            file_path = os.path.normpath(file_path)
                        
                        if not os.path.exists(file_path):
                            continue
                        
                        # Calcola hash
                        file_hash = get_file_hash(file_path)
                        doc_key = f"doc_{file_hash}"
                        
                        # Cerca nell'indice
                        if doc_key not in index_data.get("items", {}):
                            continue
                        
                        item_data = index_data["items"][doc_key]
                        thumb_rel_path = item_data.get("thumb", "")
                        
                        if not thumb_rel_path:
                            continue
                        
                        thumb_abs_path = thumbs_root / thumb_rel_path
                        
                        if thumb_abs_path.exists():
                            try:
                                if doc_key not in pcoll:
                                    thumb = pcoll.load(doc_key, str(thumb_abs_path), 'IMAGE')
                                    icon_id = thumb.icon_id
                                else:
                                    icon_id = pcoll[doc_key].icon_id
                                
                                src_path = item_data.get("src_path", "")
                                doc_name = os.path.basename(src_path) if src_path else item_data.get("filename", doc_key)
                                
                                enum_items.append((
                                    doc_key,        # identifier
                                    doc_name,       # name
                                    src_path,       # description
                                    icon_id,        # icon
                                    i               # number
                                ))
                                i += 1
                                print(f"  ✓ Caricata thumbnail per {doc_name}")
                                
                            except Exception as e:
                                print(f"  Errore caricando preview per {doc_key}: {e}")
        
        print(f"✅ Caricate {len(enum_items)} thumbnails per l'US")
        
        # ✅ SALVA IN CACHE
        _cached_us_thumbs[cache_key] = enum_items
        
        return enum_items
        
    except Exception as e:
        print(f"Errore in reload_doc_previews_for_us: {e}")
        import traceback
        traceback.print_exc()
        return []

# ✅  FUNZIONE PER PULIRE LA CACHE QUANDO NECESSARIO
def clear_us_thumbs_cache():
    """Pulisce la cache delle thumbnails US. Da chiamare quando si rigenera."""
    global _cached_us_thumbs
    _cached_us_thumbs.clear()
    print("🗑️ Cache thumbnails US pulita")

# ✅ NUOVA FUNZIONE
def clear_resolved_paths_cache():
    """Pulisce la cache dei path risolti. Da chiamare quando cambia il file .blend."""
    global _resolved_paths_cache
    _resolved_paths_cache.clear()
    print("🗑️ Cache path risolti pulita")

# ✅ NUOVA FUNZIONE COMBO
def clear_all_thumbs_caches():
    """Pulisce tutte le cache del sistema thumbnails."""
    clear_us_thumbs_cache()
    clear_resolved_paths_cache()
    print("🧹 Tutte le cache thumbnails pulite")

def reload_doc_previews_from_cache() -> List[Tuple[str, str, str, int, int]]:
    """Carica preview dalla cache per EnumProperty"""
    global preview_collections
    
    thumbs_root = em_thumbs_root()
    
    # Inizializza preview collection se necessario
    if "doc_previews" not in preview_collections:
        pcoll = bpy.utils.previews.new()
        preview_collections["doc_previews"] = pcoll
    else:
        pcoll = preview_collections["doc_previews"]
    
    # Carica indice
    index_data = load_index_json(thumbs_root)
    
    enum_items = []
    i = 0
    
    for doc_key, item_data in index_data.get("items", {}).items():
        thumb_rel_path = item_data.get("thumb", "")
        if not thumb_rel_path:
            continue
            
        thumb_abs_path = thumbs_root / thumb_rel_path
        
        if thumb_abs_path.exists():
            # Carica in preview collection
            try:
                if doc_key not in pcoll:
                    thumb = pcoll.load(doc_key, str(thumb_abs_path), 'IMAGE')
                    icon_id = thumb.icon_id
                else:
                    icon_id = pcoll[doc_key].icon_id
                
                # Nome documento dal src_path
                src_path = item_data.get("src_path", doc_key)
                doc_name = os.path.basename(src_path)
                
                enum_items.append((
                    doc_key,        # identifier
                    doc_name,       # name
                    src_path,       # description
                    icon_id,        # icon
                    i               # number
                ))
                i += 1
                
            except Exception as e:
                print(f"Errore caricando preview per {doc_key}: {e}")
    
    return enum_items


def get_src_path_from_doc_key(doc_key: str) -> Optional[str]:
    """
    Ottiene il percorso originale del documento dal doc_key.
    Ricostruisce il path assoluto dal path relativo salvato nell'indice.
    I path relativi sono relativi alla directory del file .blend.
    
    Args:
        doc_key: Chiave del documento (es. "doc_abc123...")
        
    Returns:
        Path assoluto del file originale, o None se non trovato
    """
    try:
        scene = bpy.context.scene
        em_tools = scene.em_tools
        
        # Ottieni resource_folder per calcolare thumbs_root
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            print(f"get_src_path_from_doc_key: Nessun GraphML caricato")
            return None
        
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        
        if not graphml.auxiliary_files or graphml.active_auxiliary_index < 0:
            print(f"get_src_path_from_doc_key: Nessun file ausiliario")
            return None
        
        aux_file = graphml.auxiliary_files[graphml.active_auxiliary_index]
        
        if not aux_file.resource_folder:
            print(f"get_src_path_from_doc_key: Resource folder non configurata")
            return None
        
        # ✅ USA resolve_resource_folder
        resource_folder = resolve_resource_folder(aux_file.resource_folder)
        
        if not resource_folder:
            print(f"get_src_path_from_doc_key: Impossibile risolvere resource_folder")
            return None
        
        # Carica indice
        thumbs_root = em_thumbs_root(resource_folder)
        index_data = load_index_json(thumbs_root)
        
        # Ottieni src_path dall'indice
        item_data = index_data.get("items", {}).get(doc_key, {})
        relative_src_path = item_data.get("src_path")
        
        if not relative_src_path:
            print(f"get_src_path_from_doc_key: src_path non trovato per {doc_key}")
            return None
        
        # ✅ Ricostruisci path assoluto partendo dalla directory del .blend
        # Controlla se è già assoluto (per retrocompatibilità con vecchi indici)
        if os.path.isabs(relative_src_path):
            # Path assoluto (vecchio formato) - verifica che esista
            if os.path.exists(relative_src_path):
                return relative_src_path
            else:
                print(f"⚠️ Path assoluto non esiste più: {relative_src_path}")
                return None
        else:
            # Path relativo (nuovo formato) - ricostruisci assoluto dal .blend
            blend_path = bpy.data.filepath
            if not blend_path:
                print(f"⚠️ File .blend non salvato, impossibile ricostruire path assoluto")
                return None
            
            blend_dir = os.path.dirname(blend_path)
            absolute_path = os.path.join(blend_dir, relative_src_path)
            absolute_path = os.path.normpath(absolute_path)
            
            if os.path.exists(absolute_path):
                return absolute_path
            else:
                print(f"⚠️ File non trovato: {absolute_path}")
                print(f"     Blend directory: {blend_dir}")
                print(f"     Path relativo: {relative_src_path}")
                return None
    
    except Exception as e:
        print(f"Errore in get_src_path_from_doc_key: {e}")
        import traceback
        traceback.print_exc()
        return None


def cleanup_preview_collections():
    """Pulisce le preview collections e tutte le cache (per unregister)"""
    global preview_collections
    
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
    
    # ✅ Pulisci anche tutte le cache
    clear_all_thumbs_caches()