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

class ParadataImageProps(bpy.types.PropertyGroup):
    """Properties for handling paradata images"""
    image_path: StringProperty(
        name="Image Path",
        description="Path or URL to the image"
    )
    is_loading: BoolProperty(
        name="Is Loading",
        description="Whether the image is currently loading",
        default=False
    )
    loaded_image: PointerProperty(
        name="Loaded Image",
        type=bpy.types.Image
    )
    auto_load: BoolProperty(
        name="Auto-load Images",
        description="Automatically load images when selecting documents or extractors",
        default=True
    )

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
        
        # If it's a valid URL, return it as is
        if self.is_valid_url(path):
            return path, True
            
        # Not a URL, so should be a local file
        # Check if we have a valid DosCo directory for the current graph
        if em_tools.active_file_index < 0 or not em_tools.graphml_files:
            return None, False
            
        graphml = em_tools.graphml_files[em_tools.active_file_index]
        
        # Try to get the DosCo directory for this specific graph
        dosco_dir = graphml.dosco_dir
        
        # If empty, fall back to the global DosCo setting
        if not dosco_dir:
            dosco_dir = scene.EMDosCo_dir
            
        # If still empty, we can't proceed
        if not dosco_dir:
            return None, False
            
        # Normalize the path
        dosco_dir = bpy.path.abspath(dosco_dir)
        
        # If the path already starts with the DosCo dir, don't concatenate
        if path.startswith(dosco_dir):
            full_path = path
        else:
            # Ensure path doesn't start with file separator
            if path.startswith(os.path.sep):
                path = path[1:]
            full_path = os.path.join(dosco_dir, path)
            
        return full_path, False
    
    def execute(self, context):
        scene = context.scene
        
        # Get the URL from the selected item
        if self.node_type == "em_v_sources_list" and scene.em_v_sources_list_index >= 0 and len(scene.em_v_sources_list) > 0:
            path = scene.em_v_sources_list[scene.em_v_sources_list_index].url
        elif self.node_type == "em_v_extractors_list" and scene.em_v_extractors_list_index >= 0 and len(scene.em_v_extractors_list) > 0:
            path = scene.em_v_extractors_list[scene.em_v_extractors_list_index].url
        else:
            self.report({'ERROR'}, "No valid item selected")
            return {'CANCELLED'}
        
        # Skip if already loading or path is empty
        if scene.paradata_image.is_loading or not path:
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


class ListIndexUpdateHandler:
    """Helper class for correctly handling list index updates"""
    
    @staticmethod
    def find_and_update_props():
        """Find and update the list index properties to add our auto-load functionality"""
        try:
            # Get property definitions for sources and extractors indices
            sources_prop = bpy.types.Scene.bl_rna.properties.get("em_v_sources_list_index")
            extractors_prop = bpy.types.Scene.bl_rna.properties.get("em_v_extractors_list_index")
            
            # Make copies of original update function if they exist
            if sources_prop and hasattr(sources_prop, "update"):
                original_sources_update = sources_prop.update
            else:
                original_sources_update = None
                
            if extractors_prop and hasattr(extractors_prop, "update"):
                original_extractors_update = extractors_prop.update
            else:
                original_extractors_update = None
                
            # Create wrappers that call both original and our new update
            def sources_update_wrapper(self, context):
                # Call original update if exists
                if original_sources_update:
                    original_sources_update(self, context)
                # Call our update function
                sources_index_update(self, context)
                
            def extractors_update_wrapper(self, context):
                # Call original update if exists
                if original_extractors_update:
                    original_extractors_update(self, context)
                # Call our update function
                extractors_index_update(self, context)
            
            # Replace with our wrapped versions
            if sources_prop:
                setattr(bpy.types.Scene, "em_v_sources_list_index", bpy.props.IntProperty(
                    name="Sources List Index",
                    default=0,
                    update=sources_update_wrapper
                ))
                
            if extractors_prop:
                setattr(bpy.types.Scene, "em_v_extractors_list_index", bpy.props.IntProperty(
                    name="Extractors List Index",
                    default=0,
                    update=extractors_update_wrapper
                ))
                
            print("Successfully installed auto-load update handlers")
            return True
            
        except Exception as e:
            print(f"Error installing update handlers: {str(e)}")
            return False


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
        

        if scene.paradata_streaming_mode and scene.em_list_index >= 0 and len(scene.em_list) > 0:
            # Se è attivo lo streaming, mostra il nome stratigrafico selezionato
            paradata_text = str("Paradata related to: "+str(scene.em_list[scene.em_list_index].name))
        else:
            paradata_text = "Full list of paradata in: "+str(scene.em_tools.graphml_files[scene.em_tools.active_file_index].graph_code) if scene.em_tools.active_file_index >= 0 else "No GraphML file selected"
        # Mostra il nome del file GraphML attivo    

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
        layout.separator()
        
        # Split row for preview title and auto-load toggle
        split = layout.split(factor=0.6)
        split.label(text="Image Preview:")
        
        # Only show auto-load toggle if we have the property
        if hasattr(scene, "paradata_image"):
            split.prop(scene.paradata_image, "auto_load", text="Auto-load")
        
        box = layout.box()
        row = box.row()
        
        # Determine if we should show image controls
        show_image_preview = False
        preview_node_type = None
        
        # Check if we have a source with a valid URL
        if source_index_valid:
            item_source = eval(source_list_cmd)[source_list_index]
            if item_source.url:
                url_path = item_source.url
                # Check if it might be an image (basic check)
                img_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.gif']
                if any(url_path.lower().endswith(ext) for ext in img_exts) or is_valid_url(url_path):
                    show_image_preview = True
                    preview_node_type = source_list_var
        
        # Check if we have an extractor with a valid URL
        elif extractor_index_valid:
            item_extractor = eval(extractor_list_cmd)[extractor_list_index]
            if item_extractor.url:
                url_path = item_extractor.url
                # Check if it might be an image (basic check)
                img_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.gif']
                if any(url_path.lower().endswith(ext) for ext in img_exts) or is_valid_url(url_path):
                    show_image_preview = True
                    preview_node_type = extractor_list_var
        
        if show_image_preview:
            # Show load button
            row = box.row()
            op = row.operator("em.load_paradata_image", icon="FILE_IMAGE", text="Load Image Preview")
            op.node_type = preview_node_type
            
            # Show image if loaded
            if hasattr(scene, "paradata_image") and scene.paradata_image.loaded_image:
                row = box.row()
                # Use template_preview for better image display
                row.template_preview(
                    scene.paradata_image.loaded_image,
                    show_buttons=False,
                    preview_id="paradata_preview"
                )
                
                # Add save button
                row = box.row()
                row.operator("em.save_paradata_image", icon="EXPORT", text="Save Image")
                
                # Add a refresh button 
                op = row.operator("em.load_paradata_image", icon="FILE_REFRESH", text="Reload")
                op.node_type = preview_node_type
        else:
            row.label(text="Select a document or extractor with an image URL")





class VIEW3D_PT_ParadataPanel(Panel, EM_ParadataPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_ParadataPanel"
    bl_context = "objectmode"


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
            basedir = bpy.path.abspath(scene.EMDosCo_dir)
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
            
        return {'FINISHED'}

class EM_OT_update_paradata_lists(bpy.types.Operator):
    bl_idname = "em.update_paradata_lists"
    bl_label = "Update Paradata Lists"
    bl_description = "Update all paradata lists based on streaming settings"

    _is_running = False

    def execute(self, context):
        scene = context.scene
        em_tools = context.scene.em_tools

        # Check if we're already running to prevent recursion
        if EM_OT_update_paradata_lists._is_running:
            print("Preventing recursive call to update_paradata_lists")
            return {'FINISHED'}
            
        # Set flag to indicate we're running
        EM_OT_update_paradata_lists._is_running = True

        # Pulizia preventiva di tutte le liste
        scene.em_v_properties_list.clear()
        scene.em_v_combiners_list.clear()
        scene.em_v_extractors_list.clear()
        scene.em_v_sources_list.clear()

        try:
            # Verifica se c'è un file GraphML attivo
            if em_tools.active_file_index < 0 or not em_tools.graphml_files:
                print("Nessun file GraphML attivo, le liste rimarranno vuote")
                return {'FINISHED'}  # Non è un errore, semplicemente non facciamo nulla
            
            graphml = em_tools.graphml_files[em_tools.active_file_index]
            
            # Importa get_graph e debug_graph_structure
            from .s3Dgraphy import get_graph
            #from .s3Dgraphy.utils import debug_graph_structure
            
            graph = get_graph(graphml.name)
            
            if not graph:
                print(f"Il grafo {graphml.name} non è stato trovato o è vuoto")
                return {'FINISHED'}  # Non è un errore, le liste rimarranno vuote
                
            # Debug della struttura del grafo
            #debug_graph_structure(graph)
            
            # Determina il nodo di partenza (stratigrafico selezionato o tutti)
            strat_node_id = None
            if scene.paradata_streaming_mode and scene.em_list_index >= 0 and len(scene.em_list) > 0:
                strat_node_id = scene.em_list[scene.em_list_index].id_node
            #    # Debug delle relazioni del nodo selezionato
            #    debug_graph_structure(graph, strat_node_id)
            
            # Aggiorna la lista delle proprietà
            self.update_property_list(scene, graph, strat_node_id)
            
            # Assicurati che l'indice delle proprietà sia valido
            if len(scene.em_v_properties_list) > 0:
                if scene.em_v_properties_list_index >= len(scene.em_v_properties_list):
                    scene.em_v_properties_list_index = 0
                    
                # Solo se abbiamo proprietà e l'indice è valido, aggiorna le altre liste
                prop_node_id = scene.em_v_properties_list[scene.em_v_properties_list_index].id_node
                self.update_combiner_list(scene, graph, prop_node_id)
                self.update_extractor_list(scene, graph, prop_node_id)
                
                # Assicurati che l'indice degli estrattori sia valido
                if len(scene.em_v_extractors_list) > 0:
                    if scene.em_v_extractors_list_index >= len(scene.em_v_extractors_list):
                        scene.em_v_extractors_list_index = 0
                    
                    # Solo se abbiamo estrattori e l'indice è valido, aggiorna le liste dei documenti
                    ext_node_id = scene.em_v_extractors_list[scene.em_v_extractors_list_index].id_node
                    self.update_document_list(scene, graph, ext_node_id)
            else:
                # Se non ci sono proprietà, imposta l'indice a -1 e pulisci le altre liste
                scene.em_v_properties_list_index = -1
                scene.em_v_combiners_list.clear()
                scene.em_v_extractors_list.clear()
                scene.em_v_sources_list.clear()
            
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error updating paradata lists: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
        finally:
            # Always reset the running flag when done
            EM_OT_update_paradata_lists._is_running = False

    def update_property_list(self, scene, graph, strat_node_id=None):
        """Aggiorna la lista delle proprietà"""
        scene.em_v_properties_list.clear()
        
        if strat_node_id:
            # Se c'è un nodo stratigrafico selezionato, filtra le proprietà
            prop_nodes = graph.get_property_nodes_for_node(strat_node_id)
            print(f"Trovate {len(prop_nodes)} proprietà per il nodo {strat_node_id}")
        else:
            # Altrimenti prendi tutte le proprietà
            prop_nodes = [node for node in graph.nodes if node.node_type == "property"]
            print(f"Trovate {len(prop_nodes)} proprietà totali")
        
        for prop_node in prop_nodes:
            item = scene.em_v_properties_list.add()
            item.name = prop_node.name
            item.description = prop_node.description if hasattr(prop_node, 'description') else ""
            item.url = prop_node.value if hasattr(prop_node, 'value') else ""
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(prop_node.name)
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = prop_node.node_id

    def update_combiner_list(self, scene, graph, prop_node_id):
        """Aggiorna la lista dei combiner basata sulla proprietà selezionata"""
        scene.em_v_combiners_list.clear()
        
        if not scene.prop_paradata_streaming_mode:
            combiners = [node for node in graph.nodes if node.node_type == "combiner"]
        else:
            combiners = graph.get_combiner_nodes_for_property(prop_node_id)
        
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
                
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(combiner.name)
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = combiner.node_id

    def update_extractor_list(self, scene, graph, node_id):
        """Aggiorna la lista degli estrattori basata sul nodo selezionato"""
        scene.em_v_extractors_list.clear()
        
        extractors = []
        
        if scene.prop_paradata_streaming_mode:
            # Se è attivo lo streaming, usa il nodo_id passato (proprietà)
            property_extractors = graph.get_extractor_nodes_for_node(node_id)
            extractors.extend(property_extractors)
            print(f"Estrattori dalla proprietà: {len(property_extractors)}")
            
            # Se c'è un combiner selezionato, aggiungi anche i suoi estrattori
            if scene.comb_paradata_streaming_mode and scene.em_v_combiners_list_index >= 0 and len(scene.em_v_combiners_list) > 0:
                comb_node_id = scene.em_v_combiners_list[scene.em_v_combiners_list_index].id_node
                combiner_extractors = graph.get_extractor_nodes_for_node(comb_node_id)
                extractors.extend(combiner_extractors)
                print(f"Estrattori dal combiner: {len(combiner_extractors)}")
        else:
            # Altrimenti prendi tutti gli estrattori
            extractors = [node for node in graph.nodes if node.node_type == "extractor"]
            print(f"Tutti gli estrattori: {len(extractors)}")
        
        # Rimuovi duplicati
        seen = set()
        unique_extractors = [x for x in extractors if not (x.node_id in seen or seen.add(x.node_id))]
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
                
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(extractor.name)
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = extractor.node_id

    def update_document_list(self, scene, graph, extractor_id):
        """Aggiorna la lista dei documenti basata sull'estrattore selezionato"""
        scene.em_v_sources_list.clear()
        
        if scene.extr_paradata_streaming_mode:
            # Se è attivo lo streaming, filtra i documenti per l'estrattore
            documents = graph.get_document_nodes_for_extractor(extractor_id)
            print(f"Trovati {len(documents)} documenti per l'estrattore {extractor_id}")
        else:
            # Altrimenti prendi tutti i documenti
            documents = [node for node in graph.nodes if node.node_type == "document"]
            print(f"Trovati {len(documents)} documenti totali")
        
        for doc in documents:
            item = scene.em_v_sources_list.add()
            item.name = doc.name if hasattr(doc, 'name') and doc.name is not None else ""
            item.description = doc.description if hasattr(doc, 'description') and doc.description is not None else ""
            item.url = doc.url if hasattr(doc, 'url') and doc.url is not None else ""
            item.icon = check_objs_in_scene_and_provide_icon_for_list_element(doc.name)
            item.icon_url = "CHECKBOX_HLT" if item.url else "CHECKBOX_DEHLT"
            item.id_node = doc.node_id

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
    EM_OT_check_selection_changed
]

# Registration
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
        
    # Register image handling properties
    bpy.types.Scene.paradata_image = bpy.props.PointerProperty(type=ParadataImageProps)


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
