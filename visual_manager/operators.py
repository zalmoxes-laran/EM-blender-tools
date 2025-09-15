"""
Operators for the Visual Manager
This module contains all operators for property-based visualization,
color schemes, and material management.
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
from s3dgraphy import get_graph, get_all_graph_ids
from s3dgraphy.multigraph.multigraph import multi_graph_manager

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
            
            # LOGICA CORRETTA PER ENTRAMBE LE MODALITÀ
            if not em_tools.mode_switch:  # Modalità 3D GIS
                # Nome hardcodato per modalità 3D GIS
                graph_name = "3dgis_graph"
                print(f"EM-tools: 3D GIS mode - processing hardcoded graph '{graph_name}'")
                
                # *** VALIDAZIONE ESISTENZA GRAFO 3D GIS ***
                from s3dgraphy.multigraph.multigraph import multi_graph_manager
                if graph_name not in multi_graph_manager.graphs:
                    message = f"3D GIS graph '{graph_name}' not found. Please import data first."
                    self.report({'WARNING'}, message)
                    print(f"❌ {message}")
                    return {'FINISHED'}
                
                graph = get_graph(graph_name)
                if graph:
                    print(f"Processing graph '{graph_name}'")
                    mapping = self._create_complete_property_mapping(graph, scene.selected_property)
                    values.update(mapping.values())
                    processed_graphs = 1
                    print(f"Found {len(set(mapping.values()))} unique values")
                else:
                    message = f"3D GIS graph '{graph_name}' not accessible"
                    self.report({'ERROR'}, message)
                    print(f"❌ {message}")
                    return {'FINISHED'}
                    
            else:  # Modalità Advanced EM
                if scene.show_all_graphs:  # Modalità multigrafo
                    graph_ids = get_all_graph_ids()
                    print(f"Advanced EM multigrafo mode: processing {len(graph_ids)} graphs")
                    for graph_id in graph_ids:
                        graph = get_graph(graph_id)
                        if graph:
                            print(f"Processing graph '{graph_id}'")
                            mapping = self._create_complete_property_mapping(graph, scene.selected_property)
                            values.update(mapping.values())
                            processed_graphs += 1
                else:  # Solo grafo attivo
                    if em_tools.active_file_index >= 0:
                        active_file = em_tools.graphml_files[em_tools.active_file_index]
                        graph = get_graph(active_file.name)
                        if graph:
                            print(f"Processing active graph '{active_file.name}'")
                            mapping = self._create_complete_property_mapping(graph, scene.selected_property)
                            values.update(mapping.values())
                            processed_graphs = 1
                        else:
                            print(f"Graph '{active_file.name}' not found")
                    else:
                        print("No active GraphML file selected in Advanced EM mode")

            # Update property values
            sorted_values = sorted(values)
            for value in sorted_values:
                item = scene.property_values.add()
                item.value = str(value)  # Usa 'value' come nell'originale

            print(f"Updated property values: {len(sorted_values)} unique values from {processed_graphs} graphs")
            
        except Exception as e:
            print(f"Error in update_property_values: {e}")
            self.report({'ERROR'}, f"Error updating property values: {str(e)}")
        finally:
            VISUAL_OT_update_property_values._is_updating = False
        
        return {'FINISHED'}

    def _create_complete_property_mapping(self, graph, property_name):
        """
        Approccio ibrido: prima trova i nodi property, poi le connessioni
        Più efficiente e segue la logica originale
        """
        mapping = {}
        
        # 1. Trova TUTTI i nodi property con questo nome
        property_nodes = [node for node in graph.nodes 
                        if hasattr(node, 'node_type') and node.node_type == "property" 
                        and node.name == property_name]
        
        print(f"Found {len(property_nodes)} property nodes for '{property_name}'")
        
        # 2. Tieni traccia delle US già elaborate
        connected_strat_nodes = set()
        
        # 3. Per ogni nodo property, trova le US collegate
        for prop_node in property_nodes:
            value = getattr(prop_node, 'description', '')
            is_empty = not (value and value.strip())
            
            print(f"Processing property node {prop_node.node_id}: empty={is_empty}, value='{value}'")
            
            # Trova tutte le US collegate a questo nodo property
            connected_us = []
            for edge in graph.edges:
                if edge.edge_type == "has_property" and edge.edge_target == prop_node.node_id:
                    strat_node = graph.find_node_by_id(edge.edge_source)
                    if strat_node:
                        connected_us.append(strat_node)
                        connected_strat_nodes.add(strat_node.node_id)
            
            print(f"  Connected to {len(connected_us)} US: {[us.name for us in connected_us]}")
            
            # Assegna il valore appropriato
            for us_node in connected_us:
                if is_empty:
                    mapping[us_node.name] = f"empty property {property_name} node"
                    print(f"  -> {us_node.name}: EMPTY PROPERTY")
                else:
                    mapping[us_node.name] = value
                    print(f"  -> {us_node.name}: '{value}'")
        
        # 4. Trova tutte le US che NON hanno questa proprietà
        from s3dgraphy.nodes.stratigraphic_node import StratigraphicNode
        all_strat_nodes = [node for node in graph.nodes 
                        if hasattr(node, 'node_type') and isinstance(node, StratigraphicNode)]
        
        no_property_count = 0
        for strat_node in all_strat_nodes:
            if strat_node.node_id not in connected_strat_nodes:
                mapping[strat_node.name] = f"no property {property_name} node"
                no_property_count += 1
        
        print(f"Final mapping: {len(mapping)} total US")
        print(f"  - With property: {len(connected_strat_nodes)}")  
        print(f"  - Without property: {no_property_count}")
        
        return mapping


class VISUAL_OT_apply_colors(Operator):
    """Apply the selected colors to proxies based on their property values"""
    bl_idname = "visual.apply_colors"
    bl_label = "Apply Color Scheme"
    bl_description = "Apply the selected colors to proxies based on their property values"
    bl_options = {'REGISTER', 'UNDO'}
    
    def get_active_graph_for_mode(self, context):
        """Determina il grafo attivo in base alla modalità"""
        scene = context.scene
        em_tools = scene.em_tools
        
        if not em_tools.mode_switch:  # Modalità 3D GIS
            # Nome hardcodato per modalità 3D GIS
            graph_name = "3dgis_graph"
            graph = get_graph(graph_name)
            if graph:
                print(f"3D GIS mode: using hardcoded graph '{graph_name}'")
                return graph
            else:
                print(f"3D GIS mode: hardcoded graph '{graph_name}' not found")
                return None
        else:  # Modalità Advanced EM
            # Usa il grafo attivo selezionato
            if em_tools.active_file_index >= 0:
                graphml = em_tools.graphml_files[em_tools.active_file_index]
                graph = get_graph(graphml.name)
                print(f"Advanced EM mode: using active graph '{graphml.name}'")
                return graph
            else:
                print("Advanced EM mode: no active GraphML file selected")
                return None
    
    def execute(self, context):
        scene = context.scene
        em_tools = scene.em_tools
        
        if not scene.selected_property:
            self.report({'ERROR'}, "No property selected")
            return {'CANCELLED'}
        
        # USA LA NUOVA LOGICA PER DETERMINARE IL GRAFO ATTIVO
        graph = self.get_active_graph_for_mode(context)
        
        if not graph:
            self.report({'ERROR'}, "No active graph found")
            return {'CANCELLED'}
        
        alpha_value = scene.proxy_display_alpha
        
        print(f"\nApplying colors using graph with {len(graph.nodes)} nodes")
        print(f"Selected property: {scene.selected_property}")
        print(f"Available property values: {len(scene.property_values)}")
        
        try:
            # Create mapping from property values to colors
            color_mapping = {}
            for item in scene.property_values:
                color_mapping[item.value] = item.color
            
            # Create property-to-node mapping
            property_mapping = create_property_value_mapping(graph, scene.selected_property)
            
            # Apply colors to mesh objects
            colored_count = 0
            total_objects = 0
            
            for obj in scene.objects:
                if obj.type == 'MESH':
                    total_objects += 1
                    obj_name = obj.name
                    
                    if obj_name in property_mapping:
                        property_value = str(property_mapping[obj_name])
                        
                        if property_value in color_mapping:
                            color = color_mapping[property_value]
                            
                            # Create or get material
                            mat_name = f"prop_{scene.selected_property}_{property_value}"
                            if mat_name not in bpy.data.materials:
                                mat = bpy.data.materials.new(name=mat_name)
                                mat.use_nodes = True
                                
                                # Set base color
                                if mat.node_tree and mat.node_tree.nodes:
                                    principled = mat.node_tree.nodes.get("Principled BSDF")
                                    if principled:
                                        principled.inputs[0].default_value = (*color[:3], alpha_value)
                            else:
                                mat = bpy.data.materials[mat_name]
                            
                            # Apply material to object
                            if obj.data.materials:
                                obj.data.materials[0] = mat
                            else:
                                obj.data.materials.append(mat)
                            
                            colored_count += 1
                        else:
                            print(f"Warning: No color defined for value '{property_value}' on object '{obj_name}'")
                    else:
                        print(f"Warning: No property value found for object '{obj_name}'")
            
            summary = f"Applied colors to {colored_count} of {total_objects} mesh objects"
            print(f"\n{summary}")
            self.report({'INFO'}, summary)
            
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            print("\nError during color application:")
            print(traceback.format_exc())
            self.report({'ERROR'}, f"Error applying colors: {str(e)}")
            return {'CANCELLED'}


class VISUAL_OT_select_proxies(Operator):
    """Select all proxies with a specific property value"""
    bl_idname = "visual.select_proxies"
    bl_label = "Select Proxies"
    bl_description = "Select all proxies with this property value"

    value: StringProperty() # type: ignore

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