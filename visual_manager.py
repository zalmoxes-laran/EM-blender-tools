import bpy # type: ignore

from bpy.types import Panel # type: ignore
from bpy.types import Operator # type: ignore
from bpy.types import PropertyGroup # type: ignore
from bpy.types import UIList # type: ignore

from .color_ramps import COLOR_RAMPS

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
from .s3Dgraphy.multigraph.multigraph import multi_graph_manager

import json
import os
import shutil

import logging
log = logging.getLogger(__name__)


class PROPERTY_OT_apply_colors(bpy.types.Operator):
    bl_idname = "property.apply_colors"
    bl_label = "Apply Color Scheme"
    bl_description = "Apply the selected colors to proxies based on their property values"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        
        if not scene.selected_property:
            self.report({'ERROR'}, "No property selected")
            return {'CANCELLED'}
        
        if not em_tools.mode_switch:

            mgr = multi_graph_manager
            print("\nDebug - Graph Manager Status:")
            print(f"Available graphs: {list(mgr.graphs.keys())}")
            
            graph = mgr.graphs.get("3dgis_graph")
        else:
            if em_tools.active_file_index >= 0:
                try:
                    graphml = em_tools.graphml_files[em_tools.active_file_index]
                    graph = get_graph(graphml.name)
                except Exception as e:
                    self.report({'ERROR'}, f"Error loading graph: {str(e)}")
                    return {'CANCELLED'}


        if graph:
            # Create a mapping of property values to colors
            color_mapping = {item.value: item.color for item in scene.property_values}
            
            # Create materials
            materials = {}
            for value, color in color_mapping.items():
                mat_name = f"prop_{scene.selected_property}_{value}"
                mat = bpy.data.materials.get(mat_name)
                if not mat:
                    mat = bpy.data.materials.new(name=mat_name)
                    mat.use_nodes = True
                principled = mat.node_tree.nodes["Principled BSDF"]
                principled.inputs[0].default_value = (*color[:3], 1.0)
                materials[value] = mat

            # Find all property nodes of the selected type
            property_nodes = [node for node in graph.nodes 
                            if node.node_type == "property" 
                            and node.name == scene.selected_property]

            # Set per tracciare i nodi stratigrafici che hanno la proprietà
            connected_strat_nodes = set()
            colored_objects = 0

            # Prima gestisci i nodi con valori e quelli vuoti
            for prop_node in property_nodes:
                # Traccia tutti i nodi stratigrafici connessi a questa proprietà
                for edge in graph.edges:
                    if edge.edge_type == "has_property" and edge.edge_target == prop_node.node_id:
                        connected_strat_nodes.add(edge.edge_source)
                        strat_node = graph.find_node_by_id(edge.edge_source)
                        if strat_node:
                            # Determina il valore appropriato
                            if prop_node.description:
                                value = prop_node.description
                            else:
                                value = f"empty property {scene.selected_property} node"

                            # Se abbiamo un materiale per questo valore, applicalo
                            if value in materials:
                                proxy = bpy.data.objects.get(strat_node.name)
                                if proxy and proxy.type == 'MESH':
                                    if proxy.data.materials:
                                        proxy.data.materials[0] = materials[value]
                                    else:
                                        proxy.data.materials.append(materials[value])
                                    colored_objects += 1

            # Ora gestisci i nodi stratigrafici senza questa proprietà
            no_prop_value = f"no property {scene.selected_property} node"
            if no_prop_value in materials:
                for node in graph.nodes:
                    if isinstance(node, StratigraphicNode) and node.node_id not in connected_strat_nodes:
                        proxy = bpy.data.objects.get(node.name)
                        if proxy and proxy.type == 'MESH':
                            if proxy.data.materials:
                                proxy.data.materials[0] = materials[no_prop_value]
                            else:
                                proxy.data.materials.append(materials[no_prop_value])
                            colored_objects += 1

            self.report({'INFO'}, f"Applied colors to {colored_objects} objects")
            return {'FINISHED'}
            
        self.report({'ERROR'}, "No active graph")
        return {'CANCELLED'}


def update_property_enum(self, context):
    print("\nProperty enum updated!")  # Debug
    context.scene.selected_property = self.property_enum
    print(f"Selected property: {context.scene.selected_property}")  # Debug
    bpy.ops.update.property_values()

def get_enum_items(self, context):
    """Funzione getter per gli items dell'enum property"""
    props = get_available_properties(context)
    return [(p, p, f"Select {p} property") for p in props]


def update_selected_property(self, context):
    bpy.ops.update.property_values()



class UPDATE_OT_property_values(bpy.types.Operator):
    bl_idname = "update.property_values"
    bl_label = "Update Property Values"
    
    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        
        print("\n=== Starting Property Values Update ===")
        
        # Clear existing values
        scene.property_values.clear()
        
        try:
            values = set()
            processed_graphs = 0
            
            if scene.show_all_graphs or not em_tools.mode_switch:
                print("Processing all loaded graphs...")
                graph_ids = get_all_graph_ids()
                print(f"Found {len(graph_ids)} graph(s): {graph_ids}")
                
                for graph_id in graph_ids:
                    graph = get_graph(graph_id)
                    if graph:
                        print(f"\nProcessing graph '{graph_id}'")
                        # Debug degli edges
                        print("\nDEBUG - Graph edges:")
                        for edge in graph.edges:
                            print(f"Edge: {edge.edge_id}")
                            print(f"  Type: {edge.edge_type}")
                            print(f"  Source: {edge.edge_source}")
                            print(f"  Target: {edge.edge_target}")
                        
                        mapping = create_property_value_mapping_optimized(graph, scene.selected_property)

                        values.update(mapping.values())
                        processed_graphs += 1
                    else:
                        print(f"Warning: Could not retrieve graph '{graph_id}'")
            else:
                # Process only the active GraphML file
                if em_tools.active_file_index >= 0:
                    graphml = em_tools.graphml_files[em_tools.active_file_index]
                    graph = get_graph(graphml.name)

                    
                    if graph:
                        print(f"\nProcessing active graph '{graphml.name}'")
                        # Debug degli edges
                        print("\nDEBUG - Graph edges:")
                        for edge in graph.edges:
                            print(f"Edge: {edge.edge_id}")
                            print(f"  Type: {edge.edge_type}")
                            print(f"  Source: {edge.edge_source}")
                            print(f"  Target: {edge.edge_target}")
                        
                        mapping = create_property_value_mapping(graph, scene.selected_property)
                        values.update(mapping.values())
                        processed_graphs = 1
                    else:
                        message = "No active graph found. Please load a GraphML file first."
                        self.report({'ERROR'}, message)
                        print(f"Error: {message}")
                        return {'CANCELLED'}
                else:
                    message = "No GraphML file selected"
                    self.report({'ERROR'}, message)
                    print(f"Error: {message}")
                    return {'CANCELLED'}
            
            # Sort and add values to property_values collection
            print("\nAdding property values:")
            for value in sorted(values):
                item = scene.property_values.add()
                item.value = str(value)
                item.color = (0.5, 0.5, 0.5, 1.0)  # Default gray
                print(f"Added value: {value}")
            
            summary = f"Successfully processed {processed_graphs} graph(s) and found {len(values)} unique values"
            print(f"\n{summary}")
            self.report({'INFO'}, summary)
            
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            print("\nError during property values update:")
            print(traceback.format_exc())
            self.report({'ERROR'}, f"Error updating property values: {str(e)}")
            return {'CANCELLED'}
        finally:
            print("\n=== Property Values Update Completed ===")

def get_available_properties(context):
    """
    Get list of available property names using optimized indices.
    """
    print(f"\n=== Getting Available Properties (OPTIMIZED) ===")
    scene = context.scene
    em_tools = scene.em_tools
    properties = set()

    if not em_tools.mode_switch:  # Modalità 3D GIS
        mgr = multi_graph_manager
        graph = mgr.graphs.get("3dgis_graph")
        if graph:
            # USA GLI INDICI OTTIMIZZATI! 🚀
            properties.update(graph.indices.get_property_names())
    else:  # Modalità EM Advanced
        if scene.show_all_graphs:
            graph_ids = get_all_graph_ids()
        else:
            if em_tools.active_file_index >= 0:
                active_file = em_tools.graphml_files[em_tools.active_file_index]
                graph_ids = [active_file.name]
            else:
                return []

        for graph_id in graph_ids:
            graph = get_graph(graph_id)
            if graph:
                # USA GLI INDICI OTTIMIZZATI! 🚀
                properties.update(graph.indices.get_property_names())

    result = sorted(list(properties))
    print(f"Found {len(result)} properties using optimized indices")
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
        print(f"Drawing item {index}: value={item.value}, color={item.color}")  # Debug
        row = layout.row(align=True)
        row.prop(item, "value", text="")
        row.prop(item, "color", text="")
        op = row.operator("property.select_proxies", text="", icon='RESTRICT_SELECT_OFF')
        op.value = item.value


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

        if context.scene.em_tools.mode_switch:
            layout.operator("emset.emmaterial", text="EM")
            layout.operator("emset.epochmaterial", text="Epochs")

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
            
            if scene.em_tools.mode_switch:
                row = box.row()
                row.prop(scene, "show_all_graphs", text="Show All Graphs")
            
            row = box.row()
            row.prop(scene, "property_enum", text="Select Property")

            if scene.selected_property:
                
                row = box.row()
                row.template_list("PROPERTY_UL_values", "", 
                                scene, "property_values",
                                scene, "active_value_index")

                # Color scheme management
                row = box.row(align=True)
                row.operator("color_scheme.save", text="Save Schema", icon='FILE_TICK')
                row.operator("color_scheme.load", text="Load Schema", icon='FILE_FOLDER')

                row = box.row()
                row.prop(scene.color_ramp_props, "advanced_options", 
                        text="Color Ramp", 
                        icon='TRIA_DOWN' if scene.color_ramp_props.advanced_options else 'TRIA_RIGHT',
                        emboss=False)

                if scene.color_ramp_props.advanced_options:
                    preview = box.box()
                    preview.prop(scene.color_ramp_props, "ramp_type")
                    preview.prop(scene.color_ramp_props, "ramp_name")
                    
                    # Preview della color ramp
                    if (scene.color_ramp_props.ramp_type in COLOR_RAMPS and 
                        scene.color_ramp_props.ramp_name in COLOR_RAMPS[scene.color_ramp_props.ramp_type]):
                        
                        ramp_info = COLOR_RAMPS[scene.color_ramp_props.ramp_type][scene.color_ramp_props.ramp_name]
                        preview.label(text=f"Selected: {ramp_info['name']}")
                        preview.label(text=ramp_info['description'])
                    
                        preview.operator("property.apply_color_ramp", text="Apply Color Ramp")

                if scene.selected_property and len(scene.property_values) > 0:
                    row = box.row()
                    row.operator("property.apply_colors", text="Apply Colors to Proxies", icon='COLOR')


        
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

class PROPERTY_OT_select_proxies(bpy.types.Operator):
    bl_idname = "property.select_proxies"
    bl_label = "Select Proxies"
    bl_description = "Select all proxies with this property value"

    value: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        
        if not scene.selected_property:
            self.report({'ERROR'}, "No property selected")
            return {'CANCELLED'}
            
        # Deselect all objects first
        bpy.ops.object.select_all(action='DESELECT')


        if not scene.em_tools.mode_switch:

            mgr = multi_graph_manager
            print("\nDebug - Graph Manager Status:")
            print(f"Available graphs: {list(mgr.graphs.keys())}")
            
            graph = mgr.graphs.get("3dgis_graph")

        else:
            if em_tools.active_file_index >= 0:
                try:
                    graphml = em_tools.graphml_files[em_tools.active_file_index]
                    graph = get_graph(graphml.name)
                except Exception as e:
                    self.report({'ERROR'}, f"Error loading graph: {str(e)}")
                    return {'CANCELLED'}
        
        if graph:
            selected_count = 0
            connected_strat_nodes = set()

            # Trova tutti i nodi property del tipo selezionato
            property_nodes = [node for node in graph.nodes 
                            if node.node_type == "property" 
                            and node.name == scene.selected_property]

            # Prima raccogli tutti i nodi stratigrafici connessi
            for prop_node in property_nodes:
                for edge in graph.edges:
                    if edge.edge_type == "has_property" and edge.edge_target == prop_node.node_id:
                        connected_strat_nodes.add(edge.edge_source)

            if self.value == f"no property {scene.selected_property} node":
                # Seleziona i proxy che non hanno questa proprietà
                for node in graph.nodes:
                    if isinstance(node, StratigraphicNode) and node.node_id not in connected_strat_nodes:
                        proxy = bpy.data.objects.get(node.name)
                        if proxy and proxy.type == 'MESH':
                            proxy.select_set(True)
                            selected_count += 1

            elif self.value == f"empty property {scene.selected_property} node":
                # Seleziona i proxy con proprietà ma senza valore
                for prop_node in property_nodes:
                    if not prop_node.description:
                        for edge in graph.edges:
                            if edge.edge_type == "has_property" and edge.edge_target == prop_node.node_id:
                                strat_node = graph.find_node_by_id(edge.edge_source)
                                if strat_node:
                                    proxy = bpy.data.objects.get(strat_node.name)
                                    if proxy and proxy.type == 'MESH':
                                        proxy.select_set(True)
                                        selected_count += 1

            else:
                # Seleziona i proxy con il valore specifico
                for prop_node in property_nodes:
                    if prop_node.description == self.value:
                        for edge in graph.edges:
                            if edge.edge_type == "has_property" and edge.edge_target == prop_node.node_id:
                                strat_node = graph.find_node_by_id(edge.edge_source)
                                if strat_node:
                                    proxy = bpy.data.objects.get(strat_node.name)
                                    if proxy and proxy.type == 'MESH':
                                        proxy.select_set(True)
                                        selected_count += 1
            
            self.report({'INFO'}, f"Selected {selected_count} objects")
            return {'FINISHED'}
            
        self.report({'ERROR'}, "No active graph")
        return {'CANCELLED'}


def get_ramp_types(self, context):
    """Return color ramp types for the enum property"""
    return [(k, k.title(), k.title()) for k in COLOR_RAMPS.keys()]

def get_ramp_names(self, context):
    """Return color ramp names for the selected type"""
    ramp_type = context.scene.color_ramp_props.ramp_type
    if ramp_type in COLOR_RAMPS:
        return [(k, v["name"], v["description"]) 
                for k, v in COLOR_RAMPS[ramp_type].items()]
    return []

class ColorRampProperties(bpy.types.PropertyGroup):
    """Properties for color ramp selection"""
    ramp_type: bpy.props.EnumProperty(
        name="Scale Type",
        items=get_ramp_types,
        description="Type of color scale"
    ) # type: ignore
    
    ramp_name: bpy.props.EnumProperty(
        name="Color Ramp",
        items=get_ramp_names,
        description="Selected color ramp"
    ) # type: ignore

    advanced_options: bpy.props.BoolProperty(
        name="Show advanced options",
        description="Show advanced export options like compression settings",
        default=False
    ) # type: ignore


class PROPERTY_OT_apply_color_ramp(bpy.types.Operator):
    """Apply the selected color ramp to property values"""
    bl_idname = "property.apply_color_ramp"
    bl_label = "Apply Color Ramp"
    bl_description = "Apply selected color ramp to property values"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        props = scene.color_ramp_props
        
        if not scene.selected_property:
            self.report({'ERROR'}, "No property selected")
            return {'CANCELLED'}
            
        # Get the selected color ramp
        if props.ramp_type not in COLOR_RAMPS or props.ramp_name not in COLOR_RAMPS[props.ramp_type]:
            self.report({'ERROR'}, "Invalid color ramp selection")
            return {'CANCELLED'}
            
        colors = COLOR_RAMPS[props.ramp_type][props.ramp_name]["colors"]
        
        # Sort property values for sequential/diverging ramps
        values = list(scene.property_values)
        if props.ramp_type in ["sequential", "diverging"]:
            values.sort(key=lambda x: float(x.value) if x.value.replace(".", "").isdigit() else float("-inf"))
        
        # Assign colors to values
        num_colors = len(colors)
        num_values = len(values)
        
        for i, value in enumerate(values):
            # Calculate color index based on distribution type
            if props.ramp_type == "diverging":
                # Center the values around the middle color
                mid_point = (num_values - 1) / 2
                rel_pos = (i - mid_point) / mid_point if mid_point > 0 else 0
                color_idx = int((rel_pos + 1) * (num_colors - 1) / 2)
            else:
                # Distribute colors evenly
                color_idx = min(int(i * num_colors / num_values), num_colors - 1)
            
            value.color = (*colors[color_idx], 1.0)  # Add alpha channel
        
        self.report({'INFO'}, f"Applied {props.ramp_name} color ramp to {num_values} values")
        return {'FINISHED'}


classes = [
    VIEW3D_PT_VisualPanel,
    Display_mode_menu,
    EM_set_property_materials,
    SaveColorScheme,
    LoadColorScheme,
    PROPERTY_UL_values,
    PropertyValueItem,
    UPDATE_OT_property_values,
    PROPERTY_OT_apply_colors,
    PROPERTY_OT_select_proxies,
    ColorRampProperties,
    PROPERTY_OT_apply_color_ramp
    ]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.property_values = bpy.props.CollectionProperty(type=PropertyValueItem)
    bpy.types.Scene.active_value_index = bpy.props.IntProperty()
    
    bpy.types.Scene.show_all_graphs = bpy.props.BoolProperty(
        name="Show All Graphs",
        description="Show properties from all loaded graphs",
        default=False
    )
    bpy.types.Scene.available_properties = bpy.props.CollectionProperty(
        type=bpy.types.PropertyGroup
    )

    # Property enum
        
    # Property enum che ora usa la funzione update_property_enum
    bpy.types.Scene.property_enum = bpy.props.EnumProperty(
        items=get_enum_items,
        name="Properties",
        description="Available properties",
        update=update_property_enum  # Usa la funzione update definita sopra
    )

    bpy.types.Scene.color_ramp_props = bpy.props.PointerProperty(type=ColorRampProperties)

    bpy.types.Scene.selected_property = bpy.props.StringProperty(
        name="Selected Property",
        description="Property to use for coloring",
        update=update_selected_property
    )

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.property_values
    del bpy.types.Scene.active_value_index
    del bpy.types.Scene.show_all_graphs
    del bpy.types.Scene.available_properties
    del bpy.types.Scene.selected_property

    del bpy.types.Scene.property_enum
    del bpy.types.Scene.color_ramp_props
