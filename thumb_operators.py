# thumb_operators.py
"""
Operatori per la gestione delle thumbnails in EM-Tools
"""

import os
import subprocess
from pathlib import Path
import bpy
from bpy.types import Operator
from s3dgraphy import get_graph
from .thumb_utils import (
    em_thumbs_root, load_index_json, save_index_json, 
    generate_thumbnail, get_thumb_path, reload_doc_previews_from_cache,
    get_file_hash  
)

class EMTOOLS_OT_build_doc_thumbs(Operator):
    """Genera/rigenera thumbnails per tutti i DocumentNode della scena"""
    bl_idname = "emtools.build_doc_thumbs"
    bl_label = "(Ri)genera thumbnails"
    bl_description = "Scansiona i DocumentNode e genera thumbnails nella cache locale"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        
        # ✅ NUOVO APPROCCIO: Non serve il grafo, solo la resource_folder
        # Ottieni file ausiliare attivo per prendere la resource_folder
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            self.report({'ERROR'}, "Carica prima un file GraphML per configurare la resource_folder")
            return {'CANCELLED'}
            
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        
        if not graphml.auxiliary_files or graphml.active_auxiliary_index < 0:
            self.report({'ERROR'}, "Nessun file ausiliario configurato. Vai in EMsetup → File ausiliari")
            return {'CANCELLED'}
            
        aux_file = graphml.auxiliary_files[graphml.active_auxiliary_index]
        
        if not aux_file.resource_folder:
            self.report({'ERROR'}, "Cartella risorse non configurata. Vai in EMsetup → File ausiliari e imposta 'Resource Folder'")
            return {'CANCELLED'}
        
        # Converti in path assoluto usando os.path
        resource_folder = os.path.abspath(bpy.path.abspath(aux_file.resource_folder))
        
        if not os.path.exists(resource_folder):
            self.report({'ERROR'}, f"Cartella risorse non trovata: {resource_folder}")
            return {'CANCELLED'}
        
        # Setup cartella thumbs univoca per questa resource_folder
        thumbs_root = em_thumbs_root(resource_folder)
        
        print(f"Generazione thumbs da: {resource_folder}")
        print(f"Thumbs salvate in: {thumbs_root}")
        
        # Carica indice esistente
        index_data = load_index_json(thumbs_root)
        
        # Contatori
        total_images_found = 0
        thumbs_generated = 0
        thumbs_skipped = 0
        thumbs_errors = 0
        
        # Formati supportati
        supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.pdf'}
        
        # Scansiona TUTTE le immagini nella resource_folder (ricorsivamente)
        print(f"Scansionando cartella: {resource_folder}")
        
        for root, dirs, files in os.walk(resource_folder):
            for filename in files:
                file_path = os.path.join(root, filename)
                file_ext = os.path.splitext(filename)[1].lower()
                
                # Salta se non è un formato supportato
                if file_ext not in supported_formats:
                    continue
                
                total_images_found += 1
                
                # Genera chiave univoca basata sul file
                file_hash = get_file_hash(file_path)
                doc_key = f"doc_{file_hash}"
                
                # Ottieni percorso thumbnail
                thumb_path = get_thumb_path(file_path, thumbs_root)
                
                # Controlla se serve rigenerare
                needs_regen = True
                if doc_key in index_data["items"]:
                    stored_item = index_data["items"][doc_key]
                    stored_mtime = stored_item.get("src_mtime", 0)
                    
                    try:
                        current_mtime = os.path.getmtime(file_path)
                        
                        # DEBUG: Stampa informazioni
                        print(f"CHECK: {filename}")
                        print(f"  - Chiave: {doc_key}")
                        print(f"  - Thumb exists: {thumb_path.exists()}")
                        print(f"  - Stored mtime: {stored_mtime}")
                        print(f"  - Current mtime: {current_mtime}")
                        print(f"  - Thumb path: {thumb_path}")
                        
                        if thumb_path.exists() and stored_mtime >= current_mtime:
                            needs_regen = False
                            thumbs_skipped += 1
                            print(f"  → SKIP (già aggiornata)")
                        else:
                            print(f"  → REGEN (da aggiornare)")
                    except OSError as e:
                        # File non accessibile
                        print(f"  → ERROR: {e}")
                        thumbs_errors += 1
                        continue
                else:
                    print(f"NEW: {filename} (chiave {doc_key} non in indice)")
                
                # Genera thumbnail se necessario
                if needs_regen:
                    try:
                        if generate_thumbnail(file_path, thumb_path):
                            thumbs_generated += 1
                            
                            # Aggiorna indice
                            thumb_rel_path = thumb_path.relative_to(thumbs_root)
                            index_data["items"][doc_key] = {
                                "thumb": str(thumb_rel_path).replace("\\", "/"),
                                "src_path": file_path,
                                "src_mtime": os.path.getmtime(file_path),
                                "src_size": os.path.getsize(file_path),
                                "file_hash": file_hash,
                                "filename": filename
                            }
                            
                            if thumbs_generated % 10 == 0:  # Log ogni 10
                                print(f"Generate {thumbs_generated} thumbnails...")
                        else:
                            thumbs_errors += 1
                            print(f"Errore generando: {filename}")
                    except Exception as e:
                        thumbs_errors += 1
                        print(f"Errore su {filename}: {e}")
        
        # Salva indice aggiornato
        save_index_json(thumbs_root, index_data)
        
        # Ricarica preview per UI (opzionale, dipende se serve)
        try:
            reload_doc_previews_from_cache()
        except:
            pass  # Potrebbe fallire se il grafo non è caricato
        
        # Report finale dettagliato
        total_processed = thumbs_generated + thumbs_skipped
        
        if total_images_found == 0:
            self.report({'WARNING'}, f"Nessuna immagine trovata in: {os.path.basename(resource_folder)}")
        elif thumbs_generated > 0:
            self.report({'INFO'}, 
                    f"✓ Create {thumbs_generated} nuove thumbnails | "
                    f"{thumbs_skipped} già aggiornate | "
                    f"{thumbs_errors} errori | "
                    f"Totale immagini: {total_images_found}")
        else:
            self.report({'INFO'}, 
                    f"✓ Tutte le {total_processed} thumbnails erano già aggiornate | "
                    f"Totale immagini: {total_images_found}")
        
        return {'FINISHED'}
    
class EMTOOLS_OT_open_doc_thumbs_folder(Operator):
    """Apre la cartella delle thumbnails"""
    bl_idname = "emtools.open_doc_thumbs_folder"
    bl_label = "Apri cartella thumbs"
    bl_description = "Apre la cartella EM_thumbs nel file manager"
    bl_options = {'REGISTER'}

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        
        # Ottieni resource_folder dal file ausiliare attivo
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            self.report({'ERROR'}, "Carica prima un file GraphML")
            return {'CANCELLED'}
            
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        
        if not graphml.auxiliary_files or graphml.active_auxiliary_index < 0:
            self.report({'ERROR'}, "Nessun file ausiliario attivo")
            return {'CANCELLED'}
            
        aux_file = graphml.auxiliary_files[graphml.active_auxiliary_index]
        
        if not aux_file.resource_folder:
            self.report({'ERROR'}, "Resource folder non configurata")
            return {'CANCELLED'}
        
        # Converti in path assoluto
        resource_folder = os.path.abspath(bpy.path.abspath(aux_file.resource_folder))
        
        # Ottieni la cartella thumbs CORRETTA
        thumbs_root = em_thumbs_root(resource_folder)
        
        if not thumbs_root.exists():
            self.report({'ERROR'}, f"Cartella thumbnails non esiste ancora: {thumbs_root}")
            return {'CANCELLED'}
        
        thumbs_path = str(thumbs_root)
        
        try:
            # Prova prima il metodo di Blender
            res = bpy.ops.wm.path_open(filepath=thumbs_path)
            if res == {"FINISHED"}:
                return {'FINISHED'}
        except:
            pass
        
        try:
            # Windows
            subprocess.Popen(['explorer', thumbs_path])
        except:
            try:
                # macOS
                subprocess.call(['open', thumbs_path])
            except:
                try:
                    # Linux
                    subprocess.call(['xdg-open', thumbs_path])
                except:
                    self.report({'ERROR'}, f"Impossibile aprire cartella. Naviga manualmente a: {thumbs_path}")
                    return {'CANCELLED'}
        
        return {'FINISHED'}


class EMTOOLS_OT_select_doc_from_thumb(Operator):
    """Seleziona DocumentNode dalla thumbnail cliccata"""
    bl_idname = "emtools.select_doc_from_thumb"
    bl_label = "Seleziona documento"
    bl_description = "Seleziona il DocumentNode corrispondente a questa thumbnail"
    bl_options = {'REGISTER', 'UNDO'}
    
    doc_key: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        if not self.doc_key:
            return {'CANCELLED'}
        
        # Trova il DocumentNode corrispondente
        thumbs_root = em_thumbs_root()
        index_data = load_index_json(thumbs_root)
        
        item_data = index_data.get("items", {}).get(self.doc_key, {})
        doc_node_id = item_data.get("doc_node_id")
        
        if not doc_node_id:
            self.report({'WARNING'}, "DocumentNode non trovato per questa thumbnail")
            return {'CANCELLED'}
        
        # TODO: Implementa selezione del nodo nella UI
        # Questo dipenderà da come gestisci la selezione nel tuo UI manager
        print(f"Selezionato DocumentNode: {doc_node_id}")
        
        self.report({'INFO'}, f"Selezionato documento: {item_data.get('doc_name', 'Sconosciuto')}")
        return {'FINISHED'}


class EMTOOLS_OT_open_original_doc(Operator):
    """Apre il documento originale dal percorso del LinkNode"""
    bl_idname = "emtools.open_original_doc"
    bl_label = "Apri originale"
    bl_description = "Apre il documento originale usando il percorso memorizzato nel LinkNode"
    bl_options = {'REGISTER'}
    
    doc_key: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        if not self.doc_key:
            return {'CANCELLED'}
        
        # Ottieni percorso originale
        from .thumb_utils import get_src_path_from_doc_key
        src_path = get_src_path_from_doc_key(self.doc_key)
        
        if not src_path or not os.path.exists(src_path):
            self.report({'ERROR'}, "File originale non trovato")
            return {'CANCELLED'}
        
        try:
            # Apri con applicazione predefinita del sistema
            if os.name == 'nt':  # Windows
                os.startfile(src_path)
            elif os.name == 'posix':  # macOS e Linux
                subprocess.call(['open', src_path] if os.uname().sysname == 'Darwin' 
                              else ['xdg-open', src_path])
            
            self.report({'INFO'}, f"Aperto: {os.path.basename(src_path)}")
            
        except Exception as e:
            self.report({'ERROR'}, f"Errore aprendo file: {e}")
            return {'CANCELLED'}
        
        return {'FINISHED'}


# Lista operatori per registrazione
classes = [
    EMTOOLS_OT_build_doc_thumbs,
    EMTOOLS_OT_open_doc_thumbs_folder,
    EMTOOLS_OT_select_doc_from_thumb,
    EMTOOLS_OT_open_original_doc,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
