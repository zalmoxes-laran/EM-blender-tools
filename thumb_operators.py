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
        
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            self.report({'ERROR'}, "Nessun grafo attivo. Carica prima un file GraphML.")
            return {'CANCELLED'}
        
        # Ottieni grafo attivo
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        graph = get_graph(graphml.name)
        
        if not graph:
            self.report({'ERROR'}, "Impossibile accedere al grafo.")
            return {'CANCELLED'}
        
        # Setup cartelle
        thumbs_root = em_thumbs_root()
        
        # Ottieni cartella risorse base
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            self.report({'ERROR'}, "Nessun file GraphML attivo")
            return {'CANCELLED'}
            
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        
        if not graphml.auxiliary_files or graphml.active_auxiliary_index < 0:
            self.report({'ERROR'}, "Nessun file ausiliario configurato. Vai in EMsetup → File ausiliari")
            return {'CANCELLED'}
            
        aux_file = graphml.auxiliary_files[graphml.active_auxiliary_index]
        
        if not aux_file.resource_folder:
            self.report({'ERROR'}, "Cartella risorse non configurata. Vai in EMsetup → File ausiliari e imposta 'Resource Folder'")
            return {'CANCELLED'}
        
        base_resource_folder = Path(bpy.path.abspath(aux_file.resource_folder))
        if not base_resource_folder.exists():
            self.report({'ERROR'}, f"Cartella risorse non trovata: {base_resource_folder}")
            return {'CANCELLED'}
        
        # Carica indice esistente
        index_data = load_index_json(thumbs_root)
        
        # Conta DocumentNode processati
        processed_count = 0
        generated_count = 0
        
        # Trova tutti i DocumentNode nel grafo
        for node in graph.nodes:
            if hasattr(node, 'node_type') and node.node_type == 'document':
                # Trova LinkNode collegati
                linked_resources = self._get_linked_resources(graph, node.node_id)
                
                for link_node in linked_resources:
                    processed_count += 1
                    
                    # Percorso assoluto del file originale
                    src_path = bpy.path.abspath(link_node.data.get("url", ""))
                    
                    if not src_path:
                        print(f"LinkNode {link_node.node_id} non ha URL valido")
                        continue
                                        
                    if not os.path.exists(src_path):
                        print(f"File non trovato: {src_path}")
                        continue
                    
                    # Genera chiave per l'indice (usa node_id del DocumentNode)
                    # ✅ NUOVO: Genera chiave basata su percorso file per evitare duplicati
                    file_hash = get_file_hash(src_path)
                    doc_key = f"doc_{file_hash}"
                    
                    # ✅ Aggiorna/sovrascrivi se esiste già
                    needs_regen = True
                    if doc_key in index_data["items"]:
                        stored_item = index_data["items"][doc_key]
                        stored_mtime = stored_item.get("src_mtime", 0)
                        current_mtime = os.path.getmtime(src_path)
                        
                        if thumb_path.exists() and stored_mtime >= current_mtime:
                            needs_regen = False
                            print(f"Thumbnail già aggiornata per: {node.name}")                    
                    # Ottieni percorso thumbnail
                    thumb_path = get_thumb_path(src_path, thumbs_root)
                    
                    # Controlla se rigenerare
                    needs_regen = True
                    if doc_key in index_data["items"]:
                        stored_item = index_data["items"][doc_key]
                        stored_mtime = stored_item.get("src_mtime", 0)
                        current_mtime = os.path.getmtime(src_path)
                        
                        if thumb_path.exists() and stored_mtime >= current_mtime:
                            needs_regen = False
                    
                    if needs_regen:
                        # Genera thumbnail
                        if generate_thumbnail(src_path, thumb_path):
                            generated_count += 1
                            
                            # Aggiorna/sovrascrivi indice (evita duplicati)
                            thumb_rel_path = thumb_path.relative_to(thumbs_root)
                            index_data["items"][doc_key] = {
                                "thumb": str(thumb_rel_path).replace("\\", "/"),
                                "src_path": src_path,
                                "src_mtime": os.path.getmtime(src_path),
                                "src_size": os.path.getsize(src_path),
                                "doc_node_id": node.node_id,
                                "doc_name": node.name,
                                "file_hash": file_hash  # ✅ Aggiungi hash per debug
                            }
                            
                            print(f"Generata thumbnail per: {node.name}")
                        else:
                            print(f"Errore generando thumbnail per: {node.name}")
        
        # Salva indice aggiornato
        save_index_json(thumbs_root, index_data)
        
        # Ricarica preview per UI
        reload_doc_previews_from_cache()
        
        # Report risultati
        if generated_count > 0:
            self.report({'INFO'}, f"Generate {generated_count} thumbnails su {processed_count} documenti processati")
        else:
            self.report({'INFO'}, f"Tutte le {processed_count} thumbnails erano già aggiornate")
        
        return {'FINISHED'}
            
    def _get_linked_resources(self, graph, doc_node_id):
        """Trova LinkNode collegati a un DocumentNode"""
        linked_resources = []
        
        print(f"DEBUG: Cercando LinkNode per DocumentNode {doc_node_id}")
        
        # Debug: elenca tutti gli edge dal DocumentNode
        edges_from_doc = [e for e in graph.edges if e.edge_source == doc_node_id]
        print(f"DEBUG: Trovati {len(edges_from_doc)} edge dal DocumentNode")
        
        for edge in edges_from_doc:
            print(f"DEBUG: Edge tipo '{edge.edge_type}' verso {edge.edge_target}")
            
            if edge.edge_type == "has_linked_resource":
                target_node = graph.find_node_by_id(edge.edge_target)
                if target_node:
                    print(f"DEBUG: Target node tipo: {getattr(target_node, 'node_type', 'UNKNOWN')}")
                    if hasattr(target_node, 'node_type') and target_node.node_type == 'link':
                        linked_resources.append(target_node)
                        # ✅ CORRETTO: l'URL è in target_node.data["url"]
                        url = target_node.data.get("url", "NO_URL") if hasattr(target_node, 'data') else "NO_DATA"
                        print(f"DEBUG: Aggiunto LinkNode: {url}")
        
        print(f"DEBUG: Totale LinkNode trovati: {len(linked_resources)}")
        return linked_resources


class EMTOOLS_OT_open_doc_thumbs_folder(Operator):
    """Apre la cartella delle thumbnails"""
    bl_idname = "emtools.open_doc_thumbs_folder"
    bl_label = "Apri cartella thumbs"
    bl_description = "Apre la cartella EM_thumbs nel file manager"
    bl_options = {'REGISTER'}

    def execute(self, context):
        thumbs_root = em_thumbs_root()
        
        if not thumbs_root.exists():
            self.report({'ERROR'}, "Cartella thumbnails non esiste ancora")
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
    
    doc_key: bpy.props.StringProperty()

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
    
    doc_key: bpy.props.StringProperty()

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
