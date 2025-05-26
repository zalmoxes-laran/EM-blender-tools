"""
Operators for the Visual Manager
This module contains all operators for property-based visualization,
color schemes, and material management.
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

from ..s3Dgraphy.nodes.stratigraphic_node import StratigraphicNode
from ..s3Dgraphy import get_graph, get_all_graph_ids
from ..s3Dgraphy.multigraph.multigraph import multi_graph_manager

from .utils import (
    create_property_value_mapping, 
    save_color_scheme, 
    load_color_scheme,
    get_available_properties,
    test_optimization_performance
)
from .color_ramps import COLOR_RAMPS


# Variabili globali per controllo delle chiamate duplicate
_last_selected_property = None
_last_update_time = 0

def update_property_enum(self, context):
    global _last_selected_property, _last_update_time
    import time
    
    # Se la proprietà non è cambiata o è passato troppo poco tempo, ignora
    current_time = time.time()
    if (self.property_enum == _last_selected_property and 
            current_time - _last_update_time < 0.5):
        print(f"Ignoro aggiornamento ripetuto per: {self.property_enum}")
        return
    
    print(f"\nProperty enum aggiornato a: {self.property_enum}")
    context.scene.selected_property = self.property_enum
    _last_selected_property = self.property_enum
    _last_update_time = current_time
    
    # Ora aggiorna i valori
    bpy.ops.visual.update_property_values()

def update_selected_property(self, context):
    bpy.ops.visual.update_property_values()

def get_enum_items(self, context):
    """Funzione getter per gli items dell'enum property"""
    props = get_available_properties(context)
    return [(p, p, f"Select {p} property") for p in props]


class VISUAL_OT_update_property_values(Operator):
    """Update property values for the selected property"""
    bl_idname = "visual.update_property_values"
    bl_label = "Update Property Values"

    # Variabile di classe per prevenire ricorsione
    _is_updating = False

    def execute(self, context):
        # Evita ricorsione
        if VISUAL_OT_update_property_values._is_updating:
            print("Evitata chiamata ricorsiva a visual.update_property_values")
            return {'FINISHED'}
        
        VISUAL_OT_update_property_values._is_updating = True
        scene = context.scene
        em_tools = scene.em_tools

        try:
            print("\n=== Starting Property Values Update ===")
            
            # Clear existing values
            scene.property_values.clear()
        
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
                        mapping = create_property_value_mapping(graph, scene.selected_property)
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
            VISUAL_OT_update_property_values._is_updating = False
            print("\n=== Property Values Update Completed ===")


class VISUAL_OT_apply_colors(Operator):
    """Apply the selected colors to proxies based on their property values"""
    bl_idname = "visual.apply_colors"
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


class VISUAL_OT_select_proxies(Operator):
    """Select all proxies with a specific property value"""
    bl_idname = "visual.select_proxies"
    bl_label = "Select Proxies"
    bl_description = "Select all proxies with this property value"

    value: StringProperty()

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


class VISUAL_OT_apply_color_ramp(Operator):
    """Apply the selected color ramp to property values"""
    bl_idname = "visual.apply_color_ramp"
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


class VISUAL_OT_save_color_scheme(Operator, ExportHelper):
    """Save color scheme to file"""
    bl_idname = "visual.save_color_scheme"
    bl_label = "Save Color Scheme"
    filename_ext = ".emc"
    
    def execute(self, context):
        scene = context.scene
        color_mapping = {item.value: item.color[:] for item in scene.property_values}
        save_color_scheme(self.filepath, scene.selected_property, color_mapping)
        self.report({'INFO'}, f"Color scheme saved to {self.filepath}")
        return {'FINISHED'}


class VISUAL_OT_load_color_scheme(Operator, ImportHelper):
    """Load color scheme from file"""
    bl_idname = "visual.load_color_scheme"
    bl_label = "Load Color Scheme"
    filename_ext = ".emc"
    
    def execute(self, context):
        scene = context.scene
        try:
            property_name, color_mapping = load_color_scheme(self.filepath)
            
            # Update property values list
            scene.property_values.clear()
            for value, color in color_mapping.items():
                item = scene.property_values.add()
                item.value = value
                item.color = color if len(color) == 4 else (*color, 1.0)
            
            # Update selected property
            scene.selected_property = property_name
            
            self.report({'INFO'}, f"Color scheme loaded from {self.filepath}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error loading color scheme: {str(e)}")
            return {'CANCELLED'}


class VISUAL_OT_set_property_materials(Operator):
    """Change proxy properties display mode"""
    bl_idname = "visual.set_property_materials"
    bl_label = "Change proxy properties"
    bl_description = "Change proxy materials using property values"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        context.scene.proxy_display_mode = "Properties"
        return {'FINISHED'}


class VISUAL_OT_benchmark_property_functions(Operator):
    """Benchmark property mapping functions"""
    bl_idname = "visual.benchmark_property_functions"
    bl_label = "Benchmark Property Functions"
    bl_description = "Compare performance between legacy and optimized property mapping functions"
    
    def execute(self, context):
        test_optimization_performance(context)
        self.report({'INFO'}, "Benchmark completed. Check console for results.")
        return {'FINISHED'}


def register_operators():
    """Register operator classes."""
    classes = [
        VISUAL_OT_update_property_values,
        VISUAL_OT_apply_colors,
        VISUAL_OT_select_proxies,
        VISUAL_OT_apply_color_ramp,
        VISUAL_OT_save_color_scheme,
        VISUAL_OT_load_color_scheme,
        VISUAL_OT_set_property_materials,
        VISUAL_OT_benchmark_property_functions,
    ]
    
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # Class might already be registered
            pass
    
    # Register scene properties for property enum
    if not hasattr(bpy.types.Scene, "property_enum"):
        bpy.types.Scene.property_enum = bpy.props.EnumProperty(
            items=get_enum_items,
            name="Properties",
            description="Available properties",
            update=update_property_enum
        )

    if not hasattr(bpy.types.Scene, "selected_property"):
        bpy.types.Scene.selected_property = bpy.props.StringProperty(
            name="Selected Property",
            description="Property to use for coloring",
            update=update_selected_property
        )


def unregister_operators():
    """Unregister operator classes."""
    # Remove scene properties
    if hasattr(bpy.types.Scene, "property_enum"):
        del bpy.types.Scene.property_enum
    
    if hasattr(bpy.types.Scene, "selected_property"):
        del bpy.types.Scene.selected_property
    
    classes = [
        VISUAL_OT_benchmark_property_functions,
        VISUAL_OT_set_property_materials,
        VISUAL_OT_load_color_scheme,
        VISUAL_OT_save_color_scheme,
        VISUAL_OT_apply_color_ramp,
        VISUAL_OT_select_proxies,
        VISUAL_OT_apply_colors,
        VISUAL_OT_update_property_values,
    ]
    
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except ValueError:
            # Class might already be unregistered
            pass