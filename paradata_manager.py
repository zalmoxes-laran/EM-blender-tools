import bpy # type: ignore
import xml.etree.ElementTree as ET
import os
import sys
import bpy.props as prop # type: ignore
import subprocess
from bpy.types import Panel, UIList # type: ignore
from .functions import *

import urllib.request
import tempfile
from bpy.props import PointerProperty, StringProperty, BoolProperty # type: ignore

from urllib.parse import urlparse

# Variabili globali per tracciare lo stato degli aggiornamenti
_paradata_update_in_progress = False
_paradata_refresh_needed = False


# Funzione di utilità per controllare lo stato degli aggiornamenti
def set_paradata_update_state(state):
    global _paradata_update_in_progress, _paradata_refresh_needed
    if state and _paradata_update_in_progress:
        # Aggiornamento già in corso, marca come necessario un aggiornamento futuro
        _paradata_refresh_needed = True
        return False
    _paradata_update_in_progress = state
    return True

class ParadataImageProps(bpy.types.PropertyGroup):
    """Properties for handling paradata images"""
    image_path: StringProperty(
        name="Image Path",
        description="Path or URL to the image"
    )# type: ignore
    is_loading: BoolProperty(
        name="Is Loading",
        description="Whether the image is currently loading",
        default=False
    )# type: ignore
    loaded_image: PointerProperty(
        name="Loaded Image",
        type=bpy.types.Image
    )# type: ignore
    auto_load: BoolProperty(
        name="Auto-load Images",
        description="Automatically load images when selecting documents or extractors",
        default=True
    ) # type: ignore

    # Track the last seen selections
    last_source_index: IntProperty(default=-1)# type: ignore
    last_extractor_index: IntProperty(default=-1)# type: ignore

    image_collection: CollectionProperty(type=bpy.types.PropertyGroup)# type: ignore
    active_image_index: IntProperty(default=0)# type: ignore

def check_selection_changed(context):
    """Check if selection has changed and load images if needed"""
    scene = context.scene
    
    # Skip if auto-loading is disabled
    if not hasattr(scene, "paradata_image") or not scene.paradata_image.auto_load:
        return
    
    # Check sources list
    if (hasattr(scene, "em_v_sources_list_index") and 
        scene.em_v_sources_list_index >= 0 and 
        scene.em_v_sources_list_index != scene.paradata_image.last_source_index):
        
        # Update last seen index
        scene.paradata_image.last_source_index = scene.em_v_sources_list_index
        
        # Try loading image
        if len(scene.em_v_sources_list) > 0:
            auto_load_paradata_image(context, "em_v_sources_list")
            
    # Check extractors list
    if (hasattr(scene, "em_v_extractors_list_index") and 
        scene.em_v_extractors_list_index >= 0 and 
        scene.em_v_extractors_list_index != scene.paradata_image.last_extractor_index):
        
        # Update last seen index
        scene.paradata_image.last_extractor_index = scene.em_v_extractors_list_index
        
        # Try loading image
        if len(scene.em_v_extractors_list) > 0:
            auto_load_paradata_image(context, "em_v_extractors_list")

def auto_load_paradata_image(context, node_type):
    """Helper function for auto-loading images when selection changes"""
    scene = context.scene
    
    # Skip if auto-loading is disabled
    if not hasattr(scene, "paradata_image") or not scene.paradata_image.auto_load:
        return
    
    # Skip if already loading an image
    if scene.paradata_image.is_loading:
        return
    
    # Check if the URL might be an image
    url = None
    if node_type == "em_v_sources_list" and scene.em_v_sources_list_index >= 0 and len(scene.em_v_sources_list) > 0:
        url = scene.em_v_sources_list[scene.em_v_sources_list_index].url
    elif node_type == "em_v_extractors_list" and scene.em_v_extractors_list_index >= 0 and len(scene.em_v_extractors_list) > 0:
        url = scene.em_v_extractors_list[scene.em_v_extractors_list_index].url
    
    if not url:
        return
    
    # Skip web URLs for auto-loading (to avoid unnecessary downloads)
    # unless explicitly containing image extensions in the URL
    is_web_url = url.startswith(("http://", "https://"))
    
    # Quick check if the URL might be an image
    img_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.gif']
    is_potential_image = any(url.lower().endswith(ext) for ext in img_exts)
    
    # For web URLs, only auto-load if they're obviously image URLs
    if is_web_url and not is_potential_image:
        for ext in img_exts:
            if ext in url.lower():
                is_potential_image = True
                break
    
    # If it's a potential image or a local file, trigger the load operator
    if is_potential_image or not is_web_url:
        bpy.ops.em.load_paradata_image(node_type=node_type)

class EM_OT_load_paradata_image(bpy.types.Operator):
    """Load an image from a URL or file path for the Paradata Manager"""
    bl_idname = "em.load_paradata_image"
    bl_label = "Load Paradata Image"
    bl_description = "Load an image from a URL or local file for preview"
    
    node_type: StringProperty()
    
    def is_valid_url(self, url):
        """Check if the string is a valid URL"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
                
    def build_file_path(self, context, path):
        """Build a proper file path based on context and path information"""
        scene = context.scene
        em_tools = scene.em_tools
        
        # Debug output
        print(f"Building path for: {path}")
        
        # If it's a valid URL, return it as is
        if self.is_valid_url(path):
            print(f"Path is a valid URL")
            return path, True
            
        # Not a URL, so should be a local file
        # Check if we have a valid DosCo directory for the current graph
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            print("No active GraphML file found")
            return None, False
            
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        
        # Try to get the DosCo directory for this specific graph
        dosco_dir = graphml.dosco_dir
        print(f"Graph-specific DosCo directory: {dosco_dir}")
        
        # If empty, fall back to the global DosCo setting
        if not dosco_dir:
            dosco_dir = scene.EMDosCo_dir
            print(f"Falling back to global DosCo directory: {dosco_dir}")
            
        # If still empty, we can't proceed
        if not dosco_dir:
            print("No DosCo directory specified")
            return None, False
            
        # Normalize the path
        dosco_dir = bpy.path.abspath(dosco_dir)
        print(f"Normalized DosCo directory: {dosco_dir}")
        
        # Try multiple path variants
        path_variants = [
            path,                              # Original path
            path.split("/")[-1],               # Just the filename
            os.path.basename(path)             # Another way to get just the filename
        ]
        
        # Add the graph code variant if available
        graph_code = graphml.graph_code if hasattr(graphml, 'graph_code') else None
        if graph_code:
            path_variants.append(f"{graph_code}.{path}")  # Prefixed path
            path_variants.append(path.replace(f"{graph_code}.", ""))  # Un-prefixed path
        
        # Check each variant
        for variant in path_variants:
            if variant.startswith(dosco_dir):
                full_path = variant
            else:
                # Ensure path doesn't start with file separator
                if variant.startswith(os.path.sep):
                    variant = variant[1:]
                full_path = os.path.join(dosco_dir, variant)
                
            print(f"Trying path: {full_path}")
            if os.path.exists(full_path):
                normalized_path = os.path.normpath(full_path)
                print(f"Found existing file at: {normalized_path}")
                return normalized_path, False
        
        # If we get here, none of the variants worked
        print(f"Could not find file for any of these variants: {path_variants}")
        return None, False
    
    def execute(self, context):
        scene = context.scene
        
        # Retrieve the path from the selected item
        path = eval("scene."+self.node_type+"[scene."+self.node_type+"_index].url")
        
        # Skip if already loading or path is empty
        if scene.paradata_image.is_loading or not path:
            print(f"Skipping: is_loading={scene.paradata_image.is_loading}, path empty={not bool(path)}")
            return {'CANCELLED'}
        
        # Clear any previous image
        if scene.paradata_image.loaded_image:
            bpy.data.images.remove(scene.paradata_image.loaded_image)
            scene.paradata_image.loaded_image = None
        
        scene.paradata_image.is_loading = True
        scene.paradata_image.image_path = path
        
        try:
            # Build the proper path
            full_path, is_url = self.build_file_path(context, path)
            
            if not full_path:
                self.report({'ERROR'}, f"Cannot resolve path: {path}. Check DosCo directory settings.")
                scene.paradata_image.is_loading = False
                return {'CANCELLED'}
            
            # Load based on whether it's URL or local path
            if is_url:
                # Create a temporary file
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                temp_file.close()
                
                # Download the image
                urllib.request.urlretrieve(full_path, temp_file.name)
                
                # Load the image into Blender
                img = bpy.data.images.load(temp_file.name)
                img.name = f"ParadataPreview_{os.path.basename(path)}"
                img.use_fake_user = False  # No users
                
                # Delete the temporary file
                os.unlink(temp_file.name)
                
            else:
                # Check if the file exists
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    # Check if it's an image file (basic check)
                    img_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
                    if any(full_path.lower().endswith(ext) for ext in img_exts):
                        img = bpy.data.images.load(full_path)
                        img.name = f"ParadataPreview_{os.path.basename(path)}"
                        img.use_fake_user = False  # No users
                    else:
                        self.report({'WARNING'}, f"Not an image file: {full_path}")
                        scene.paradata_image.is_loading = False
                        return {'CANCELLED'}
                else:
                    self.report({'WARNING'}, f"File not found: {full_path}")
                    scene.paradata_image.is_loading = False
                    return {'CANCELLED'}
            
            # Store the loaded image
            scene.paradata_image.loaded_image = img
            
        except Exception as e:
            self.report({'ERROR'}, f"Error loading image: {str(e)}")
            scene.paradata_image.is_loading = False
            return {'CANCELLED'}
            
        scene.paradata_image.is_loading = False
        return {'FINISHED'}

class EM_OT_save_paradata_image(bpy.types.Operator):
    """Save the displayed paradata image to disk"""
    bl_idname = "em.save_paradata_image"
    bl_label = "Save Paradata Image"
    bl_description = "Save the displayed image to disk"
    
    filepath: StringProperty(subtype="FILE_PATH")
    
    def execute(self, context):
        scene = context.scene
        
        if not scene.paradata_image.loaded_image:
            self.report({'ERROR'}, "No image loaded")
            return {'CANCELLED'}
        
        # Open file browser
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def invoke(self, context, event):
        scene = context.scene
        
        # Use the original filename if available
        if scene.paradata_image.image_path:
            base_name = os.path.basename(scene.paradata_image.image_path)
            self.filepath = base_name
        else:
            self.filepath = "paradata_image.png"
            
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
        
    def execute(self, context):
        scene = context.scene
        
        if not scene.paradata_image.loaded_image:
            self.report({'ERROR'}, "No image loaded")
            return {'CANCELLED'}
            
        # Save the image
        try:
            scene.paradata_image.loaded_image.save_render(self.filepath)
            self.report({'INFO'}, f"Image saved to {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Error saving image: {str(e)}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

def sources_index_update(self, context):
    """Function to call when sources list index changes"""
    if hasattr(context.scene, "paradata_image") and context.scene.paradata_image.auto_load:
        # Trigger image loading for selected source
        auto_load_paradata_image(context, "em_v_sources_list")
    
def extractors_index_update(self, context):
    """Function to call when extractors list index changes"""
    if hasattr(context.scene, "paradata_image") and context.scene.paradata_image.auto_load:
        # Trigger image loading for selected extractor
        auto_load_paradata_image(context, "em_v_extractors_list")

def auto_load_paradata_image(context, node_type):
    """Helper function for auto-loading images when selection changes"""
    scene = context.scene
    
    # Skip if auto-loading is disabled
    if not hasattr(scene, "paradata_image") or not scene.paradata_image.auto_load:
        return
    
    # Skip if already loading an image
    if scene.paradata_image.is_loading:
        return
    
    # Check if the URL might be an image
    url = None
    if node_type == "em_v_sources_list" and scene.em_v_sources_list_index >= 0 and len(scene.em_v_sources_list) > 0:
        url = scene.em_v_sources_list[scene.em_v_sources_list_index].url
    elif node_type == "em_v_extractors_list" and scene.em_v_extractors_list_index >= 0 and len(scene.em_v_extractors_list) > 0:
        url = scene.em_v_extractors_list[scene.em_v_extractors_list_index].url
    
    if not url:
        return
    
    # Skip web URLs for auto-loading (to avoid unnecessary downloads)
    # unless explicitly containing image extensions in the URL
    is_web_url = url.startswith(("http://", "https://"))
    
    # Quick check if the URL might be an image
    img_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.gif']
    is_potential_image = any(url.lower().endswith(ext) for ext in img_exts)
    
    # For web URLs, only auto-load if they're obviously image URLs
    if is_web_url and not is_potential_image:
        for ext in img_exts:
            if ext in url.lower():
                is_potential_image = True
                break
    
    # If it's a potential image or a local file, trigger the load operator
    if is_potential_image or not is_web_url:
        bpy.ops.em.load_paradata_image(node_type=node_type)
    scene = context.scene
    
    # Skip if auto-loading is disabled
    if not hasattr(scene, "paradata_image") or not scene.paradata_image.auto_load:
        return
    
    # Skip if already loading an image
    if scene.paradata_image.is_loading:
        return
    
    # Check if the URL might be an image
    url = None
    if node_type == "em_v_sources_list" and scene.em_v_sources_list_index >= 0 and len(scene.em_v_sources_list) > 0:
        url = scene.em_v_sources_list[scene.em_v_sources_list_index].url
    elif node_type == "em_v_extractors_list" and scene.em_v_extractors_list_index >= 0 and len(scene.em_v_extractors_list) > 0:
        url = scene.em_v_extractors_list[scene.em_v_extractors_list_index].url
    
    if not url:
        return
    
    # Skip web URLs for auto-loading (to avoid unnecessary downloads)
    # unless explicitly containing image extensions in the URL
    is_web_url = url.startswith(("http://", "https://"))
    
    # Quick check if the URL might be an image
    img_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.gif']
    is_potential_image = any(url.lower().endswith(ext) for ext in img_exts)
    
    # For web URLs, only auto-load if they're obviously image URLs
    if is_web_url and not is_potential_image:
        for ext in img_exts:
            if ext in url.lower():
                is_potential_image = True
                break
    
    # If it's a potential image or a local file, trigger the load operator
    if is_potential_image or not is_web_url:
        bpy.ops.em.load_paradata_image(node_type=node_type)


#####################################################################
#Paradata Section

class EM_ParadataPanel:
    bl_label = "Paradata Manager"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        em_tools = context.scene.em_tools
        # Restituisce True se mode_switch è False, quindi il pannello viene mostrato solo in modalità 3D GIS
        return em_tools.mode_switch

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.object

        # Box per i controlli di aggiornamento
        control_box = layout.box()
        row = control_box.row(align=True)
        
        # Checkbox per l'aggiornamento automatico
        row.prop(scene, "paradata_auto_update", text="Auto Update")
        
        # Pulsante di aggiornamento manuale
        op = row.operator("em.update_paradata_lists", text="Refresh", icon="FILE_REFRESH")


        row = layout.row()

        # Define variables 
        if scene.paradata_streaming_mode:
            property_list_var = "em_v_properties_list"
            property_list_index_var = "em_v_properties_list_index"
            property_list_cmd = "scene.em_v_properties_list"
            property_list_index_cmd = "scene.em_v_properties_list_index"

            combiner_list_var = "em_v_combiners_list"
            combiner_list_index_var = "em_v_combiners_list_index"
            combiner_list_cmd = "scene.em_v_combiners_list"
            combiner_list_index_cmd = "scene.em_v_combiners_list_index"

            extractor_list_var = "em_v_extractors_list"
            extractor_list_index_var = "em_v_extractors_list_index"
            extractor_list_cmd = "scene.em_v_extractors_list"
            extractor_list_index_cmd = "scene.em_v_extractors_list_index"

            source_list_var = "em_v_sources_list"
            source_list_index_var = "em_v_sources_list_index"
            source_list_cmd = "scene.em_v_sources_list"
            source_list_index_cmd = "scene.em_v_sources_list_index"

        else:
            property_list_var = "em_properties_list"
            property_list_index_var = "em_properties_list_index"
            property_list_cmd = "scene.em_properties_list"
            property_list_index_cmd = "scene.em_properties_list_index"

            combiner_list_var = "em_combiners_list"
            combiner_list_index_var = "em_combiners_list_index"
            combiner_list_cmd = "scene.em_combiners_list"
            combiner_list_index_cmd = "scene.em_combiners_list_index"

            extractor_list_var = "em_extractors_list"
            extractor_list_index_var = "em_extractors_list_index"
            extractor_list_cmd = "scene.em_extractors_list"
            extractor_list_index_cmd = "scene.em_extractors_list_index"  

            source_list_var = "em_sources_list"
            source_list_index_var = "em_sources_list_index"
            source_list_cmd = "scene.em_sources_list"
            source_list_index_cmd = "scene.em_sources_list_index"           

        ###############################################################################
        ##          Properties
        ###############################################################################

        # Safely get the property list length and index
        property_list_length = len(eval(property_list_cmd))
        property_list_index = eval(property_list_index_cmd)
        
        # Invece di modificare l'indice, controlla solo se è valido
        property_index_valid = (property_list_length > 0 and 0 <= property_list_index < property_list_length)
        
        # Safely get the GraphML file information
        paradata_text = "Full list of paradata"
        if scene.paradata_streaming_mode and scene.em_list_index >= 0 and len(scene.em_list) > 0:
            # Se è attivo lo streaming, mostra il nome stratigrafico selezionato
            paradata_text = str("Paradata related to: " + str(scene.em_list[scene.em_list_index].name))
        else:
            # Safe access to GraphML file information 
            try:
                if hasattr(scene, 'em_tools') and hasattr(scene.em_tools, 'active_file_index'):
                    if scene.em_tools.active_file_index >= 0 and hasattr(scene.em_tools, 'graphml_files'):
                        if scene.em_tools.active_file_index < len(scene.em_tools.graphml_files):
                            graphml_file = scene.em_tools.graphml_files[scene.em_tools.active_file_index]
                            if hasattr(graphml_file, 'graph_code') and graphml_file.graph_code:
                                paradata_text = f"Full list of paradata in: {graphml_file.graph_code}"
                            else:
                                paradata_text = "Full list of paradata (no graph code available)"
                        else:
                            paradata_text = "Full list of paradata (invalid file index)"
                    else:
                        paradata_text = "No GraphML file selected"
                else:
                    paradata_text = "EM Tools not properly initialized"
            except Exception as e:
                print(f"Error getting graph code: {str(e)}")
                paradata_text = "Error accessing GraphML information"  

        # Suddividiamo la riga in due colonne: 70% per la prima e 30% per la seconda
        split = layout.split(factor=0.70)  # Il fattore indica la percentuale della prima colonna

        col1 = split.column()
        col1.label(text=paradata_text)

        col2 = split.column()
        col2.prop(scene, "paradata_streaming_mode", text='Filter Paradata', icon="SHORTDISPLAY")

        row = layout.row()
        row.label(text="Properties: (" + str(property_list_length) + ")")
        #row.prop(scene, "prop_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
        row = layout.row()
        row.template_list("EM_UL_properties_managers", "", scene, property_list_var, scene, property_list_index_var, rows=2)
        
        # Mostra sempre il box, anche se non ci sono elementi
        box = layout.box()
        if property_index_valid:
            item_property = eval(property_list_cmd)[property_list_index]
            row = box.row()
            row.prop(item_property, "name", text="", icon='FILE_TEXT')
            row = box.row()
            row.prop(item_property, "description", text="", slider=True, emboss=True, icon='TEXT')
        else:
            row = box.row()
            row.label(text="Nessuna proprietà disponibile")

        ###############################################################################
        ##          Combiners
        ###############################################################################

        # Safely get the combiner list length and index
        combiner_list_length = len(eval(combiner_list_cmd))
        combiner_list_index = eval(combiner_list_index_cmd)
        
        # Invece di modificare l'indice, controlla solo se è valido
        combiner_index_valid = (combiner_list_length > 0 and 0 <= combiner_list_index < combiner_list_length)
        
        # Sezione Combiners
        row = layout.row()
        row.label(text="Combiners: (" + str(combiner_list_length) + ")")
        #row.prop(scene, "comb_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
        row = layout.row()
        row.template_list("EM_UL_combiners_managers", "", scene, combiner_list_var, scene, combiner_list_index_var, rows=1)
        
        # Mostra sempre il box, anche se non ci sono elementi
        box = layout.box()
        if combiner_index_valid:
            item_property = eval(combiner_list_cmd)[combiner_list_index]
            row = box.row()
            row.prop(item_property, "name", text="", icon='FILE_TEXT')
            row = box.row()
            row.prop(item_property, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_property, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            if op:  # Check if operator is valid
                op.node_type = combiner_list_var
        else:
            row = box.row()
            row.label(text="Nessun combiner disponibile")
        
        ###############################################################################
        ##          Extractors
        ###############################################################################

        # Safely get the extractor list length and index
        extractor_list_length = len(eval(extractor_list_cmd))
        extractor_list_index = eval(extractor_list_index_cmd)
        
        # Invece di modificare l'indice, controlla solo se è valido
        extractor_index_valid = (extractor_list_length > 0 and 0 <= extractor_list_index < extractor_list_length)
        
        # Sezione Extractors
        row = layout.row()
        row.label(text="Extractors: (" + str(extractor_list_length) + ")")
        #row.prop(scene, "extr_paradata_streaming_mode", text='', icon="SHORTDISPLAY")
        row = layout.row()
        row.template_list("EM_UL_extractors_managers", "", scene, extractor_list_var, scene, extractor_list_index_var, rows=2)
        
        # Mostra sempre il box, anche se non ci sono elementi
        box = layout.box()
        if extractor_index_valid:
            item_source = eval(extractor_list_cmd)[extractor_list_index]
            row = box.row()
            row.prop(item_source, "name", text="", icon='FILE_TEXT')
            op = row.operator("listitem.toobj", icon="PASTEDOWN", text='')
            if op:  # Check if operator is valid
                op.list_type = extractor_list_var
            
            if scene.em_list_index >= 0 and len(scene.em_list) > 0 and scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                op = row.operator("select.fromlistitem", text='', icon="MESH_CUBE")
                if op:  # Check if operator is valid
                    op.list_type = extractor_list_var
            else:
                row.label(text="", icon='MESH_CUBE')
            
            if obj and check_if_current_obj_has_brother_inlist(obj.name, extractor_list_var):
                op = row.operator("select.listitem", text='', icon="LONGDISPLAY")
                if op:  # Check if operator is valid
                    op.list_type = extractor_list_var
            else:
                row.label(text="", icon='LONGDISPLAY')   
            
            row = box.row()
            row.prop(item_source, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_source, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            if op:  # Check if operator is valid
                op.node_type = extractor_list_var
        else:
            row = box.row()
            row.label(text="Nessun estrattore disponibile")
        
        ###############################################################################
        ##          Sources
        ###############################################################################

        # Safely get the source list length and index
        source_list_length = len(eval(source_list_cmd))
        source_list_index = eval(source_list_index_cmd)
        
        # Invece di modificare l'indice, controlla solo se è valido
        source_index_valid = (source_list_length > 0 and 0 <= source_list_index < source_list_length)
        
        # Sezione Documents
        row = layout.row()
        row.label(text="Docs: (" + str(source_list_length) + ")")
        row = layout.row()
        row.template_list("EM_UL_sources_managers", "", scene, source_list_var, scene, source_list_index_var, rows=2)
        
        # Mostra sempre il box, anche se non ci sono elementi
        box = layout.box()
        if source_index_valid:
            item_source = eval(source_list_cmd)[source_list_index]
            row = box.row()
            row.prop(item_source, "name", text="", icon='FILE_TEXT')
            
            op = row.operator("listitem.toobj", icon="PASTEDOWN", text='')
            if op:  # Check if operator is valid
                op.list_type = source_list_var
            
            if scene.em_list_index >= 0 and len(scene.em_list) > 0 and scene.em_list[scene.em_list_index].icon == 'RESTRICT_INSTANCED_OFF':
                op = row.operator("select.fromlistitem", text='', icon="MESH_CUBE")
                if op:  # Check if operator is valid
                    op.list_type = source_list_var
            else:
                row.label(text="", icon='MESH_CUBE')
            
            if obj and check_if_current_obj_has_brother_inlist(obj.name, source_list_var):
                op = row.operator("select.listitem", text='', icon="LONGDISPLAY")
                if op:  # Check if operator is valid
                    op.list_type = source_list_var
            else:
                row.label(text="", icon='LONGDISPLAY')
            
            row = box.row()
            row.prop(item_source, "description", text="", slider=True, emboss=True, icon='TEXT')
            row = box.row()
            row.prop(item_source, "url", text="", slider=True, emboss=True, icon='URL')
            op = row.operator("open.file", icon="EMPTY_SINGLE_ARROW", text='')
            if op:  # Check if operator is valid
                op.node_type = source_list_var
        else:
            row = box.row()
            row.label(text="Nessun documento disponibile")

        ###############################################################################
        ##          Image Preview
        ###############################################################################
        
        # Add image preview section at the end
        #layout.separator()

        # Image preview section
        box = layout.box()
        row = box.row()
        
        # Multiple image preview logic
        if scene.paradata_image.image_collection:
            images = scene.paradata_image.image_collection
            active_index = scene.paradata_image.active_image_index
            
            # Navigation buttons
            if len(images) > 1:
                row = box.row()
                row.operator("em.previous_image", text="", icon="TRIA_LEFT")
                row.label(text=f"Image {active_index + 1} of {len(images)}")
                row.operator("em.next_image", text="", icon="TRIA_RIGHT")
            
            # Display active image
            if 0 <= active_index < len(images):
                active_image = images[active_index].image
                row = box.row()
                row.template_preview(active_image, show_buttons=False)





class VIEW3D_PT_ParadataPanel(Panel, EM_ParadataPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ParadataPanel"
    bl_context = "objectmode"


class EM_OT_previous_image(bpy.types.Operator):
    """Go to previous image"""
    bl_idname = "em.previous_image"
    bl_label = "Previous Image"
    
    def execute(self, context):
        scene = context.scene
        images = scene.paradata_image.image_collection
        
        if len(images) > 1:
            scene.paradata_image.active_image_index = \
                (scene.paradata_image.active_image_index - 1) % len(images)
        
        return {'FINISHED'}

class EM_OT_next_image(bpy.types.Operator):
    """Go to next image"""
    bl_idname = "em.next_image"
    bl_label = "Next Image"
    
    def execute(self, context):
        scene = context.scene
        images = scene.paradata_image.image_collection
        
        if len(images) > 1:
            scene.paradata_image.active_image_index = \
                (scene.paradata_image.active_image_index + 1) % len(images)
        
        return {'FINISHED'}

class EM_UL_sources_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.22, align = True)
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon=item.icon_url)

class EM_UL_properties_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.4, align = True)
        layout.label(text = item.name)
        layout.label(text = item.description)

class EM_UL_combiners_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.25, align = True)
        layout.label(text = item.name)
        layout.label(text = item.description)

class EM_UL_extractors_managers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        icons_style = 'OUTLINER'
        scene = context.scene
        layout = layout.split(factor =0.25, align = True)
        layout.label(text = item.name, icon = item.icon)
        layout.label(text = item.description, icon=item.icon_url)

# Paradata section 
#####################################################################


#### da qui si definiscono le funzioni e gli operatori

class EM_files_opener(bpy.types.Operator):
    """If the button is grey, set the path to a DosCo folder in the EM setup panel above"""
    bl_idname = "open.file"
    bl_label = "Open a file using external software or a url using the default system browser"
    bl_options = {"REGISTER", "UNDO"}

    node_type: StringProperty() # type: ignore

    #@classmethod
    #def poll(cls, context):
        # The button works if DosCo and the url field are valorised
    #    return context.scene.EMDosCo_dir 

    def execute(self, context):
        scene = context.scene        
        file_res_path = eval("scene."+self.node_type+"[scene."+self.node_type+"_index].url")
        
        if is_valid_url(file_res_path): # nel caso nel nodo fonte ci sia una risorsa online
            print(file_res_path)
            bpy.ops.wm.url_open(url=file_res_path)
        else: # nel caso nel nodo fonte ci sia una risorsa locale
            # Get the DosCo directory from the active GraphML file
            if scene.em_tools.active_file_index >= 0 and scene.em_tools.graphml_files:
                graphml = scene.em_tools.graphml_files[scene.em_tools.active_file_index]
                dosco_dir = graphml.dosco_dir
                if dosco_dir:
                    basedir = bpy.path.abspath(dosco_dir)
                    path_to_file = os.path.join(basedir, file_res_path)
                    if os.path.exists(path_to_file):
                        try:
                            if os.name == 'nt':  # Windows
                                os.startfile(path_to_file)
                            elif os.name == 'posix':  # macOS, Linux
                                opener = 'open' if sys.platform == 'darwin' else 'xdg-open'
                                subprocess.run([opener, path_to_file])
                        except Exception as e:
                            print("Error when opening the file:", e)
                            self.report({'WARNING'}, "Cannot open file: " + str(e))
                            return {'CANCELLED'}
                    else:
                        self.report({'WARNING'}, f"File not found: {path_to_file}")
                else:
                    self.report({'WARNING'}, "DosCo directory not set for the active GraphML file")
            else:
                self.report({'WARNING'}, "No active GraphML file")
                
        return {'FINISHED'}

class EM_OT_update_paradata_lists(bpy.types.Operator):
    bl_idname = "em.update_paradata_lists"
    bl_label = "Update Paradata Lists"
    bl_description = "Update all paradata lists based on streaming settings"

    def execute(self, context):
        # Dichiarare che stai usando le variabili globali
        global _paradata_update_in_progress, _paradata_refresh_needed
        
        scene = context.scene
        em_tools = context.scene.em_tools

        # Ora puoi accedere alla variabile globale
        if _paradata_update_in_progress:
            print("Skipping paradata update (already in progress)")
            # Segnala la necessità di un futuro aggiornamento ma NON eseguirlo ora
            _paradata_refresh_needed = True
            return {'FINISHED'}
        
        # Blocca gli aggiornamenti durante l'esecuzione
        _paradata_update_in_progress = True

        try:
            # Pulizia preventiva di tutte le liste - sempre sicura
            scene.em_v_properties_list.clear()
            scene.em_v_combiners_list.clear()
            scene.em_v_extractors_list.clear()
            scene.em_v_sources_list.clear()

            # Verifica che ci sia un file GraphML attivo PRIMA di continuare
            if em_tools.active_file_index < 0 or not em_tools.graphml_files:
                print("Nessun file GraphML attivo, le liste rimarranno vuote")
                set_paradata_update_state(False)
                return {'FINISHED'}  # Non è un errore, semplicemente non facciamo nulla
            
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            
            # Importa get_graph e verifica che esista
            from .s3Dgraphy import get_graph
            graph = get_graph(graphml.name)
            
            if not graph:
                print(f"Il grafo {graphml.name} non è stato trovato o è vuoto")
                set_paradata_update_state(False)
                return {'FINISHED'}  # Non è un errore, le liste rimarranno vuote
            
            # Determina il nodo di partenza (stratigrafico selezionato o tutti)
            strat_node_id = None
            if scene.paradata_streaming_mode and scene.em_list_index >= 0 and len(scene.em_list) > 0:
                strat_node_id = scene.em_list[scene.em_list_index].id_node
            
            # Aggiorna la lista delle proprietà con controlli di sicurezza
            self.update_property_list(scene, graph, strat_node_id)
            
            # Assicurati che l'indice delle proprietà sia valido
            if len(scene.em_v_properties_list) > 0:
                if scene.em_v_properties_list_index >= len(scene.em_v_properties_list):
                    scene.em_v_properties_list_index = 0

                # Procedi solo se l'indice è valido
                if (scene.em_v_properties_list_index >= 0 and 
                    scene.em_v_properties_list_index < len(scene.em_v_properties_list) and
                    hasattr(scene.em_v_properties_list[scene.em_v_properties_list_index], 'id_node')):
                    
                    prop_node_id = scene.em_v_properties_list[scene.em_v_properties_list_index].id_node
                    self.update_combiner_list(scene, graph, prop_node_id)
                    self.update_extractor_list(scene, graph, prop_node_id)
                
                # Aggiorna estrattori e documenti solo se ci sono elementi validi
                if len(scene.em_v_extractors_list) > 0:
                    if scene.em_v_extractors_list_index >= len(scene.em_v_extractors_list):
                        scene.em_v_extractors_list_index = 0
                    
                    # Solo se abbiamo estrattori e l'indice è valido, aggiorna le liste dei documenti
                    if scene.em_v_extractors_list_index >= 0:
                        ext_node_id = scene.em_v_extractors_list[scene.em_v_extractors_list_index].id_node
                        self.update_document_list(scene, graph, ext_node_id)
            else:
                # Se non ci sono proprietà, imposta l'indice a -1 e pulisci le altre liste
                scene.em_v_properties_list_index = -1
                scene.em_v_combiners_list.clear()
                scene.em_v_extractors_list.clear()
                scene.em_v_sources_list.clear()
                scene.em_v_combiners_list_index = -1
                scene.em_v_extractors_list_index = -1
                scene.em_v_sources_list_index = -1
            
            # Aggiorna la UI
            try:
                if hasattr(context, 'area') and context.area:
                    context.area.tag_redraw()
            except AttributeError:
                # L'area potrebbe non essere disponibile durante gli aggiornamenti in background
                pass
                
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Error updating paradata lists: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
        
        finally:
            # Reset dello stato
            set_paradata_update_state(False)
            
            # Invece di usare un timer complesso, segna semplicemente la necessità di aggiornare
            if _paradata_refresh_needed and scene.paradata_auto_update:
                _paradata_refresh_needed = False
                
                # Semplice messaggio di debug
                print("Update needed but skipped - use Refresh button for manual update")

            _paradata_update_in_progress = False


    

    def delayed_update(self, context):
        """Funzione per aggiornamenti ritardati, chiamata dal timer"""
        try:
            if context.scene.paradata_auto_update:
                bpy.ops.em.update_paradata_lists()
        except Exception as e:
            print(f"Error in delayed paradata update: {e}")
        
        # Ritorna None per rimuovere il timer dopo l'uso
        return None

    def update_property_list(self, scene, graph, strat_node_id=None):
        """Aggiorna la lista delle proprietà con controlli di sicurezza"""
        scene.em_v_properties_list.clear()
        
        if strat_node_id:
            # Se c'è un nodo stratigrafico selezionato, filtra le proprietà
            prop_nodes = graph.get_property_nodes_for_node(strat_node_id)
            print(f"Trovate {len(prop_nodes)} proprietà per il nodo {strat_node_id}")
        else:
            # Altrimenti prendi tutte le proprietà
            prop_nodes = [node for node in graph.nodes if hasattr(node, 'node_type') and node.node_type == "property"]
            print(f"Trovate {len(prop_nodes)} proprietà totali")
        
        for prop_node in prop_nodes:
            item = scene.em_v_properties_list.add()
            item.name = prop_node.name
            item.description = prop_node.description if hasattr(prop_node, 'description') else ""
            item.url = prop_node.value if hasattr(prop_node, 'value') else ""
            
            # Protezione contro funzioni esterne non trovate
            try:
                from .functions import check_objs_in_scene_and_provide_icon_for_list_element
                item.icon = check_objs_in_scene_and_provide_icon_for_list_element(prop_node.name)
            except Exception:
                item.icon = "RESTRICT_INSTANCED_ON"
                
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = prop_node.node_id

    def update_combiner_list(self, scene, graph, prop_node_id):
        """Aggiorna la lista dei combiner in modo sicuro"""
        scene.em_v_combiners_list.clear()
        
        if not scene.prop_paradata_streaming_mode:
            combiners = [node for node in graph.nodes if hasattr(node, 'node_type') and node.node_type == "combiner"]
        else:
            try:
                combiners = graph.get_combiner_nodes_for_property(prop_node_id)
            except Exception as e:
                print(f"Errore nel recupero dei combiners: {e}")
                combiners = []
        
        print(f"Trovati {len(combiners)} combiner per la proprietà {prop_node_id}")
        
        for combiner in combiners:
            item = scene.em_v_combiners_list.add()
            item.name = combiner.name if hasattr(combiner, 'name') and combiner.name is not None else ""
            item.description = combiner.description if hasattr(combiner, 'description') and combiner.description is not None else ""
            
            # Assicuriamoci che url non sia mai None
            if hasattr(combiner, 'url') and combiner.url is not None:
                item.url = combiner.url
            elif hasattr(combiner, 'sources') and combiner.sources and len(combiner.sources) > 0:
                item.url = combiner.sources[0]
            else:
                item.url = ""
                
            try:
                from .functions import check_objs_in_scene_and_provide_icon_for_list_element
                item.icon = check_objs_in_scene_and_provide_icon_for_list_element(combiner.name)
            except Exception:
                item.icon = "RESTRICT_INSTANCED_ON"
                
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = combiner.node_id
        
        # Resetta l'indice a un valore valido o -1 se la lista è vuota
        if len(scene.em_v_combiners_list) > 0:
            if scene.em_v_combiners_list_index >= len(scene.em_v_combiners_list):
                scene.em_v_combiners_list_index = 0
        else:
            scene.em_v_combiners_list_index = -1

    def update_extractor_list(self, scene, graph, node_id):
        """Aggiorna la lista degli estrattori in modo sicuro"""
        scene.em_v_extractors_list.clear()
        
        extractors = []
        
        if scene.prop_paradata_streaming_mode:
            # Se è attivo lo streaming, usa il nodo_id passato (proprietà)
            try:
                property_extractors = graph.get_extractor_nodes_for_node(node_id)
                extractors.extend(property_extractors)
                print(f"Estrattori dalla proprietà: {len(property_extractors)}")
            
                # Se c'è un combiner selezionato, aggiungi anche i suoi estrattori
                if scene.comb_paradata_streaming_mode and scene.em_v_combiners_list_index >= 0 and len(scene.em_v_combiners_list) > 0:
                    comb_node_id = scene.em_v_combiners_list[scene.em_v_combiners_list_index].id_node
                    combiner_extractors = graph.get_extractor_nodes_for_node(comb_node_id)
                    extractors.extend(combiner_extractors)
                    print(f"Estrattori dal combiner: {len(combiner_extractors)}")
            except Exception as e:
                print(f"Errore nel recupero degli estrattori: {e}")
        else:
            # Altrimenti prendi tutti gli estrattori
            extractors = [node for node in graph.nodes if hasattr(node, 'node_type') and node.node_type == "extractor"]
            print(f"Tutti gli estrattori: {len(extractors)}")
        
        # Rimuovi duplicati in modo sicuro
        seen = set()
        unique_extractors = []
        for x in extractors:
            if hasattr(x, 'node_id') and x.node_id not in seen:
                seen.add(x.node_id)
                unique_extractors.append(x)
        
        print(f"Estrattori unici: {len(unique_extractors)}")
        
        # Popola la lista
        for extractor in unique_extractors:
            item = scene.em_v_extractors_list.add()
            item.name = extractor.name if hasattr(extractor, 'name') and extractor.name is not None else ""
            item.description = extractor.description if hasattr(extractor, 'description') and extractor.description is not None else ""
            
            # Determina l'URL appropriata (source o url)
            if hasattr(extractor, 'source') and extractor.source is not None:
                item.url = extractor.source
            elif hasattr(extractor, 'url') and extractor.url is not None:
                item.url = extractor.url
            else:
                item.url = ""
                
            try:
                from .functions import check_objs_in_scene_and_provide_icon_for_list_element
                item.icon = check_objs_in_scene_and_provide_icon_for_list_element(extractor.name)
            except Exception:
                item.icon = "RESTRICT_INSTANCED_ON"
                
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = extractor.node_id
        
        # Resetta l'indice a un valore valido o -1 se la lista è vuota
        if len(scene.em_v_extractors_list) > 0:
            if scene.em_v_extractors_list_index >= len(scene.em_v_extractors_list):
                scene.em_v_extractors_list_index = 0
        else:
            scene.em_v_extractors_list_index = -1

    def update_document_list(self, scene, graph, extractor_id):
        """Aggiorna la lista dei documenti in modo sicuro"""
        scene.em_v_sources_list.clear()
        
        if scene.extr_paradata_streaming_mode:
            # Se è attivo lo streaming, filtra i documenti per l'estrattore
            try:
                documents = graph.get_document_nodes_for_extractor(extractor_id)
                print(f"Trovati {len(documents)} documenti per l'estrattore {extractor_id}")
            except Exception as e:
                print(f"Errore nel recupero dei documenti: {e}")
                documents = []
        else:
            # Altrimenti prendi tutti i documenti
            documents = [node for node in graph.nodes if hasattr(node, 'node_type') and node.node_type == "document"]
            print(f"Trovati {len(documents)} documenti totali")
        
        for doc in documents:
            item = scene.em_v_sources_list.add()
            item.name = doc.name if hasattr(doc, 'name') and doc.name is not None else ""
            item.description = doc.description if hasattr(doc, 'description') and doc.description is not None else ""
            item.url = doc.url if hasattr(doc, 'url') and doc.url is not None else ""
            
            try:
                from .functions import check_objs_in_scene_and_provide_icon_for_list_element
                item.icon = check_objs_in_scene_and_provide_icon_for_list_element(doc.name)
            except Exception:
                item.icon = "RESTRICT_INSTANCED_ON"
                
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = doc.node_id
        
        # Resetta l'indice a un valore valido o -1 se la lista è vuota
        if len(scene.em_v_sources_list) > 0:
            if scene.em_v_sources_list_index >= len(scene.em_v_sources_list):
                scene.em_v_sources_list_index = 0
        else:
            scene.em_v_sources_list_index = -1


# Proprietà per il controllo degli aggiornamenti automatici dei paradati
def register_auto_update_property():
    """Registra la proprietà di controllo per gli aggiornamenti automatici"""
    if not hasattr(bpy.types.Scene, "paradata_auto_update"):
        bpy.types.Scene.paradata_auto_update = bpy.props.BoolProperty(
            name="Auto Update Paradata",
            description="Automatically update paradata lists when selection changes",
            default=True  # Abilitato di default per compatibilità con il comportamento esistente
        )

classes = [
    VIEW3D_PT_ParadataPanel,
    EM_UL_properties_managers,
    EM_UL_sources_managers,
    EM_UL_extractors_managers,
    EM_UL_combiners_managers,
    EM_OT_update_paradata_lists,
    EM_files_opener,
    ParadataImageProps,
    EM_OT_load_paradata_image,
    EM_OT_save_paradata_image,
    EM_OT_previous_image,
    EM_OT_next_image
]

# Registration
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    # Register image handling properties
    bpy.types.Scene.paradata_image = bpy.props.PointerProperty(type=ParadataImageProps)

    # AGGIUNGI QUESTA RIGA
    bpy.types.Scene.paradata_auto_update = bpy.props.BoolProperty(
        name="Auto Update Paradata",
        description="Automatically update paradata lists when selection changes",
        default=True
    )

def unregister():
    # Clean up images before unregistering
    if hasattr(bpy.context.scene, "paradata_image") and bpy.context.scene.paradata_image.loaded_image:
        try:
            bpy.data.images.remove(bpy.context.scene.paradata_image.loaded_image)
        except:
            pass
        
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # Remove properties
    if hasattr(bpy.types.Scene, "paradata_image"):
        del bpy.types.Scene.paradata_image

    if hasattr(bpy.types.Scene, "paradata_auto_update"):
        del bpy.types.Scene.paradata_auto_update
