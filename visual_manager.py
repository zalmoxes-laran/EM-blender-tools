import bpy

from bpy.types import Panel
from bpy.types import Operator
from bpy.types import PropertyGroup
from bpy.types import UIList

from .functions import *
from .property_colors import *

import os
from bpy_extras.io_utils import ImportHelper, ExportHelper # type: ignore

from bpy.props import (BoolProperty, # type: ignore
                       StringProperty,
                       EnumProperty,
                       CollectionProperty
                       )

from .s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode
from .s3Dgraphy.nodes.property_node import PropertyNode

from .s3Dgraphy import get_graph
from .s3Dgraphy import get_all_graph_ids


import json
import os
import shutil

import logging
log = logging.getLogger(__name__)


def update_selected_property(self, context):
    bpy.ops.update.property_values()

bpy.types.Scene.selected_property = bpy.props.StringProperty(
    name="Selected Property",
    description="Property to use for coloring",
    update=update_selected_property
)

class UPDATE_OT_property_values(bpy.types.Operator):
    bl_idname = "update.property_values"
    bl_label = "Update Property Values"
    
    def execute(self, context):
        scene = context.scene
        
        # Clear existing values
        scene.property_values.clear()
        
        # Get all values for selected property
        values = set()
        if scene.show_all_graphs:
            for graph_id in get_all_graph_ids():
                graph = get_graph(graph_id)
                if graph:
                    mapping = create_property_value_mapping(graph, scene.selected_property)
                    values.update(mapping.values())
        else:
            graph = get_graph()
            if graph:
                mapping = create_property_value_mapping(graph, scene.selected_property)
                values.update(mapping.values())
        
        # Add values to property_values collection
        for value in sorted(values):
            item = scene.property_values.add()
            item.value = str(value)
            item.color = (0.5, 0.5, 0.5, 1.0)  # Default gray
        
        return {'FINISHED'}

def get_available_properties(graph):
    """Get list of available property names from the graph."""
    properties = set()
    
    print(f"\nCercando proprietà nel grafo...")
    print(f"Numero totale di nodi: {len(graph.nodes)}")
    
    for node in graph.nodes:
        print(f"Node type: {node.node_type}, name: {node.name}")
        if node.node_type == "property":
            print(f"Found property node: {node.name}")
            properties.add(node.name)
    
    result = list(properties)
    print(f"Proprietà trovate: {result}")
    return result

class PropertyValueItem(bpy.types.PropertyGroup):
    value: bpy.props.StringProperty(name="Value") # type: ignore
    color: bpy.props.FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 0.5, 1.0)
    ) # type: ignore

class PROPERTY_UL_values(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "value", text="")
        row.prop(item, "color", text="")

class SaveColorScheme(bpy.types.Operator, ExportHelper):
    bl_idname = "color_scheme.save"
    bl_label = "Save Color Scheme"
    filename_ext = ".emc"
    
    def execute(self, context):
        scene = context.scene
        color_mapping = {item.value: item.color[:] for item in scene.property_values}
        save_color_scheme(self.filepath, scene.selected_property, color_mapping)
        return {'FINISHED'}

class LoadColorScheme(bpy.types.Operator, ImportHelper):
    bl_idname = "color_scheme.load"
    bl_label = "Load Color Scheme"
    filename_ext = ".emc"
    
    def execute(self, context):
        scene = context.scene
        property_name, color_mapping = load_color_scheme(self.filepath)
        
        # Update property values list
        scene.property_values.clear()
        for value, color in color_mapping.items():
            item = scene.property_values.add()
            item.value = value
            item.color = color if len(color) == 4 else (*color, 1.0)
        
        return {'FINISHED'}


class EM_set_property_materials(bpy.types.Operator):
    bl_idname = "emset.propertymaterial"
    bl_label = "Change proxy properties"
    bl_description = "Change proxy materials using property values"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.proxy_display_mode = "Properties"
        print_graph_info()  # Add debug info
        return {'FINISHED'}


class Display_mode_menu(bpy.types.Menu):
    bl_label = "Custom Menu"
    bl_idname = "OBJECT_MT_Display_mode_menu"

    def draw(self, context):
        layout = self.layout

        layout.operator("emset.emmaterial", text="EM")
        layout.operator("emset.epochmaterial", text="Periods")
        layout.operator("emset.propertymaterial", text="Properties")

def print_graph_info():
    """Debug function to print graph information"""
    from .s3Dgraphy import get_graph, get_all_graph_ids
    
    print("\n=== Graph Debug Info ===")
    graph_ids = get_all_graph_ids()
    print(f"Available graph IDs: {graph_ids}")
    
    for graph_id in graph_ids:
        graph = get_graph(graph_id)
        if graph:
            print(f"\nGraph {graph_id}:")
            print(f"Number of nodes: {len(graph.nodes)}")
            print("Node types:")
            type_count = {}
            for node in graph.nodes:
                node_type = getattr(node, 'node_type', 'unknown')
                type_count[node_type] = type_count.get(node_type, 0) + 1
            for node_type, count in type_count.items():
                print(f"  {node_type}: {count}")

class VISUALToolsPanel:
    bl_label = "Visual manager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}


    def draw(self, context):
        layout = self.layout
        scene = context.scene
        current_proxy_display_mode = context.scene.proxy_display_mode
        layout.alignment = 'LEFT'

        row = layout.row(align=True)
        split = row.split()
        col = split.column()
        col.label(text="Display mode")
        col = split.column(align=True)
        
        col.menu(Display_mode_menu.bl_idname, text=current_proxy_display_mode, icon='COLOR')
    
        row = layout.row()

        # Add property-specific UI when in Properties mode
        if current_proxy_display_mode == "Properties":
            box = layout.box()
            row = box.row()
            row.prop(scene, "show_all_graphs", text="Show All Graphs")
            
            # Property selector
            row = box.row()
            props = []
            
            print("\nRecuperando il grafo...")
            if scene.show_all_graphs:
                graph_ids = get_all_graph_ids()
                print(f"Graph IDs trovati: {graph_ids}")
                for graph_id in graph_ids:
                    graph = get_graph(graph_id)
                    if graph:
                        print(f"Processando grafo {graph_id}")
                        props.extend(get_available_properties(graph))
            else:
                # Get the active file's graph_id
                em_tools = scene.em_tools
                if em_tools.active_file_index >= 0:
                    graphml = em_tools.graphml_files[em_tools.active_file_index]
                    graph = get_graph(graphml.name)
                    if graph:
                        print(f"Processando grafo {graphml.name}")
                        props = get_available_properties(graph)
                else:
                    print("Nessun file GraphML attivo")
            
            props = sorted(set(props))  # Remove duplicates and sort
            
            if props:
                print(f"Proprietà disponibili: {props}")
                enum_items = [(p, p, "") for p in props]
                row.prop_menu_enum(scene, "selected_property", text="Select Property")
                
                if scene.selected_property:
                    # Values list with colors
                    row = box.row()
                    row.template_list("PROPERTY_UL_values", "", 
                                    scene, "property_values",
                                    scene, "active_value_index")
                    
                    # Color scheme management
                    row = box.row(align=True)
                    row.operator("color_scheme.save", text="Save Schema", icon='FILE_TICK')
                    row.operator("color_scheme.load", text="Load Schema", icon='FILE_FOLDER')
            else:
                row.label(text="No properties found in graph")

       
            
            if scene.selected_property:
                # Values list with colors
                row = box.row()
                row.template_list("PROPERTY_UL_values", "", 
                                scene, "property_values",
                                scene, "active_value_index")
                
                # Color scheme management
                row = box.row(align=True)
                row.operator("color_scheme.save", text="Save Schema", icon='FILE_TICK')
                row.operator("color_scheme.load", text="Load Schema", icon='FILE_FOLDER')

        row = layout.row()
        row.prop(scene, "proxy_display_alpha")

        op = row.operator(
            "epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_BBOX')
        op.sg_objects_changer = 'BOUND_SHADE'

        op = row.operator(
            "epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_WIRE')
        op.sg_objects_changer = 'WIRE_SHADE'

        op = row.operator(
            "epoch_manager.change_selected_objects", text="", emboss=False, icon='SHADING_SOLID')
        op.sg_objects_changer = 'MATERIAL_SHADE'

        op = row.operator(
            "epoch_manager.change_selected_objects", text="", emboss=False, icon='SPHERE')
        op.sg_objects_changer = 'SHOW_WIRE'


        row = layout.row()

        row.operator("notinthematrix.material", icon="MOD_MASK", text='')

        row.label(text="Labels:")

        op = row.operator("create.collection", text="", emboss=False, icon='OUTLINER_COLLECTION')

        op = row.operator("label.creation", text="",
                          emboss=False, icon='SYNTAX_OFF')
        #op.onoff = False

        op = row.operator("center.mass", text="", emboss=False, icon='CURSOR')
        op.center_to = "cursor"

        op = row.operator("center.mass", text="", emboss=False, icon='SNAP_FACE_CENTER')
        op.center_to = "mass"
        
        """ op = row.operator("center.mass", text="", emboss=False, icon='SNAP_FACE_CENTER')
        op.center_to = "mass" """

class VIEW3D_PT_VisualPanel(Panel, VISUALToolsPanel):
    bl_category = "EM"
    bl_idname = "VIEW3D_PT_VisualPanel"
    #bl_context = "objectmode"


classes = [
    VIEW3D_PT_VisualPanel,
    Display_mode_menu,
    EM_set_property_materials,
    SaveColorScheme,
    LoadColorScheme,
    PROPERTY_UL_values,
    PropertyValueItem,
    UPDATE_OT_property_values    
    ]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.property_values = bpy.props.CollectionProperty(type=PropertyValueItem)
    bpy.types.Scene.active_value_index = bpy.props.IntProperty()
    bpy.types.Scene.selected_property = bpy.props.StringProperty(
        name="Selected Property",
        description="Property to use for coloring"
    )
    bpy.types.Scene.show_all_graphs = bpy.props.BoolProperty(
        name="Show All Graphs",
        description="Show properties from all loaded graphs",
        default=False
    )
    bpy.types.Scene.available_properties = bpy.props.CollectionProperty(
        type=bpy.types.PropertyGroup
    )


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.property_values
    del bpy.types.Scene.active_value_index
    del bpy.types.Scene.selected_property
    del bpy.types.Scene.show_all_graphs
    del bpy.types.Scene.available_properties