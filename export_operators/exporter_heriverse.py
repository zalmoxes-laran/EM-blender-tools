import bpy
from bpy.props import BoolProperty, StringProperty, IntProperty # type: ignore
from bpy.types import Operator, AddonPreferences, Panel # type: ignore
from bpy_extras.io_utils import ExportHelper # type: ignore
from ..s3Dgraphy.exporter.json_exporter import JSONExporter
from bpy_extras.io_utils import ExportHelper # type: ignore
import os
import shutil

from ..s3Dgraphy import get_graph, get_all_graph_ids
from ..functions import *
from ..graph_updaters import *

from ..s3Dgraphy.nodes.link_node import LinkNode

def clean_filename(filename: str) -> str:
    """
    Clean filename from invalid characters and spaces.
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: Cleaned filename safe for filesystem use
    """
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
        
    # Remove any other non-ASCII characters
    filename = ''.join(c for c in filename if c.isascii())
        
    return filename

class JSON_OT_exportEMformat(Operator, ExportHelper):
    """Export project data in Heriverse JSON format"""
    bl_idname = "export.heriversejson"
    bl_label = "Export Heriverse JSON"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".json"

    use_file_dialog: BoolProperty(
        name="Use File Dialog",
        description="Use the file dialog to choose where to save the JSON",
        default=True
    ) # type: ignore

    filepath: StringProperty(
        name="File Path",
        description="Path to save the JSON file",
        default=""
    ) # type: ignore

    def invoke(self, context, event):
        if self.use_file_dialog:
            return ExportHelper.invoke(self, context, event)
        else:
            return self.execute(context)

    def execute(self, context):
        print("\n=== Starting Heriverse JSON Export ===")
        try:
            # Crea l'esportatore con il percorso file specificato
            from ..s3Dgraphy.exporter.json_exporter import JSONExporter
            exporter = JSONExporter(self.filepath)
            
            print(f"Created JSONExporter for path: {self.filepath}")

            # Esporta tutti i grafi
            exporter.export_graphs()
            print("Graphs exported successfully")
            
            self.report({'INFO'}, f"Heriverse data successfully exported to {self.filepath}")
            return {'FINISHED'}
            
        except Exception as e:
            print(f"Error during JSON export: {str(e)}")
            import traceback
            print(traceback.format_exc())
            self.report({'ERROR'}, f"Error during export: {str(e)}")
            return {'CANCELLED'}

class HERIVERSE_OT_export(Operator):
    """Export project in Heriverse format"""
    bl_idname = "export.heriverse"
    bl_label = "Export Heriverse Project"
    bl_description = "Export project in Heriverse format with models, proxies and documentation"
    bl_options = {'REGISTER', 'UNDO'}


    def __init__(self):
        super().__init__()
        self.instanced_objects = set()
        self.exported_models = {}
        self.stato_collezioni = {}

    def export_proxies(self, context, export_folder):
        """Export proxy models"""
        scene = context.scene
        
        # Deseleziona tutto prima di iniziare
        bpy.ops.object.select_all(action='DESELECT')
        
        exported_count = 0
        for em in scene.em_list:
            proxy = bpy.data.objects.get(em.name)
            if proxy and proxy.type == 'MESH':
                proxy.select_set(True)
                name = clean_filename(em.name)
                export_file = os.path.join(export_folder, name)
                
                try:
                    bpy.ops.export_scene.gltf(
                        filepath=str(export_file),
                        export_format='GLB',
                        export_materials='NONE',
                        use_selection=True,
                        export_apply=True
                    )
                    exported_count += 1
                    print(f"Exported proxy: {name}")
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to export proxy {em.name}: {str(e)}")
                
                proxy.select_set(False)
        
        self.report({'INFO'}, f"Exported {exported_count} proxies")
        return exported_count > 0

    # Function to export tilesets
    def export_tilesets(self, context, export_folder):
        """Export Cesium tileset files"""
        print("\n--- Exporting Cesium Tilesets ---")
        
        # Create tilesets directory if it doesn't exist
        os.makedirs(export_folder, exist_ok=True)
        
        # Get export variables
        export_vars = context.window_manager.export_vars
        
        # Ottieni il grafo attivo
        graph = None
        if hasattr(context.scene, 'em_tools') and context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        # Find all tileset objects
        tileset_objects = [obj for obj in bpy.data.objects if "tileset_path" in obj]
        
        # If no tilesets, return early
        if not tileset_objects:
            print("No tileset objects found in scene")
            return 0
        
        exported_count = 0
        skipped_count = 0
        
        # Process each tileset
        for obj in tileset_objects:
            # Verifica se l'oggetto è pubblicabile
            is_publishable = True
            for rm_item in context.scene.rm_list:
                if rm_item.name == obj.name:
                    is_publishable = rm_item.is_publishable
                    break
            
            if not is_publishable:
                print(f"Skipping tileset {obj.name} (not publishable)")
                continue
                
            try:
                tileset_path = obj["tileset_path"]
                if not tileset_path:
                    print(f"Skipping tileset {obj.name} (empty path)")
                    continue
                    
                # Percorso assoluto
                abs_path = bpy.path.abspath(tileset_path)
                
                if not os.path.exists(abs_path):
                    self.report({'WARNING'}, f"Tileset file not found: {abs_path}")
                    continue
                    
                # Nome del file senza estensione
                filename = os.path.basename(abs_path)
                tileset_name = os.path.splitext(filename)[0]
                
                # Crea directory per questo tileset
                tileset_dir = os.path.join(export_folder, tileset_name)
                os.makedirs(tileset_dir, exist_ok=True)
                
                # Verifica se il tileset è già stato estratto
                tileset_json_path = os.path.join(tileset_dir, "tileset.json")
                tileset_extracted = False
                
                if export_vars.heriverse_skip_extracted_tilesets and os.path.exists(tileset_json_path):
                    print(f"Skipping extraction of tileset '{filename}' (already extracted)")
                    skipped_count += 1
                    tileset_extracted = True
                else:
                    # Estrai il file ZIP
                    print(f"Extracting tileset '{filename}' - this may take some time...")
                    import zipfile
                    with zipfile.ZipFile(abs_path, 'r') as zip_ref:
                        zip_ref.extractall(tileset_dir)
                    print(f"Extracted tileset: {obj.name} -> {tileset_dir}")
                    exported_count += 1
                    tileset_extracted = True
                
                # Se il tileset è stato estratto correttamente (o era già estratto),
                # aggiorna o crea il nodo Link nel grafo
                if tileset_extracted and graph:
                    model_node_id = f"{obj.name}_model"
                    model_node = graph.find_node_by_id(model_node_id)
                    
                    if model_node:
                        # Percorso relativo al tileset.json
                        relative_tileset_path = f"tilesets/{tileset_name}/tileset.json"
                        
                        # Aggiorna l'URL nel nodo RM
                        model_node.url = relative_tileset_path
                        
                        # Assicurati che ci sia la trasformazione per orientare correttamente il tileset
                        if not hasattr(model_node, 'data'):
                            model_node.data = {}
                        
                        if 'transform' not in model_node.data:
                            model_node.data['transform'] = {
                                'rotation': ["-1.57079632679", "0.0", "0.0"]  # -90 gradi in radianti
                            }
                        
                        # Crea o aggiorna il nodo Link
                        link_node_id = f"{model_node_id}_link"
                        link_node = LinkNode(
                            node_id=link_node_id,
                            name=f"Tileset Link for {obj.name}",
                            description=f"Link to Cesium tileset for {obj.name}",
                            url=relative_tileset_path,
                            url_type="3d_model"
                        )
                        
                        # Aggiungi o aggiorna il nodo nel grafo
                        existing_link = graph.find_node_by_id(link_node_id)
                        if existing_link:
                            existing_link.url = relative_tileset_path
                            print(f"Updated existing link node for tileset: {obj.name}")
                        else:
                            graph.add_node(link_node)
                            print(f"Created new link node for tileset: {obj.name}")
                            
                            # Crea l'edge tra il nodo RM e il LinkNode
                            edge_id = f"{model_node_id}_has_linked_resource_{link_node_id}"
                            if not graph.find_edge_by_id(edge_id):
                                graph.add_edge(
                                    edge_id=edge_id,
                                    edge_source=model_node_id,
                                    edge_target=link_node_id,
                                    edge_type="has_linked_resource"
                                )
                        
            except Exception as e:
                self.report({'WARNING'}, f"Failed to export tileset {obj.name}: {str(e)}")
                import traceback
                traceback.print_exc()

        # Mostra un resoconto
        if exported_count > 0 or skipped_count > 0:
            self.report({'INFO'}, f"Tilesets: {exported_count} extracted, {skipped_count} skipped (already extracted)")
        
        return exported_count + skipped_count

    # Miglioramento della funzione export_panorama
    def export_panorama(self, context, project_path):
        """Export default panorama (defsky.jpg) to the project"""
        scene = context.scene
        
        if not scene.heriverse_export_panorama:
            return False
            
        try:
            # Create panorama directory
            panorama_path = os.path.join(project_path, "panorama")
            os.makedirs(panorama_path, exist_ok=True)
            
            # Get addon path to find resources
            addon_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            resources_path = os.path.join(addon_path, "resources")
            
            # Cerca in diversi percorsi possibili per trovare defsky.jpg
            possible_paths = [
                os.path.join(resources_path, "panorama", "defsky.jpg"),
                os.path.join(resources_path, "defsky.jpg"),
                os.path.join(addon_path, "panorama", "defsky.jpg"),
                os.path.join(addon_path, "defsky.jpg")
            ]
            
            source_file = None
            for path in possible_paths:
                if os.path.exists(path):
                    source_file = path
                    break
                    
            if not source_file:
                # Se non troviamo il file, creiamo un'immagine di segnaposto
                self.report({'WARNING'}, "Default panorama file not found, creating placeholder")
                
                # Crea un'immagine vuota
                img = bpy.data.images.new("defsky", 1024, 512)
                img.filepath = os.path.join(panorama_path, "defsky.jpg")
                img.file_format = 'JPEG'
                img.save()
                
                return True
                
            # Copy the file
            dest_file = os.path.join(panorama_path, "defsky.jpg")
            shutil.copy2(source_file, dest_file)
            print(f"Copied default panorama from {source_file} to {dest_file}")
            return True
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export panorama: {str(e)}")
            return False

    def compress_textures_in_folder(self, folder_path, scene):
        """
        Compresses all textures in a folder and its subfolders in a single pass.
        
        Args:
            folder_path (str): Path to the folder containing textures to compress
            scene (bpy.types.Scene): Blender scene containing compression settings
        """
        if not scene.heriverse_enable_compression:
            return
            
        # Import required libraries
        import os
        
        try:
            # Import Pillow
            from PIL import Image
            
            print(f"\n=== Compressing all textures in {folder_path} ===")
            
            # Settings
            max_res = scene.heriverse_texture_max_res
            quality = scene.heriverse_texture_quality
            
            # Track statistics
            total_processed = 0
            total_resized = 0
            total_size_before = 0
            total_size_after = 0
            
            # Process all image files in the directory and subdirectories
            for root, dirs, files in os.walk(folder_path):
                for filename in files:
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.tga')):
                        file_path = os.path.join(root, filename)
                        
                        try:
                            # Get original file size
                            file_size_before = os.path.getsize(file_path)
                            total_size_before += file_size_before
                            
                            # Open the image with Pillow
                            img = Image.open(file_path)
                            
                            # Check if resizing is needed
                            width, height = img.size
                            needs_resize = max(width, height) > max_res
                            
                            if needs_resize:
                                # Calculate new dimensions while preserving aspect ratio
                                if width > height:
                                    new_width = max_res
                                    new_height = int(height * (max_res / width))
                                else:
                                    new_height = max_res
                                    new_width = int(width * (max_res / height))
                                    
                                # Use high-quality resampling
                                img = img.resize((new_width, new_height), Image.LANCZOS)
                                total_resized += 1
                            
                            # Save with appropriate format and compression
                            if img.mode == 'RGBA' and filename.lower().endswith('.png'):
                                # Save as PNG with compression for transparency
                                img.save(file_path, 'PNG', optimize=True)
                            else:
                                # Convert to RGB if needed and save as JPEG
                                if img.mode != 'RGB':
                                    img = img.convert('RGB')
                                img.save(file_path, 'JPEG', quality=quality, optimize=True)
                            
                            # Get new file size
                            file_size_after = os.path.getsize(file_path)
                            total_size_after += file_size_after
                            
                            total_processed += 1
                            
                        except Exception as e:
                            print(f"Error processing {filename}: {str(e)}")
            
            # Calculate size reduction
            size_reduction_mb = (total_size_before - total_size_after) / (1024 * 1024)
            percentage_reduction = ((total_size_before - total_size_after) / total_size_before * 100) if total_size_before > 0 else 0
            
            print(f"Texture compression summary:")
            print(f"- Total textures processed: {total_processed}")
            print(f"- Textures resized: {total_resized}")
            print(f"- Size before: {total_size_before / (1024 * 1024):.2f} MB")
            print(f"- Size after: {total_size_after / (1024 * 1024):.2f} MB")
            print(f"- Size reduction: {size_reduction_mb:.2f} MB ({percentage_reduction:.1f}%)")
            
            return total_processed
            
        except ImportError:
            print("PIL (Pillow) library not available, skipping texture compression")
            return 0
        except Exception as e:
            print(f"Error during texture compression: {str(e)}")
            import traceback
            traceback.print_exc()
            return 0

    # Modifica alla funzione export_rm per supportare GPU instances
    def export_rm(self, context, export_folder):
        """Export representation models with GPU instancing support"""
        scene = context.scene
        export_vars = context.window_manager.export_vars
                
        # Deseleziona tutto prima di iniziare
        bpy.ops.object.select_all(action='DESELECT')
        
        # Raggruppa gli oggetti per mesh condivisa
        mesh_groups = {}
        self.instanced_objects = set()
        self.exported_models = {}

        # Step 1: Raccogli tutti gli oggetti RM pubblicabili
        publishable_rm_objects = []
        for obj in bpy.data.objects:
            # Skip oggetti che non sono mesh o non hanno epoche
            if not (obj.type == 'MESH' and hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0):
                continue
                
            # Skip se oggetto è un tileset
            if "tileset_path" in obj:
                continue
                
            # Skip se oggetto non è pubblicabile
            is_publishable = True
            for rm_item in scene.rm_list:
                if rm_item.name == obj.name:
                    is_publishable = rm_item.is_publishable
                    break
                    
            if not is_publishable:
                continue
                
            publishable_rm_objects.append(obj)
        
        # Step 2: Raggruppa per mesh condivisa (solo se GPU instancing è abilitato)
        if export_vars.heriverse_use_gpu_instancing:
            for obj in publishable_rm_objects:
                if obj.data:
                    mesh_name = obj.data.name
                    if mesh_name not in mesh_groups:
                        mesh_groups[mesh_name] = []
                    mesh_groups[mesh_name].append(obj)
        else:
            # Se GPU instancing è disabilitato, ogni oggetto va da solo
            for obj in publishable_rm_objects:
                mesh_name = f"{obj.name}_unique"
                mesh_groups[mesh_name] = [obj]
        
        print(f"Found {len(mesh_groups)} different meshes in {len(publishable_rm_objects)} publishable RM objects")
        
        # Ottieni il grafo attivo
        graph = None
        if context.scene.em_tools.active_file_index >= 0:
            graphml = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
            graph = get_graph(graphml.name)
        
        exported_count = 0
        
        # Step 3: Process each group
        for mesh_name, objects in mesh_groups.items():
            if len(objects) == 1 or not export_vars.heriverse_use_gpu_instancing:
                # Single object, export normally
                obj = objects[0]
                try:
                    # Make sure object is visible
                    was_hidden = obj.hide_viewport
                    if was_hidden:
                        obj.hide_viewport = False
                    
                    obj.select_set(True)
                    export_file = os.path.join(export_folder, clean_filename(obj.name))
                    
                    bpy.ops.export_scene.gltf(
                        filepath=str(export_file),
                        export_format='GLTF_SEPARATE',
                        export_copyright=scene.EMviq_model_author_name if hasattr(scene, 'EMviq_model_author_name') else "",
                        export_texcoords=True,
                        export_normals=True,
                        export_draco_mesh_compression_enable=export_vars.heriverse_use_draco,
                        export_draco_mesh_compression_level=export_vars.heriverse_draco_level,
                        export_materials='EXPORT',
                        use_selection=True,
                        export_apply=True,
                        export_image_format='AUTO',
                        export_texture_dir="",
                        export_keep_originals=False,
                        check_existing=False
                    )
                    
                    # Crea o aggiorna il nodo Link
                    if graph:
                        model_node_id = f"{obj.name}_model"
                        model_node = graph.find_node_by_id(model_node_id)
                        
                        if model_node:
                            # Percorso relativo per l'export
                            gltf_path = f"models/{clean_filename(obj.name)}.gltf"
                            
                            # Crea un nuovo LinkNode
                            link_node_id = f"{model_node_id}_link"
                            link_node = LinkNode(
                                node_id=link_node_id,
                                name=f"GLTF Link for {obj.name}",
                                description=f"Link to exported GLTF for {obj.name}",
                                url=gltf_path,
                                url_type="3d_model"
                            )
                            
                            # Aggiungi o aggiorna il nodo nel grafo
                            existing_link = graph.find_node_by_id(link_node_id)
                            if existing_link:
                                existing_link.url = gltf_path
                            else:
                                graph.add_node(link_node)
                                
                                # Crea l'edge tra il nodo RM e il LinkNode
                                edge_id = f"{model_node_id}_has_linked_resource_{link_node_id}"
                                if not graph.find_edge_by_id(edge_id):
                                    graph.add_edge(
                                        edge_id=edge_id,
                                        edge_source=model_node_id,
                                        edge_target=link_node_id,
                                        edge_type="has_linked_resource"
                                    )
                    
                    # Reset visibility
                    obj.hide_viewport = was_hidden
                    obj.select_set(False)
                    
                    exported_count += 1
                    print(f"Exported RM: {obj.name}")
                    
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to export RM {obj.name}: {str(e)}")
                    obj.select_set(False)
            
            elif len(objects) > 1 and export_vars.heriverse_use_gpu_instancing:
                # Multiple objects with same mesh - instancing enabled
                try:
                    # Step 3.1: Deselect all
                    bpy.ops.object.select_all(action='DESELECT')
                    
                    # Step 3.2: Find most suitable primary object for this group
                    # Preferisci oggetti con nomi più corti o senza numeri alla fine
                    sorted_objects = sorted(objects, key=lambda obj: (len(obj.name), obj.name))
                    primary_obj = sorted_objects[0]
                    
                    # Step 3.3: Assicurati che tutti gli oggetti siano visibili
                    for obj in objects:
                        was_hidden = obj.hide_viewport
                        if was_hidden:
                            obj.hide_viewport = False
                    
                    # Step 3.4: Seleziona e imposta active l'oggetto primario
                    primary_obj.select_set(True)
                    bpy.context.view_layer.objects.active = primary_obj
                    
                    # Step 3.5: Seleziona gli altri oggetti nel gruppo
                    for obj in objects:
                        if obj != primary_obj:
                            obj.select_set(True)
                            # Aggiungi alla lista di oggetti istanziati
                            self.instanced_objects.add(obj.name)
                    
                    # Step 3.6: Prepara il nome del file
                    export_file = os.path.join(export_folder, clean_filename(primary_obj.name))
                    
                    # Step 3.7: Export with instancing enabled
                    bpy.ops.export_scene.gltf(
                        filepath=str(export_file),
                        export_format='GLTF_SEPARATE',
                        export_copyright=scene.EMviq_model_author_name if hasattr(scene, 'EMviq_model_author_name') else "",
                        export_texcoords=True,
                        export_normals=True,
                        export_draco_mesh_compression_enable=export_vars.heriverse_use_draco,
                        export_draco_mesh_compression_level=export_vars.heriverse_draco_level,
                        export_materials='EXPORT',
                        use_selection=True,
                        export_apply=True,
                        export_extras=True,
                        export_gpu_instances=True,  # Sempre attivo per l'instancing
                        check_existing=False,
                        export_image_format='AUTO',
                        export_texture_dir="",
                        export_keep_originals=False
                    )
                    
                    # Crea o aggiorna il nodo Link per l'oggetto primario
                    if graph:
                        model_node_id = f"{primary_obj.name}_model"
                        model_node = graph.find_node_by_id(model_node_id)
                        
                        if model_node:
                            # Percorso relativo per l'export
                            gltf_path = f"models/{clean_filename(primary_obj.name)}.gltf"
                            
                            # Crea un nuovo LinkNode
                            link_node_id = f"{model_node_id}_link"
                            link_node = LinkNode(
                                node_id=link_node_id,
                                name=f"GLTF Link for {primary_obj.name}",
                                description=f"Link to exported GLTF for {primary_obj.name}",
                                url=gltf_path,
                                url_type="3d_model"
                            )
                            
                            # Aggiungi o aggiorna il nodo nel grafo
                            existing_link = graph.find_node_by_id(link_node_id)
                            if existing_link:
                                existing_link.url = gltf_path
                            else:
                                graph.add_node(link_node)
                                
                                # Crea l'edge tra il nodo RM e il LinkNode
                                edge_id = f"{model_node_id}_has_linked_resource_{link_node_id}"
                                if not graph.find_edge_by_id(edge_id):
                                    graph.add_edge(
                                        edge_id=edge_id,
                                        edge_source=model_node_id,
                                        edge_target=link_node_id,
                                        edge_type="has_linked_resource"
                                    )
                    
                    # Step 3.8: Registra il gruppo di istanze per l'esportazione JSON
                    self.exported_models[primary_obj.name] = [obj.name for obj in objects]
                    
                    print(f"Exported instanced group: {primary_obj.name} with {len(objects)} instances")
                    exported_count += 1
                    
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to export instanced group {mesh_name}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                
                finally:
                    # Step 3.10: Deselect all e ripristina visibilità
                    bpy.ops.object.select_all(action='DESELECT')
                    for obj in objects:
                        if hasattr(obj, 'was_hidden') and obj.was_hidden:
                            obj.hide_viewport = True
        
        self.report({'INFO'}, f"Exported {exported_count} RM models")
        
        # Aggiungi i dati di instancing alle proprietà dell'operatore per uso nell'esportazione JSON
        self.instanced_objects = instanced_objects
        self.exported_models = exported_models
        
        return exported_count > 0

    def update_json_for_instancing(self, json_data):
        """
        Aggiorna i dati JSON per riflettere le relazioni di instancing.
        Da chiamare dopo l'esportazione del JSON principale.
        """
        # Verifica se abbiamo dati di istanziazione
        if not hasattr(self, 'instanced_objects') or not hasattr(self, 'exported_models'):
            return json_data
        
        if len(self.instanced_objects) == 0:
            return json_data
        
        # Itera attraverso tutti i grafi nel JSON
        if 'graphs' in json_data:
            for graph_id, graph_data in json_data['graphs'].items():
                # Modifica i nodi RM per riflettere l'instancing
                if 'nodes' in graph_data and 'representation_models' in graph_data['nodes']:
                    rm_nodes = graph_data['nodes']['representation_models']

                    # Per ogni modello primario, aggiungi informazioni sulle istanze
                    for primary_name, instances in self.exported_models.items():
                        if primary_name in rm_nodes:
                            primary_node = rm_nodes[primary_name]
                            
                            # Aggiungi informazioni sulle istanze
                            if 'data' not in primary_node:
                                primary_node['data'] = {}
                            
                            primary_node['data']['instances'] = instances
                            primary_node['data']['is_instance_group'] = True
                    
                    for rm_name, rm_node in rm_nodes.items():
                        if 'data' in rm_node and 'url' in rm_node['data']:
                            url = rm_node['data']['url']
                            if url and 'tileset.json' in url:
                                if 'transform' not in rm_node['data']:
                                    rm_node['data']['transform'] = {
                                        'rotation': ["-1.57079632679", "0.0", "0.0"]
                                    }
                    # Rimuovi i nodi assorbiti come istanze
                    for rm_name in list(rm_nodes.keys()):
                        if rm_name in self.instanced_objects:
                            del rm_nodes[rm_name]

                if 'edges' in graph_data:
                    for edge_type in graph_data['edges']:
                        # Lavora su una copia della lista per poterla modificare durante l'iterazione
                        edges_to_keep = []
                        for edge in graph_data['edges'][edge_type]:
                            # Mantieni l'edge solo se né from né to sono nei nodi saltati
                            if (edge['from'] not in self.instanced_objects and 
                                edge['to'] not in self.instanced_objects):
                                edges_to_keep.append(edge)
                        
                        # Sostituisci con la lista filtrata
                        graph_data['edges'][edge_type] = edges_to_keep

        return json_data

    def export_textures(self, obj, textures_dir, context):
        """Export textures for an object with optional compression"""
        scene = context.scene
        
        for mat_slot in obj.material_slots:
            if mat_slot.material and mat_slot.material.use_nodes:
                for node in mat_slot.material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        try:
                            image = node.image
                            if image.packed_file:
                                image_path = os.path.join(textures_dir, clean_filename(image.name))
                                print(f"Exporting packed texture: {image.name}")
                                
                                # If compression is enabled
                                if scene.heriverse_enable_compression:
                                    # Store original settings
                                    original_format = scene.render.image_settings.file_format
                                    original_quality = scene.render.image_settings.quality
                                    
                                    # Apply compression settings
                                    scene.render.image_settings.file_format = 'JPEG'
                                    scene.render.image_settings.quality = scene.heriverse_texture_quality
                                    
                                    # If image needs scaling
                                    needs_scaling = (image.size[0] > scene.heriverse_texture_max_res or 
                                                    image.size[1] > scene.heriverse_texture_max_res)
                                    
                                    if needs_scaling:
                                        # Create a temporary copy and scale it
                                        temp_image = image.copy()
                                        max_dim = max(temp_image.size[0], temp_image.size[1])
                                        scale_factor = scene.heriverse_texture_max_res / max_dim
                                        new_width = int(temp_image.size[0] * scale_factor)
                                        new_height = int(temp_image.size[1] * scale_factor)
                                        temp_image.scale(new_width, new_height)
                                        temp_image.save_render(image_path)
                                        bpy.data.images.remove(temp_image)
                                    else:
                                        # Just save with compression settings
                                        image.save_render(image_path)
                                        
                                    # Restore original settings
                                    scene.render.image_settings.file_format = original_format
                                    scene.render.image_settings.quality = original_quality
                                else:
                                    # Export without compression
                                    image.save_render(image_path)
                            elif image.filepath:
                                src_path = bpy.path.abspath(image.filepath)
                                if os.path.exists(src_path):
                                    dst_path = os.path.join(textures_dir, clean_filename(os.path.basename(image.filepath)))
                                    print(f"Copying external texture: {os.path.basename(image.filepath)}")
                                    
                                    # If compression is enabled, load and process the image
                                    if scene.heriverse_enable_compression:
                                        # Create a temporary image
                                        temp_image = bpy.data.images.load(src_path)
                                        
                                        # Store original settings
                                        original_format = scene.render.image_settings.file_format
                                        original_quality = scene.render.image_settings.quality
                                        
                                        # Apply compression settings
                                        scene.render.image_settings.file_format = 'JPEG'
                                        scene.render.image_settings.quality = scene.heriverse_texture_quality
                                        
                                        # Check if scaling is needed
                                        needs_scaling = (temp_image.size[0] > scene.heriverse_texture_max_res or 
                                                        temp_image.size[1] > scene.heriverse_texture_max_res)
                                        
                                        if needs_scaling:
                                            max_dim = max(temp_image.size[0], temp_image.size[1])
                                            scale_factor = scene.heriverse_texture_max_res / max_dim
                                            new_width = int(temp_image.size[0] * scale_factor)
                                            new_height = int(temp_image.size[1] * scale_factor)
                                            temp_image.scale(new_width, new_height)
                                        
                                        # Save with compression
                                        temp_image.save_render(dst_path)
                                        
                                        # Clean up
                                        bpy.data.images.remove(temp_image)
                                        
                                        # Restore original settings
                                        scene.render.image_settings.file_format = original_format
                                        scene.render.image_settings.quality = original_quality
                                    else:
                                        # Simple copy without compression
                                        shutil.copy2(src_path, dst_path)
                        except Exception as e:
                            self.report({'WARNING'}, f"Failed to export texture for {obj.name}: {str(e)}")

    def export_dosco(self, context, graph_id, dosco_path):
        """Export DosCo files for a graph"""
        em_tools = context.scene.em_tools
        
        # Se non è specificato un graph_id, usa il file attivo
        if not graph_id and em_tools.active_file_index >= 0:
            graphml = em_tools.graphml_files[em_tools.active_file_index]
        else:
            # Trova il file GraphML corrispondente al graph_id
            graphml = None
            for gfile in em_tools.graphml_files:
                if gfile.name == graph_id:
                    graphml = gfile
                    break
        
        if not graphml or not graphml.dosco_dir:
            self.report({'WARNING'}, "No DosCo directory specified")
            return False
        
        src_path = bpy.path.abspath(graphml.dosco_dir)
        if not os.path.exists(src_path):
            self.report({'WARNING'}, f"DosCo path does not exist: {src_path}")
            return False
        
        try:
            shutil.copytree(src_path, dosco_path, dirs_exist_ok=True)
            print(f"Copied DosCo files from {src_path} to {dosco_path}")
            return True
        except Exception as e:
            self.report({'ERROR'}, f"Failed to copy DosCo files: {str(e)}")
            return False

    def create_project_zip(self, project_path: str, zip_name: str = None):
        """Creates a ZIP archive of the exported project"""
        if zip_name is None:
            zip_name = os.path.basename(project_path)
            
        zip_path = os.path.join(os.path.dirname(project_path), f"{zip_name}.zip")
        
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
        shutil.make_archive(
            os.path.splitext(zip_path)[0],
            'zip',
            project_path
        )
        
        return zip_path

    def execute(self, context):
        scene = context.scene
        export_vars = context.window_manager.export_vars
        
        # Import utility functions from the main module
        from ..functions import normalize_path, create_directory, check_export_path, check_graph_loaded, show_popup_message
        
        try:
            print("\n=== Starting Heriverse Export ===")
            
            # Check if at least one graph is loaded
            if not check_graph_loaded(context):
                return {'CANCELLED'}
            
            # Check if export path is valid
            if not check_export_path(context):
                return {'CANCELLED'}
            
            print(f"Export path: {scene.heriverse_export_path}")
                
            # Setup dei percorsi (con normalizzazione)
            output_dir = normalize_path(scene.heriverse_export_path)
            project_name = scene.heriverse_project_name or os.path.splitext(os.path.basename(bpy.data.filepath))[0]
            project_name = f"{project_name}_multigraph"
            project_path = os.path.join(output_dir, project_name)
            
            print(f"Project path: {project_path}")
            print(f"Project name: {project_name}")
            print(f"Using GPU instancing: {export_vars.heriverse_use_gpu_instancing}")
            
            # Crea la directory del progetto
            try:
                os.makedirs(project_path, exist_ok=True)
                print("Created project directory")
            except Exception as e:
                show_popup_message(context, "Directory Error", f"Failed to create project directory: {str(e)}", 'ERROR')
                return {'CANCELLED'}

            # Salva lo stato delle collezioni
            collection_states = {}
            for collection in bpy.data.collections:
                layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
                if layer_collection:
                    collection_states[collection.name] = layer_collection.exclude

            try:
                # Update the graph before exporting
                update_graph_with_scene_data()
                
                if export_vars.heriverse_overwrite_json:
                    update_graph_with_scene_data()
                    # Esporta il JSON direttamente usando il nuovo JSONExporter
                    json_path = os.path.join(project_path, "project.json")
                    print(f"Exporting JSON to: {json_path}")
                    
                    # Verifica che esista almeno un grafo valido
                    if not check_graph_loaded(context):
                        show_popup_message(context, "Export Error", "No valid graph found. Please load a GraphML file first.")
                        return {'CANCELLED'}
                    
                    # Usa l'operatore JSON con i parametri corretti
                    result = bpy.ops.export.heriversejson(
                        filepath=json_path,
                        use_file_dialog=False
                    )
                    
                    if result == {'FINISHED'}:
                        print("JSON export completed successfully")

                        if hasattr(self, 'instanced_objects') and len(self.instanced_objects) > 0:
                            # Leggi il file JSON
                            with open(json_path, 'r') as f:
                                json_data = json.load(f)
                            
                            # Aggiorna con informazioni sulle istanze
                            json_data = self.update_json_for_instancing(json_data)
                            
                            # Scrivi il file JSON aggiornato
                            with open(json_path, 'w') as f:
                                json.dump(json_data, f, indent=4)
                                
                            print(f"Updated JSON with instancing information for {len(self.instanced_objects)} objects")


                    else:
                        self.report({'ERROR'}, "JSON export failed")
                        return {'CANCELLED'}

                # Export Cesium tilesets if requested
                tilesets_exported = False
                if export_vars.heriverse_export_rm:
                    print("\n--- Starting Tileset Export ---")
                    tilesets_path = os.path.join(project_path, "tilesets")
                    os.makedirs(tilesets_path, exist_ok=True)
                    
                    count = self.export_tilesets(context, tilesets_path)
                    tilesets_exported = count > 0
                    if tilesets_exported:
                        print(f"Exported {count} tileset files")
                    else:
                        print("No tilesets were exported")

                # Esporta i proxy se richiesto
                if export_vars.heriverse_export_proxies:
                    print("\n--- Starting Proxy Export ---")
                    proxy_path = os.path.join(project_path, "proxies")
                    os.makedirs(proxy_path, exist_ok=True)
                    
                    proxy_collection = bpy.data.collections.get('Proxy')
                    if proxy_collection:
                        print(f"Found Proxy collection with {len(proxy_collection.objects)} objects")
                        layer_collection = find_layer_collection(context.view_layer.layer_collection, 'Proxy')
                        if layer_collection:
                            layer_collection.exclude = False
                            result = self.export_proxies(context, proxy_path)
                            if result:
                                print("Proxy export completed successfully")
                            else:
                                print("No proxies were exported")
                    else:
                        print("No Proxy collection found")

                # Esporta i modelli RM se richiesto
                models_exported = False
                models_path = None
                if export_vars.heriverse_export_rm:
                    print("\n--- Starting RM Export ---")
                    models_path = os.path.join(project_path, "models")
                    os.makedirs(models_path, exist_ok=True)
                    
                    # Make sure all collections containing RM objects are visible
                    rm_objects = [obj for obj in bpy.data.objects 
                                if hasattr(obj, "EM_ep_belong_ob") and len(obj.EM_ep_belong_ob) > 0]
                    
                    # Get all collections containing RM objects
                    rm_collections = set()
                    for obj in rm_objects:
                        for collection in bpy.data.collections:
                            if obj.name in collection.objects:
                                rm_collections.add(collection.name)
                    
                    # Make them all visible for export
                    for col_name in rm_collections:
                        layer_collection = find_layer_collection(context.view_layer.layer_collection, col_name)
                        if layer_collection:
                            layer_collection.exclude = False
                    
                    result = self.export_rm(context, models_path)
                    models_exported = result
                    if result:
                        print("RM export completed successfully")
                    else:
                        print("No RM models were exported")

                # Esporta i file DosCo se richiesto
                if export_vars.heriverse_export_dosco:
                    print("\n--- Starting DosCo Export ---")
                    active_graph_id = None
                    if not export_vars.heriverse_export_all_graphs and context.scene.em_tools.active_file_index >= 0:
                        active_file = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                        active_graph_id = active_file.name

                    dosco_path = os.path.join(project_path, "dosco")
                    result = self.export_dosco(context, active_graph_id, dosco_path)
                    if result:
                        print("DosCo export completed successfully")
                    else:
                        print("DosCo export failed or was skipped")
                
                # Nel metodo execute, dopo tutti gli altri export
                if scene.heriverse_export_panorama:
                    print("\n--- Exporting Panorama ---")
                    result = self.export_panorama(context, project_path)
                    if result:
                        print("Panorama export completed successfully")
                    else:
                        print("Panorama export failed or was skipped")
                
                # Compress all textures at once if texture compression is enabled and RM models were exported
                if scene.heriverse_enable_compression and models_exported and models_path:
                    print("\n--- Starting Texture Compression ---")
                    self.compress_textures_in_folder(models_path, scene)

            finally:
                # Ripristina lo stato delle collezioni
                for collection_name, was_excluded in collection_states.items():
                    layer_collection = find_layer_collection(context.view_layer.layer_collection, collection_name)
                    if layer_collection:
                        layer_collection.exclude = was_excluded

            # Crea ZIP se richiesto
            if export_vars.heriverse_create_zip:
                print("\n--- Creating ZIP Archive ---")
                zip_path = self.create_project_zip(project_path)
                print(f"ZIP archive created at: {zip_path}")

            print("\n=== Export Completed Successfully ===")
            self.report({'INFO'}, f"Export completed to {project_path}")
            return {'FINISHED'}
                
        except Exception as e:
            print(f"\n!!! Export Failed !!!")
            print(f"Error: {str(e)}")
            import traceback
            print(traceback.format_exc())
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

def find_layer_collection(layer_collection, collection_name):
    """Trova ricorsivamente un layer_collection dato il nome della collection"""
    if layer_collection.name == collection_name:
        return layer_collection
    
    for child in layer_collection.children:
        found = find_layer_collection(child, collection_name)
        if found:
            return found
    return None

def get_collection_for_object(obj):
    """Trova la collection principale di un oggetto"""
    for collection in bpy.data.collections:
        if obj.name in collection.objects:
            return collection.name
    return None

class HERIVERSE_OT_make_collections_visible(Operator):
    bl_idname = "heriverse.make_collections_visible"
    bl_label = "Make Collections Visible"
    bl_description = "Make all collections containing RM objects visible"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Recupera tutti gli oggetti con EM_ep_belong_ob
        rm_objects = [obj for obj in bpy.data.objects if len(obj.EM_ep_belong_ob) > 0]
        
        # Attiva tutte le collection che contengono questi oggetti
        for obj in rm_objects:
            for collection in bpy.data.collections:
                if obj.name in collection.objects:
                    layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
                    if layer_collection:
                        layer_collection.exclude = False
        
        self.report({'INFO'}, "All collections containing RM objects are now visible")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(HERIVERSE_OT_export)
    bpy.utils.register_class(JSON_OT_exportEMformat)  
    bpy.utils.register_class(HERIVERSE_OT_make_collections_visible) 
    
def unregister():
    bpy.utils.unregister_class(HERIVERSE_OT_export)
    bpy.utils.unregister_class(JSON_OT_exportEMformat)  
    bpy.utils.unregister_class(HERIVERSE_OT_make_collections_visible) 

