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
    bl_idname = "export.emjson"
    bl_label = "Export emjson"
    bl_options = {"REGISTER", "UNDO"}

    # Property to control if showing file dialog
    use_file_dialog: BoolProperty(
        name="Use File Dialog",
        description="Use the file dialog to choose where to save the JSON",
        default=True
    ) # type: ignore

    filename_ext = ".json"

    def execute(self, context):
    
        if self.use_file_dialog:
            return self.export_emjson(context, self.filepath)
        else:
            return self.export_emjson(context, None)
    
    def export_emjson(self, context, file_path):
        scene = context.scene
        if not file_path:
            file_path = "output.json"
            
        try:
            # Create exporter
            exporter = JSONExporter(file_path)
            
            # Export all graphs
            exporter.export_graphs()
            
            self.report({'INFO'}, f"EM data successfully exported to {file_path}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error during export: {str(e)}")
            return {'CANCELLED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error exporting EM data: {str(e)}")
            return {'CANCELLED'}

class HERIVERSE_OT_export(Operator):
    """Export project in Heriverse format"""
    bl_idname = "export.heriverse"
    bl_label = "Export Heriverse Project"
    bl_description = "Export project in Heriverse format with models, proxies and documentation"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        wm = context.window_manager
        export_vars = wm.export_vars
        
        # Get project name and base path
        project_name = export_vars.heriverse_project_name
        if not project_name:
            project_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        project_name = f"{project_name}_multigraph"
        
        if not export_vars.heriverse_export_path:
            self.report({'ERROR'}, "Export path not specified")
            return {'CANCELLED'}
            
        # Verify output path exists and is writable
        try:
            output_dir = bpy.path.abspath(export_vars.heriverse_export_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            elif not os.access(output_dir, os.W_OK):
                self.report({'ERROR'}, f"Cannot write to export path: {output_dir}")
                return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error creating export directory: {str(e)}")
            return {'CANCELLED'}
            
        project_path = os.path.join(bpy.path.abspath(export_vars.heriverse_export_path), project_name)
        
        # Create project folder
        if os.path.exists(project_path):
            if export_vars.heriverse_overwrite_json:
                shutil.rmtree(project_path)
            else:
                self.report({'ERROR'}, f"Project folder already exists: {project_path}")
                return {'CANCELLED'}
        os.makedirs(project_path)
        
        # Get graphs to export
        if export_vars.heriverse_export_all_graphs:
            graph_ids = get_all_graph_ids()
        else:
            active_graph_id = None
            if context.scene.em_tools.active_file_index >= 0:
                active_file = context.scene.em_tools.graphml_files[context.scene.em_tools.active_file_index]
                active_graph_id = active_file.name
            if not active_graph_id:
                self.report({'ERROR'}, "No active graph selected")
                return {'CANCELLED'}
            graph_ids = [active_graph_id]
            
        if not graph_ids:
            self.report({'ERROR'}, "No graphs to export")
            return {'CANCELLED'}
            
        # Export JSON
        bpy.ops.export.emjson('INVOKE_DEFAULT', 
            filepath=os.path.join(project_path, "project.json"),
            use_file_dialog=False)
            
        # Process each graph
        for graph_id in graph_ids:
            graph = get_graph(graph_id)
            if not graph:
                self.report({'WARNING'}, f"Could not get graph: {graph_id}")
                continue
                
            # Create graph folders
            safe_graph_id = clean_filename(graph_id)
            graph_dosco_path = os.path.join(project_path, f"{safe_graph_id}_DosCo")
            graph_proxy_path = os.path.join(project_path, f"{safe_graph_id}_proxy")
            
            if export_vars.heriverse_export_dosco:
                self.export_dosco(context, graph_id, graph_dosco_path)
                
            if export_vars.heriverse_export_proxies:
                os.makedirs(graph_proxy_path, exist_ok=True)
                self.export_proxies(context, graph_proxy_path)
                
        # Create models folder and export RMs
        if export_vars.heriverse_export_rm:
            models_path = os.path.join(project_path, "models")
            os.makedirs(models_path, exist_ok=True)
            self.export_rm(context, models_path)
            
        # Create ZIP if requested
        if export_vars.heriverse_create_zip:
            zip_path = self.create_project_zip(project_path)
            self.report({'INFO'}, f"Created ZIP archive: {zip_path}")
            
        self.report({'INFO'}, f"Heriverse project exported to: {project_path}")
        return {'FINISHED'}
        
    def export_dosco(self, context, graph_id, dosco_path):
        """Export DosCo files for a graph"""
        em_tools = context.scene.em_tools
        # Trova il file GraphML corrispondente al graph_id
        graphml = None
        for gfile in em_tools.graphml_files:
            if gfile.name == graph_id:
                graphml = gfile
                break
                
        if graphml:
                if graphml.dosco_dir:
                    src_path = bpy.path.abspath(graphml.dosco_dir)
                    if os.path.exists(src_path):
                        try:
                            shutil.copytree(src_path, dosco_path, dirs_exist_ok=True)
                            return True
                        except Exception as e:
                            self.report({'WARNING'}, f"Error copying DosCo files for {graph_id}: {str(e)}")
                    else:
                        self.report({'WARNING'}, f"DosCo path for {graph_id} does not exist: {src_path}")
                else:
                    self.report({'WARNING'}, f"No DosCo directory specified for {graph_id}")
        return False
        
    def export_proxies(self, context, export_folder):
        """Export proxy models"""
        scene = context.scene
        for proxy in bpy.data.objects:
            for em in scene.em_list:
                if proxy.name == em.name:
                    proxy.select_set(True)
                    name = clean_filename(em.name)
                    export_file = os.path.join(export_folder, name)
                    bpy.ops.export_scene.gltf(
                        export_format='GLB',
                        filepath=str(export_file), 
                        export_materials='NONE',
                        use_selection=True
                    )
                    proxy.select_set(False)
                    
    def export_rm(self, context, export_folder):
        """Export representation models"""
        scene = context.scene
        export_vars = context.window_manager.export_vars
        EM_list_clear(context, "emviq_error_list")
        
        for ob in bpy.data.objects:
            if len(ob.EM_ep_belong_ob) > 0:
                ob.select_set(True)
                export_file = os.path.join(export_folder, clean_filename(ob.name))
                
                bpy.ops.export_scene.gltf(
                    export_format='GLTF_SEPARATE',
                    export_copyright=scene.EMviq_model_author_name,
                    export_texcoords=True,
                    export_normals=True,
                    export_draco_mesh_compression_enable=export_vars.heriverse_use_draco,
                    export_draco_mesh_compression_level=export_vars.heriverse_draco_level,
                    export_materials='EXPORT',
                    use_selection=True,
                    export_apply=True,
                    filepath=str(export_file),
                    check_existing=False
                )
                
                if export_vars.heriverse_separate_textures:
                    copy_tex_ob(ob, export_folder)
                
                ob.select_set(False)
                
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

def register():
    bpy.utils.register_class(HERIVERSE_OT_export)
    
def unregister():
    bpy.utils.unregister_class(HERIVERSE_OT_export)
                    
