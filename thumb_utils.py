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


def em_thumbs_root(resource_folder_path: str = None) -> Path:
    """
    Restituisce la cartella thumbnails per una resource_folder specifica.
    Se due file ausiliari usano la stessa resource_folder, condividono le thumbs.
    
    Args:
        resource_folder_path: Path assoluto o relativo della resource_folder.
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
    
    # Converte in path assoluto usando os.path
    abs_resource_path = os.path.abspath(bpy.path.abspath(resource_folder_path))
    
    # Genera hash univoco basato sul path assoluto della resource_folder
    # Se due file ausiliari puntano alla stessa cartella → stesso hash → stesse thumbs
    path_hash = hashlib.md5(abs_resource_path.encode('utf-8')).hexdigest()[:8]
    
    # Nome univoco: NomeCartella_hash
    folder_name = os.path.basename(os.path.normpath(abs_resource_path))
    unique_name = f"{folder_name}_{path_hash}"
    
    # Se il .blend è salvato, thumbs vicino al .blend
    # Altrimenti in temp
    if blend_path:
        blend_dir = os.path.dirname(blend_path)
        thumbs_dir = os.path.join(blend_dir, "EM_thumbs", unique_name)
    else:
        import tempfile
        thumbs_dir = os.path.join(tempfile.gettempdir(), "EM_thumbs", unique_name)
    
    # Crea la directory
    os.makedirs(thumbs_dir, exist_ok=True)
    
    return Path(thumbs_dir)


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


# ============================================================================
# ✅ CORREZIONE 1: has_doc_thumbs() CON RESOURCE_FOLDER
# ============================================================================
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
        
        # ✅ CORREZIONE: Ottieni path assoluto della resource_folder
        resource_folder = os.path.abspath(bpy.path.abspath(aux_file.resource_folder))
        
        if not os.path.exists(resource_folder):
            return False
        
        # ✅ CORREZIONE: Calcola thumbs_root per questa resource_folder
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
        return False


# ============================================================================
# ✅ CORREZIONE 2: reload_doc_previews_for_us() CON RESOURCE_FOLDER
# ============================================================================
def reload_doc_previews_for_us(us_node_id: str) -> List[Tuple[str, str, str, int, int]]:
    """
    Carica preview filtrate per una specifica US.
    IMPORTANTE: Usa il thumbs_root corretto basato sulla resource_folder.
    """
    global preview_collections
    
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
        
        # ✅ CORREZIONE: Calcola thumbs_root usando la resource_folder corretta
        resource_folder = os.path.abspath(bpy.path.abspath(aux_file.resource_folder))
        thumbs_root = em_thumbs_root(resource_folder)
        
        # Ottieni il grafo
        from s3dgraphy import get_graph
        graph = get_graph(graphml.name)
        
        if not graph:
            return []
        
        # Trova DocumentNode collegati a questa US
        us_document_ids = set()
        for edge in graph.edges:
            # ✅ USA "generic_connection" come nel codice di import
            if edge.edge_source == us_node_id and edge.edge_type == "generic_connection":
                us_document_ids.add(edge.edge_target)
        
        if not us_document_ids:
            print(f"Nessun DocumentNode collegato all'US {us_node_id}")
            return []
        
        print(f"Trovati {len(us_document_ids)} DocumentNode per US {us_node_id}")
        
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
            doc_node_id = item_data.get("doc_node_id")
            
            # FILTRA: solo DocumentNode di questa US
            if doc_node_id not in us_document_ids:
                continue
            
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
        
        print(f"Caricate {len(enum_items)} thumbnails per l'US")
        return enum_items
        
    except Exception as e:
        print(f"Errore in reload_doc_previews_for_us: {e}")
        import traceback
        traceback.print_exc()
        return []


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
    """Ottiene il percorso originale del documento dal doc_key"""
    thumbs_root = em_thumbs_root()
    index_data = load_index_json(thumbs_root)
    
    item_data = index_data.get("items", {}).get(doc_key, {})
    return item_data.get("src_path")


def cleanup_preview_collections():
    """Pulisce le preview collections (per unregister)"""
    global preview_collections
    
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()