import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator, AddonPreferences, Panel
from bpy_extras.io_utils import ExportHelper
from ..s3Dgraphy.exporter.json_exporter import JSONExporter
from bpy_extras.io_utils import ExportHelper
import os
import shutil

from ..s3Dgraphy import get_graph, get_all_graph_ids
from ..functions import *

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
    )

    filepath: StringProperty(
        name="File Path",
        description="Path to save the JSON file",
        default=""
    )

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

    def export_rm(self, context, export_folder):
        """Export representation models"""
        scene = context.scene
        export_vars = context.window_manager.export_vars
        
        # Deseleziona tutto prima di iniziare
        bpy.ops.object.select_all(action='DESELECT')
        
        exported_count = 0
        for obj in bpy.data.objects:
            if len(obj.EM_ep_belong_ob) > 0:
                try:
                    # Verifica che l'oggetto sia effettivamente accessibile
                    if obj.hide_viewport:
                        print(f"Object {obj.name} is hidden in viewport, making it temporarily visible")
                        obj.hide_viewport = False
                    
                    obj.select_set(True)
                    export_file = os.path.join(export_folder, clean_filename(obj.name))
                    
                    bpy.ops.export_scene.gltf(
                        filepath=str(export_file),
                        export_format='GLTF_SEPARATE',
                        export_copyright=scene.EMviq_model_author_name,
                        export_texcoords=True,
                        export_normals=True,
                        export_draco_mesh_compression_enable=export_vars.heriverse_use_draco,
                        export_draco_mesh_compression_level=export_vars.heriverse_draco_level,
                        export_materials='EXPORT',
                        use_selection=True,
                        export_apply=True,
                        check_existing=False
                    )
                    
                    if export_vars.heriverse_separate_textures:
                        textures_dir = os.path.join(os.path.dirname(export_file), "textures")
                        os.makedirs(textures_dir, exist_ok=True)
                        self.export_textures(obj, textures_dir)
                    
                    exported_count += 1
                    print(f"Exported RM: {obj.name}")
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to export RM {obj.name}: {str(e)}")
                finally:
                    obj.select_set(False)
        
        self.report({'INFO'}, f"Exported {exported_count} RM models")
        return exported_count > 0

    def export_textures(self, obj, textures_dir):
        """Export textures for an object"""
        for mat_slot in obj.material_slots:
            if mat_slot.material and mat_slot.material.use_nodes:
                for node in mat_slot.material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        try:
                            image = node.image
                            if image.packed_file:
                                image_path = os.path.join(textures_dir, clean_filename(image.name))
                                print(f"Exporting packed texture: {image.name}")
                                image.save_render(image_path)
                            elif image.filepath:
                                src_path = bpy.path.abspath(image.filepath)
                                if os.path.exists(src_path):
                                    dst_path = os.path.join(textures_dir, clean_filename(os.path.basename(image.filepath)))
                                    print(f"Copying external texture: {os.path.basename(image.filepath)}")
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
        
        try:
            print("\n=== Starting Heriverse Export ===")
            
            # Verifiche preliminari
            if not export_vars.heriverse_export_path:
                self.report({'ERROR'}, "Export path not specified")
                return {'CANCELLED'}
            
            print(f"Export path: {export_vars.heriverse_export_path}")
                
            # Setup dei percorsi
            output_dir = bpy.path.abspath(export_vars.heriverse_export_path)
            project_name = export_vars.heriverse_project_name or os.path.splitext(os.path.basename(bpy.data.filepath))[0]
            project_name = f"{project_name}_multigraph"
            project_path = os.path.join(output_dir, project_name)
            
            print(f"Project path: {project_path}")
            
            # Crea la directory del progetto
            os.makedirs(project_path, exist_ok=True)
            print("Created project directory")
            
            # Esporta il JSON direttamente usando il nuovo JSONExporter
            json_path = os.path.join(project_path, "project.json")
            print(f"Exporting JSON to: {json_path}")
            
            # Usa l'operatore JSON con i parametri corretti
            result = bpy.ops.export.heriversejson(
                filepath=json_path,
                use_file_dialog=False
            )
            
            if result == {'FINISHED'}:
                print("JSON export completed successfully")
            else:
                self.report({'ERROR'}, "JSON export failed")
                return {'CANCELLED'}

            # Salva lo stato delle collezioni
            collection_states = {}
            for collection in bpy.data.collections:
                layer_collection = find_layer_collection(context.view_layer.layer_collection, collection.name)
                if layer_collection:
                    collection_states[collection.name] = layer_collection.exclude

            try:
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
                if export_vars.heriverse_export_rm:
                    print("\n--- Starting RM Export ---")
                    models_path = os.path.join(project_path, "models")
                    os.makedirs(models_path, exist_ok=True)
                    
                    rm_collection = bpy.data.collections.get('RM')
                    if rm_collection:
                        print(f"Found RM collection with {len(rm_collection.objects)} objects")
                        layer_collection = find_layer_collection(context.view_layer.layer_collection, 'RM')
                        if layer_collection:
                            layer_collection.exclude = False
                            result = self.export_rm(context, models_path)
                            if result:
                                print("RM export completed successfully")
                            else:
                                print("No RM models were exported")
                    else:
                        print("No RM collection found")

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

