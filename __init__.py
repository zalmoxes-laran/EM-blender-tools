'''
Created by EMANUEL DEMETRESCU 2018-2025
emanuel.demetrescu@cnr.it

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

bl_info = {
    "name": "EM tools",
    "author": "E. Demetrescu",
    "version": (1, 5, 0),
    "blender": (4, 0, 0),
    "warning": "1.5.0-dev.33",
    "category": "Tools",
}

def get_bl_info():
    return bl_info

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    CollectionProperty,
    FloatVectorProperty,
)
from bpy.types import PropertyGroup

# Import external dependencies - handled automatically by Blender Extension system
import pandas
import networkx
from PIL import Image

# Import addon modules
from . import (
    EM_list,
    epoch_manager,
    functions,
    paradata_manager,
    export_manager,
    visual_tools,
    visual_manager,
    em_setup,
    EMdb_excel,
    em_statistics,
    graph2geometry,
    activity_manager,
    rm_manager,
    proxy_inflate_manager,
    anastylosis_manager
)

# Base PropertyGroup classes
class EMAddonSettings(bpy.types.PropertyGroup):
    preserve_web_url: BoolProperty(
        name="Preserve Web URL",
        description="Preserve web urls (if any) from the GraphML file",
        default=True
    )

    overwrite_url_with_dosco_filepath: BoolProperty(
        name="Overwrite URL with DosCo Filepath",
        description="Retrieve the URL from real DosCo Filepath ignoring the url values stated in the GraphML file",
        default=False
    )

    dosco_options: BoolProperty(
        name="Show Dosco Section",
        description="Info about DosCo folder loading the GraphML",
        default=False
    )

    dosco_advanced_options: BoolProperty(
        name="Show advanced options",
        description="Catch more information from DosCo folder loading the GraphML",
        default=False
    )

class EDGESListItem(PropertyGroup):
    id_node: StringProperty(
        name="id",
        description="A description for this item",
        default="Empty"
    )

    source: StringProperty(
        name="source",
        description="A description for this item",
        default="Empty"
    )

    target: StringProperty(
        name="target",
        description="A description for this item",
        default="Empty"
    )

    edge_type: StringProperty(
        name="type",
        description="A description for this item",
        default="Empty"
    )

class EPOCHListItem(PropertyGroup):
    name: StringProperty(
        name="Name",
        description="A name for this item",
        default="Untitled"
    )

    id: StringProperty(
        name="id",
        description="A description for this item",
        default="Empty"
    )

    min_y: FloatProperty(
        name="code for icon",
        description="",
        default=0.0
    )

    max_y: FloatProperty(
        name="code for icon",
        description="",
        default=0.0
    )

    height: FloatProperty(
        name="height of epoch row",
        description="",
        default=0.0
    )
       
    epoch_color: StringProperty(
        name="color of epoch row",
        description="",
        default="Empty"
    )

    start_time: FloatProperty(
        name="Start time",
        description="",
        default=0.0
    )

    end_time: FloatProperty(
        name="End time",
        description="",
        default=0.0
    )

    use_toggle: BoolProperty(name="", default=True)
    is_locked: BoolProperty(name="", default=True)
    is_selected: BoolProperty(name="", default=False)
    epoch_soloing: BoolProperty(name="", default=False)
    rm_models: BoolProperty(name="", default=False)
    reconstruction_on: BoolProperty(name="", default=False)
    
    unique_id: StringProperty(default="")

    epoch_RGB_color: FloatVectorProperty(
        name="epoch_color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 0.5)
    )

    wire_color: FloatVectorProperty(
        name="wire",
        subtype='COLOR',
        default=(0.2, 0.2, 0.2),
        min=0.0, max=1.0,
        description="wire color of the group"
    )

class EM_Other_Settings(PropertyGroup):
    select_all_layers: BoolProperty(name="Select Visible Layers", default=True)
    unlock_obj: BoolProperty(name="Unlock Objects", default=False)
    unhide_obj: BoolProperty(name="Unhide Objects", default=True)
    em_proxy_sync: BoolProperty(name="Selecting a proxy you select the corresponding EM", default=False)
    em_proxy_sync2: BoolProperty(name="Selecting an EM you select the corresponding proxy", default=False)
    em_proxy_sync2_zoom: BoolProperty(name="Option to zoom to proxy", default=False)
    soloing_mode: BoolProperty(name="Soloing mode", default=False)

class EMListItem(PropertyGroup):
    name: StringProperty(
           name="Name",
           description="A name for this item",
           default="Untitled")

    description: StringProperty(
           name="Description",
           description="A description for this item",
           default="Empty")

    icon: StringProperty(
           name="code for icon",
           description="",
           default="RESTRICT_INSTANCED_ON")

    icon_db: StringProperty(
           name="code for icon db",
           description="",
           default="DECORATE_ANIMATE")

    url: StringProperty(
           name="url",
           description="An url behind this item",
           default="Empty")

    shape: StringProperty(
           name="shape",
           description="The shape of this item",
           default="Empty")

    y_pos: FloatProperty(
           name="y_pos",
           description="The y_pos of this item",
           default=0.0)

    epoch: StringProperty(
           name="code for epoch",
           description="",
           default="Empty")

    id_node: StringProperty(
           name="id node",
           description="",
           default="Empty")
    
    border_style: StringProperty(
           name="border style",
           description="",
           default="Empty")    

    fill_color: StringProperty(
           name="fill color",
           description="",
           default="Empty")
           
    is_visible: BoolProperty(
           name="Visible",
           description="Whether this item is visible in the viewport",
           default=True)

    node_type: StringProperty(
           name="Node Type",
           description="The type of this node",
           default="")

class EMreusedUS(PropertyGroup):
    epoch: StringProperty(
           name="epoch",
           description="Epoch",
           default="Untitled")

    em_element: StringProperty(
           name="em_element",
           description="",
           default="Empty")

class EMviqListErrors(PropertyGroup):
    name: StringProperty( 
           name="Object",
           description="The object with an error",
           default="Empty")

    description: StringProperty(
           name="Description",
           description="A description of the error",
           default="Empty")

    material: StringProperty(
           name="material",
           description="",
           default="Empty")

    texture_type: StringProperty(
           name="texture_type",
           description="",
           default="Empty")

class EMListParadata(PropertyGroup):
    name: StringProperty(
           name="Name",
           description="A name for this item",
           default="Untitled")

    description: StringProperty(
           name="Description",
           description="A description for this item",
           default="Empty")

    icon: StringProperty(
           name="code for icon",
           description="",
           default="RESTRICT_INSTANCED_ON")

    icon_url: StringProperty(
           name="code for icon url",
           description="",
           default="CHECKBOX_DEHLT")

    url: StringProperty(
           name="url",
           description="An url behind this item",
           default="Empty")

    id_node: StringProperty(
           name="id_node",
           description="The id node of this item",
           default="Empty")

class EM_epochs_belonging_ob(PropertyGroup):
    epoch: StringProperty(
           name="epoch",
           description="Epoch",
           default="Untitled")

class ExportVars(PropertyGroup):
    format_file: bpy.props.EnumProperty(
        items=[
        ('gltf','gltf','gltf','', 0),
        ('obj','obj','obj','', 1),
        ('fbx','fbx','fbx','', 2),
        ],
        default='gltf'
    )

    heriverse_expanded: BoolProperty(
        name="Show Heriverse export options",
        description="Expand/Collapse Heriverse export options",
        default=False
    )

    emviq_expanded: BoolProperty(
        name="Show Emviq export options",
        description="Expand/Collapse Emviq export options",
        default=False
    )

    heriverse_project_name: StringProperty(
        name="Project Name", 
        description="Name of the Heriverse project",
        default=""
    )

    heriverse_export_path: StringProperty(
        name="Export Path",
        description="Path where to export Heriverse project",
        subtype='DIR_PATH'
    )

    heriverse_export_all_graphs: BoolProperty(
        name="Export all graphs",
        description="Export all loaded graphs instead of just the selected one",
        default=False
    )

    heriverse_overwrite_json: BoolProperty(
        name="Overwrite JSON",
        description="Overwrite existing JSON file",
        default=True
    )

    heriverse_export_dosco: BoolProperty(
        name="Export DosCo files",
        description="Copy DosCo files to output",
        default=True
    )

    heriverse_export_proxies: BoolProperty(
        name="Export proxies",
        description="Export proxy models",
        default=True
    )

    heriverse_export_rm: BoolProperty(
        name="Export RM",
        description="Export representation models",
        default=True
    )

    heriverse_create_zip: BoolProperty(
        name="Create ZIP archive",
        description="Create a ZIP archive of the exported project",
        default=True
    )

    heriverse_advanced_options: BoolProperty(
        name="Show advanced options",
        description="Show advanced export options like compression settings",
        default=False
    )

    heriverse_use_draco: BoolProperty(
        name="Use Draco compression",
        description="Enable Draco mesh compression for smaller file size",
        default=True
    )

    heriverse_draco_level: IntProperty(
        name="Compression Level",
        description="Draco compression level (higher = smaller files but slower)",
        min=1,
        max=10,
        default=6
    )

    heriverse_separate_textures: BoolProperty(
        name="Export textures separately",
        description="Export textures as separate files instead of embedding",
        default=True
    )

    heriverse_use_gpu_instancing: BoolProperty(
        name="Use GPU Instancing",
        description="Enable GPU instancing for models with shared meshes (improved performance)",
        default=True
    )

    heriverse_skip_extracted_tilesets: BoolProperty(
        name="Skip Previously Extracted Tilesets",
        description="Skip tileset extraction if already extracted in the destination folder",
        default=True
    )

    heriverse_export_rmdoc: BoolProperty(
        name="Export ParaData Objects",
        description="Export 3D objects associated with ParaData nodes (Documents, Extractors, Combiners)",
        default=True
    )

    heriverse_export_rmsf: BoolProperty(
        name="Export Special Finds Models",
        description="Export 3D models associated with Special Finds (SF) nodes",
        default=True
    )

class ExportTablesVars(PropertyGroup):
    table_type: bpy.props.EnumProperty(
        items=[
        ('US/USV','US/USV','US/USV','', 0),
        ('Sources','Sources','Sources','', 1),
        ('Extractors','Extractors','Extractors','', 2),
        ],
        default='US/USV'
    )

class EMUSItem(PropertyGroup):
    name: StringProperty(name="Name", default="")
    description: StringProperty(name="Description", default="")
    status: StringProperty(name="Status", default="")
    y_pos: StringProperty(name="y_pos", default="")

class em_create_collection(bpy.types.Operator):
    bl_idname = "create.collection"
    bl_label = "Create Collection"
    bl_description = "Create Collection"
    bl_options = {'REGISTER', 'UNDO'}

    def create_collection(target_collection):
        context = bpy.context
        if bpy.data.collections.get(target_collection) is None:
            currentCol = bpy.context.blend_data.collections.new(name=target_collection)
            bpy.context.scene.collection.children.link(currentCol)
        else:
            currentCol = bpy.data.collections.get(target_collection)
        return currentCol

# List of base classes
base_classes = [
    EMAddonSettings,
    EDGESListItem,
    EPOCHListItem,
    EM_Other_Settings,
    EMListItem,
    EMreusedUS,
    EMviqListErrors,
    EMListParadata,
    EM_epochs_belonging_ob,
    ExportVars,
    ExportTablesVars,
    EMUSItem,
    em_create_collection
]

def register():
    """Simplified registration for extension"""
    # Register base classes
    for cls in base_classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Already registered, skip
            pass
    
    # Import required modules
    from .import_operators import importer_graphml
    from .export_operators import exporter_heriverse
    from .import_operators import import_EMdb
    from . import populate_lists
    from .s3Dgraphy.utils.utils import get_material_color
    from .operators import graphml_converter
    
    # UI classes
    ui_classes = [
        functions.OBJECT_OT_CenterMass,
        functions.OBJECT_OT_labelonoff,
        visual_tools.EM_label_creation,
    ]
    
    for cls in ui_classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    
    # Initialize properties
    bpy.types.Scene.em_graph = None
    
    # Scene collection properties
    scene_collections = [
        ('selected_epoch_us_list', EMUSItem),
        ('emviq_error_list', EMviqListErrors),
        ('em_list', EMListItem),
        ('em_reused', EMreusedUS),
        ('epoch_list', EPOCHListItem),
        ('edges_list', EDGESListItem),
        ('em_sources_list', EMListParadata),
        ('em_properties_list', EMListParadata),
        ('em_extractors_list', EMListParadata),
        ('em_combiners_list', EMListParadata),
        ('em_v_sources_list', EMListParadata),
        ('em_v_properties_list', EMListParadata),
        ('em_v_extractors_list', EMListParadata),
        ('em_v_combiners_list', EMListParadata),
    ]
    
    for prop_name, prop_type in scene_collections:
        if not hasattr(bpy.types.Scene, prop_name):
            setattr(bpy.types.Scene, prop_name, CollectionProperty(type=prop_type))
    
    # Scene index properties
    scene_indices = [
        ('selected_epoch_us_list_index', 0, lambda self, context: bpy.ops.epoch_manager.update_us_list()),
        ('emviq_error_list_index', 0, functions.switch_paradata_lists),
        ('em_list_index', 0, functions.switch_paradata_lists),
        ('em_sources_list_index', 0, None),
        ('em_properties_list_index', 0, None),
        ('em_extractors_list_index', 0, None),
        ('em_combiners_list_index', 0, None),
        ('em_v_sources_list_index', 0, None),
        ('em_v_properties_list_index', 0, functions.stream_properties),
        ('em_v_extractors_list_index', 0, functions.stream_extractors),
        ('em_v_combiners_list_index', 0, functions.stream_combiners),
    ]
    
    for prop_name, default, update_func in scene_indices:
        if not hasattr(bpy.types.Scene, prop_name):
            props = {'name': f"Index for {prop_name}", 'default': default}
            if update_func:
                props['update'] = update_func
            setattr(bpy.types.Scene, prop_name, IntProperty(**props))
    
    # Other scene properties
    scene_props = [
        ('paradata_streaming_mode', BoolProperty, 
            {"name": "Paradata streaming mode", "description": "Enable/disable tables streaming mode", 
             "default": True, "update": functions.switch_paradata_lists}),
        ('prop_paradata_streaming_mode', BoolProperty,
            {"name": "Properties Paradata streaming mode", "description": "Enable/disable property table streaming mode",
             "default": True, "update": functions.stream_properties}),
        ('comb_paradata_streaming_mode', BoolProperty,
            {"name": "Combiners Paradata streaming mode", "description": "Enable/disable combiner table streaming mode",
             "default": True, "update": functions.stream_combiners}),
        ('extr_paradata_streaming_mode', BoolProperty,
            {"name": "Extractors Paradata streaming mode", "description": "Enable/disable extractor table streaming mode",
             "default": True, "update": functions.stream_extractors}),
        ('proxy_shader_mode', BoolProperty,
            {"name": "Proxy shader mode", "description": "Enable additive shader for proxies",
             "default": True, "update": functions.proxy_shader_mode_function}),
    ]
    
    for prop_name, prop_type, prop_kwargs in scene_props:
        if not hasattr(bpy.types.Scene, prop_name):
            setattr(bpy.types.Scene, prop_name, prop_type(**prop_kwargs))
    
    # String properties
    scene_string_props = [
        ('EM_file', "Define the path to the EM GraphML file", ''),
        ('EMviq_folder', "Define the path to export the EMviq collection", ''),
        ('EMviq_scene_folder', "Define the path to export the EMviq scene", ''),
        ('EMviq_project_name', "Define the name of the EMviq project", ''),
        ('EMviq_user_name', "Define the name of the EMviq user", ''),
        ('EMviq_user_password', "Define the name of the EMviq user", 'PASSWORD'),
        ('ATON_path', "Define the path to the ATON framework (root folder)", ''),
        ('EMviq_model_author_name', "Define the name of the author(s) of the models", ''),
    ]
    
    for prop_name, description, subtype in scene_string_props:
        if not hasattr(bpy.types.Scene, prop_name):
            props = {'name': prop_name, 'default': "", 'description': description}
            if subtype:
                props['subtype'] = subtype
            setattr(bpy.types.Scene, prop_name, StringProperty(**props))
    
    # Other property groups
    if not hasattr(bpy.types.Scene, 'em_settings'):
        bpy.types.Scene.em_settings = PointerProperty(type=EM_Other_Settings)
    
    # Display mode properties
    scene_mode_props = [
        ('proxy_display_mode', "Proxy display mode", "select"),
        ('proxy_blend_mode', "Proxy blend mode", "BLEND"),
    ]
    
    for prop_name, name, default in scene_mode_props:
        if not hasattr(bpy.types.Scene, prop_name):
            setattr(bpy.types.Scene, prop_name, StringProperty(
                name=name, default=default, description=f"{name} for current display mode"))
    
    # Alpha property
    if not hasattr(bpy.types.Scene, 'proxy_display_alpha'):
        bpy.types.Scene.proxy_display_alpha = FloatProperty(
            name="alpha", description="The alpha value for proxies",
            min=0, max=1, default=0.5, update=functions.update_display_mode)
    
    # GLTF export properties
    scene_gltf_props = [
        ('EM_gltf_export_quality', "export quality", 
            "Define the quality of the output images", 100),
        ('EM_gltf_export_maxres', "export max resolution", 
            "Define the maximum resolution of the output images", 4096),
    ]
    
    for prop_name, name, description, default in scene_gltf_props:
        if not hasattr(bpy.types.Scene, prop_name):
            setattr(bpy.types.Scene, prop_name, IntProperty(
                name=name, description=description, default=default))
    
    # WindowManager properties
    if not hasattr(bpy.types.WindowManager, 'em_addon_settings'):
        bpy.types.WindowManager.em_addon_settings = PointerProperty(type=EMAddonSettings)
    
    if not hasattr(bpy.types.WindowManager, 'export_vars'):
        bpy.types.WindowManager.export_vars = PointerProperty(type=ExportVars)
    
    if not hasattr(bpy.types.WindowManager, 'export_tables_vars'):
        bpy.types.WindowManager.export_tables_vars = PointerProperty(type=ExportTablesVars)
    
    # Object properties
    if not hasattr(bpy.types.Object, 'EM_ep_belong_ob'):
        bpy.types.Object.EM_ep_belong_ob = CollectionProperty(type=EM_epochs_belonging_ob)
        bpy.types.Object.EM_ep_belong_ob_index = IntProperty()
    
    # Add menu function
    bpy.types.VIEW3D_MT_mesh_add.append(functions.menu_func)
    
    # Register modules
    modules_to_register = [
        em_setup,
        visual_manager,
        EMdb_excel,
        activity_manager,
        EM_list,
        epoch_manager,
        paradata_manager,
        anastylosis_manager,
        rm_manager,
        export_manager,
        em_statistics,
        graph2geometry,
        importer_graphml,
        exporter_heriverse,
        import_EMdb,
        graphml_converter,
        proxy_inflate_manager
    ]
    
    for module in modules_to_register:
        try:
            module.register()
        except Exception as e:
            print(f"Error registering {module.__name__}: {e}")
    
    print("EM Tools: Registration complete")

def unregister():
    """Simplified unregistration for extension"""
    # Import modules for unregistration
    from . import (
        activity_manager,
        graph2geometry,
        epoch_manager,
        em_statistics,
        export_manager,
        EM_list,
        EMdb_excel,
        visual_manager,
        em_setup,
        rm_manager,
        paradata_manager,
        proxy_inflate_manager,
        anastylosis_manager,
        functions
    )
    
    from .export_operators import exporter_heriverse
    from .import_operators import importer_graphml, import_EMdb
    from .operators import graphml_converter
    
    # Unregister modules
    modules_to_unregister = [
        graphml_converter,
        import_EMdb,
        exporter_heriverse,
        importer_graphml,
        activity_manager,
        graph2geometry,
        rm_manager,
        anastylosis_manager,
        paradata_manager,
        epoch_manager,
        em_statistics,
        export_manager,
        EM_list,
        EMdb_excel,
        visual_manager,
        em_setup,
        proxy_inflate_manager
    ]
    
    for module in modules_to_unregister:
        try:
            module.unregister()
        except:
            pass
    
    # Remove menu function
    try:
        bpy.types.VIEW3D_MT_mesh_add.remove(functions.menu_func)
    except:
        pass
    
    # Remove properties
    props_to_remove = [
        (bpy.types.WindowManager, 'export_vars'),
        (bpy.types.WindowManager, 'export_tables_vars'),
        (bpy.types.WindowManager, 'em_addon_settings'),
        (bpy.types.Scene, 'EM_gltf_export_maxres'),
        (bpy.types.Scene, 'EM_gltf_export_quality'),
        (bpy.types.Object, 'EM_ep_belong_ob_index'),
        (bpy.types.Object, 'EM_ep_belong_ob'),
        (bpy.types.Scene, 'proxy_display_alpha'),
        (bpy.types.Scene, 'proxy_blend_mode'),
        (bpy.types.Scene, 'proxy_display_mode'),
        (bpy.types.Scene, 'em_settings'),
        (bpy.types.Scene, 'EMviq_model_author_name'),
        (bpy.types.Scene, 'ATON_path'),
        (bpy.types.Scene, 'EMviq_user_password'),
        (bpy.types.Scene, 'EMviq_user_name'),
        (bpy.types.Scene, 'EMviq_project_name'),
        (bpy.types.Scene, 'EMviq_scene_folder'),
        (bpy.types.Scene, 'EMviq_folder'),
        (bpy.types.Scene, 'EM_file'),
        # ... all other properties
    ]
    
    for prop_owner, prop_name in props_to_remove:
        if hasattr(prop_owner, prop_name):
            try:
                delattr(prop_owner, prop_name)
            except:
                pass
    
    # Unregister base classes
    for cls in reversed(base_classes):
        try:
            bpy.utils.unregister_class(cls)
        except:
            pass