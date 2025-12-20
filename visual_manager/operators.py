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
    create_property_materials_for_scene_values,
    apply_materials_to_objects,
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
    from .utils import get_enum_items
    return get_enum_items(self, context)


class VISUAL_OT_update_property_values(Operator):
    """Update property values for the selected property"""
    bl_idname = "visual.update_property_values"
    bl_label = "Update Property Values"

    # Variabile di classe per prevenire ricorsione
    _is_updating = False

    def execute(self, context):
        # Evita ricorsione
        if VISUAL_OT_update_property_values._is_updating:
            print("Evitata chiamata ricorsiva a update_property_values")
            return {'CANCELLED'}
        
        VISUAL_OT_update_property_values._is_updating = True
        
        try:
            scene = context.scene
            em_tools = scene.em_tools
            
            if not scene.selected_property:
                self.report({'WARNING'}, "No property selected")
                return {'CANCELLED'}
            
            print(f"\n{'='*50}")
            print(f"UPDATING PROPERTY VALUES FOR: {scene.selected_property}")
            print(f"{'='*50}")
            
            # Clear existing values
            scene.property_values.clear()
            
            values = set()
            processed_graphs = 0
            
            # LOGICA CORRETTA PER ENTRAMBE LE MODALITÀ
            if not em_tools.mode_em_advanced:  # Modalità 3D GIS
                # Nome hardcodato per modalità 3D GIS
                graph_name = "3dgis_graph"
                print(f"3D GIS mode: processing hardcoded graph '{graph_name}'")
                
                # Validazione esistenza grafo 3D GIS
                if graph_name not in multi_graph_manager.graphs:
                    message = f"3D GIS graph '{graph_name}' not found. Please import data first."
                    self.report({'WARNING'}, message)
                    print(f"❌ {message}")
                    return {'FINISHED'}
                
                graph = get_graph(graph_name)
                if graph:
                    print(f"Processing graph '{graph_name}'")
                    # USA LA STESSA FUNZIONE DI APPLY_COLORS PER COERENZA
                    mapping = create_property_value_mapping(graph, scene.selected_property)
                    values.update(mapping.values())
                    processed_graphs = 1
                    print(f"Found {len(set(mapping.values()))} unique values")
                else:
                    message = f"3D GIS graph '{graph_name}' not accessible"
                    self.report({'ERROR'}, message)
                    print(f"❌ {message}")
                    return {'FINISHED'}
                    
            else:  # Modalità Advanced EM
                if hasattr(scene, 'show_all_graphs') and scene.show_all_graphs:  # Modalità multigrafo
                    graph_ids = get_all_graph_ids()
                    print(f"Advanced EM multigrafo mode: processing {len(graph_ids)} graphs")
                    
                    for graph_id in graph_ids:
                        try:
                            graph = get_graph(graph_id)
                            if graph:
                                # USA LA STESSA FUNZIONE DI APPLY_COLORS PER COERENZA
                                mapping = create_property_value_mapping(graph, scene.selected_property)
                                values.update(mapping.values())
                                processed_graphs += 1
                                print(f"Processed graph '{graph_id}': {len(set(mapping.values()))} unique values")
                        except Exception as e:
                            print(f"Error processing graph '{graph_id}': {e}")
                            continue
                            
                else:  # Solo grafo attivo
                    if em_tools.active_file_index >= 0 and len(em_tools.graphml_files) > em_tools.active_file_index:
                        active_file = em_tools.graphml_files[em_tools.active_file_index]
                        graph = get_graph(active_file.name)
                        if graph:
                            print(f"Advanced EM single graph mode: processing '{active_file.name}'")
                            # USA LA STESSA FUNZIONE DI APPLY_COLORS PER COERENZA
                            mapping = create_property_value_mapping(graph, scene.selected_property)
                            values.update(mapping.values())
                            processed_graphs = 1
                            print(f"Found {len(set(mapping.values()))} unique values")
                        else:
                            message = f"Graph '{active_file.name}' not found"
                            self.report({'ERROR'}, message)
                            print(f"❌ {message}")
                            return {'FINISHED'}
                    else:
                        message = "No active GraphML file selected"
                        self.report({'WARNING'}, message)
                        print(f"❌ {message}")
                        return {'FINISHED'}
            
            # Converti i valori in lista ordinata
            unique_values = sorted(list(values))
            print(f"\n=== Property Values Summary ===")
            print(f"Property: {scene.selected_property}")
            print(f"Processed graphs: {processed_graphs}")
            print(f"Unique values found: {len(unique_values)}")
            
            # Controlla se abbiamo i valori speciali
            has_empty = any(v.startswith("empty property") for v in unique_values)
            has_no_property = any(v.startswith("no property") for v in unique_values)
            print(f"Special values - Empty: {has_empty}, No property: {has_no_property}")
            
            # Aggiungi i valori alla collezione scene con colori di default
            default_colors = [
                (1.0, 0.0, 0.0, 1.0),  # Rosso
                (0.0, 1.0, 0.0, 1.0),  # Verde
                (0.0, 0.0, 1.0, 1.0),  # Blu
                (1.0, 1.0, 0.0, 1.0),  # Giallo
                (1.0, 0.0, 1.0, 1.0),  # Magenta
                (0.0, 1.0, 1.0, 1.0),  # Ciano
                (1.0, 0.5, 0.0, 1.0),  # Arancione
                (0.5, 0.0, 1.0, 1.0),  # Viola
                (0.0, 0.5, 0.0, 1.0),  # Verde scuro
                (0.5, 0.5, 0.5, 1.0),  # Grigio
            ]
            
            for i, value in enumerate(unique_values):
                item = scene.property_values.add()
                item.value = value
                # Assegna colore ciclico
                color_idx = i % len(default_colors)
                item.color = default_colors[color_idx]
                print(f"  {i+1}. '{value}' -> {item.color}")
            
            message = f"Found {len(unique_values)} unique values for {scene.selected_property}"
            print(f"\n✅ {message}")
            print(f"{'='*50}")
            self.report({'INFO'}, message)
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            print(f"\nError in update_property_values:")
            print(traceback.format_exc())
            self.report({'ERROR'}, f"Error updating property values: {str(e)}")
            return {'CANCELLED'}
        finally:
            VISUAL_OT_update_property_values._is_updating = False


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
        
        if not em_tools.mode_em_advanced:  # Modalità 3D GIS
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
            if em_tools.active_file_index >= 0 and len(em_tools.graphml_files) > em_tools.active_file_index:
                graphml = em_tools.graphml_files[em_tools.active_file_index]
                graph = get_graph(graphml.name)
                print(f"Advanced EM mode: using active graph '{graphml.name}'")
                return graph
            else:
                print("Advanced EM mode: no active GraphML file selected")
                return None
    
    def execute(self, context):
        scene = context.scene
        
        # Verifica prerequisiti
        if not scene.selected_property:
            self.report({'ERROR'}, "No property selected")
            return {'CANCELLED'}
        
        if not hasattr(scene, 'property_values') or len(scene.property_values) == 0:
            self.report({'ERROR'}, "No property values available. Please update property values first.")
            return {'CANCELLED'}
        
        # Ottieni il grafo attivo
        graph = self.get_active_graph_for_mode(context)
        if not graph:
            self.report({'ERROR'}, "No active graph found")
            return {'CANCELLED'}
        
        print(f"\n{'='*50}")
        print(f"APPLYING COLORS FOR PROPERTY: {scene.selected_property}")
        print(f"{'='*50}")
        print(f"Using graph with {len(graph.nodes)} nodes")
        print(f"Available property values: {len(scene.property_values)}")
        
        # Debug: stampa i colori disponibili
        print(f"\nProperty values and colors:")
        for i, item in enumerate(scene.property_values):
            print(f"  {i+1}. '{item.value}' -> {item.color}")
        
        try:
            # STEP 1: Crea il mapping property value -> object names
            # ADESSO USA LA STESSA FUNZIONE DI UPDATE_PROPERTY_VALUES
            property_mapping = create_property_value_mapping(graph, scene.selected_property)
            print(f"\n✓ STEP 1: Created property mapping with {len(property_mapping)} entries")
            
            # STEP 2: Crea i materiali per tutti i valori presenti in scene.property_values
            materials_by_value = create_property_materials_for_scene_values(context)
            print(f"✓ STEP 2: Created {len(materials_by_value)} materials")

            # ✅ OPTIMIZATION: Invalidate material cache after creating new materials
            from ..material_cache import invalidate_material_cache
            invalidate_material_cache()

            # STEP 3: Applica i materiali agli oggetti
            colored_count = apply_materials_to_objects(context, property_mapping, materials_by_value)
            print(f"✓ STEP 3: Applied materials to objects")
            
            # Report risultato
            total_meshes = len([obj for obj in scene.objects if obj.type == 'MESH'])
            summary = f"Applied colors to {colored_count} of {total_meshes} mesh objects"
            print(f"\n{'='*50}")
            print(f"✅ SUCCESS: {summary}")
            print(f"{'='*50}")
            self.report({'INFO'}, summary)
            
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            error_msg = f"Error applying colors: {str(e)}"
            print(f"\n{'='*50}")
            print(f"❌ ERROR: {error_msg}")
            print("Full traceback:")
            print(traceback.format_exc())
            print(f"{'='*50}")
            self.report({'ERROR'}, error_msg)
            return {'CANCELLED'}


class VISUAL_OT_select_proxies(Operator):
    """Select all proxies with a specific property value"""
    bl_idname = "visual.select_proxies"
    bl_label = "Select Proxies"
    bl_description = "Select all proxies with this property value"
    value: StringProperty() # type: ignore
    
    def execute(self, context):
        # Import corretto dal modulo operators già importato nel package
        from ..operators.addon_prefix_helpers import node_name_to_proxy_name
        
        scene = context.scene
        em_tools = scene.em_tools
        
        if not scene.selected_property:
            self.report({'ERROR'}, "No property selected")
            return {'CANCELLED'}
        
        print(f"\nSelecting proxies with value: '{self.value}'")
        
        # Deselect all objects first
        bpy.ops.object.select_all(action='DESELECT')
        
        # Determina il grafo attivo basato sulla modalità
        graph = None
        use_prefix = True  # Flag per sapere se usare il prefisso
        
        if not scene.em_tools.mode_em_advanced: # Modalità 3D GIS
            graph = get_graph("3dgis_graph")
            use_prefix = False  # 3DGIS non usa prefissi!
            if graph:
                print(f"Using 3D GIS graph (no prefix)")
        else: # Modalità Advanced EM
            use_prefix = True  # Advanced EM usa i prefissi
            if em_tools.active_file_index >= 0 and len(em_tools.graphml_files) > em_tools.active_file_index:
                try:
                    graphml = em_tools.graphml_files[em_tools.active_file_index]
                    graph = get_graph(graphml.name)
                    print(f"Using Advanced EM graph: {graphml.name} (with prefix)")
                except Exception as e:
                    self.report({'ERROR'}, f"Error loading graph: {str(e)}")
                    return {'CANCELLED'}
        
        if not graph:
            self.report({'ERROR'}, "No active graph found")
            return {'CANCELLED'}
        
        try:
            # USA LA STESSA FUNZIONE PER COERENZA
            property_mapping = create_property_value_mapping(graph, scene.selected_property)
            print(f"Created property mapping with {len(property_mapping)} entries")
            
            # Seleziona gli oggetti che hanno questo valore
            selected_count = 0
            for node_name, prop_value in property_mapping.items():
                if str(prop_value) == self.value:
                    # Determina il nome del proxy in base alla modalità
                    if use_prefix:
                        # Advanced EM: usa il prefisso
                        proxy_name = node_name_to_proxy_name(node_name, context=context, graph=graph)
                    else:
                        # Basic 3DGIS: usa il nome diretto senza prefisso
                        proxy_name = node_name
                    
                    # Cerca l'oggetto con il nome appropriato
                    proxy = bpy.data.objects.get(proxy_name)
                    if proxy and proxy.type == 'MESH':
                        proxy.select_set(True)
                        selected_count += 1
                        print(f"  Selected: {proxy_name}")
                    else:
                        print(f"  Warning: Proxy not found or not mesh: {proxy_name}")
            
            message = f"Selected {selected_count} objects with value '{self.value}'"
            print(f"✅ {message}")
            self.report({'INFO'}, message)
            
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            error_msg = f"Error selecting proxies: {str(e)}"
            print(f"❌ {error_msg}")
            print(traceback.format_exc())
            self.report({'ERROR'}, error_msg)
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
            values.sort(key=lambda x: float(x.value) if x.value.replace(".", "").replace("-", "").isdigit() else float("-inf"))
        
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
        context.scene.em_tools.proxy_display_mode = "Properties"
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