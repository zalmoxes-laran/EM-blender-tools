"""
CronoFilter Direct Integration for JSONExporter
==============================================

This module directly patches the JSONExporter to include the context section
with custom chronological horizons in the exported JSON.

This approach is more reliable than monkey patching and ensures the context
is actually included in the final export.
"""

import bpy
from typing import Dict, Any, Optional, List

def get_cronofilter_horizons_as_dict() -> Dict[str, Any]:
    """
    Get custom chronological horizons from CronoFilter settings as a dictionary
    ready to be merged with the default absolute_time_Epochs.
    
    Returns:
        Dict containing custom horizons in the same format as default horizons
    """
    custom_horizons = {}
    
    try:
        # Check if CronoFilter is available and has data
        if hasattr(bpy.types.Scene, 'cf_settings'):
            scene = bpy.context.scene
            if hasattr(scene, 'cf_settings'):
                cf_settings = scene.cf_settings
                
                def color_to_hex(color_vector):
                    """Convert Blender color (float vector) to hex string"""
                    r, g, b = color_vector
                    return "#{:02x}{:02x}{:02x}".format(
                        int(r * 255), int(g * 255), int(b * 255)
                    )
                
                for i, horizon in enumerate(cf_settings.horizons):
                    if horizon.enabled:  # Only include enabled horizons
                        # Create safe ID from label
                        safe_label = horizon.label.lower().replace(' ', '_').replace('-', '_')
                        # Remove special characters
                        safe_label = ''.join(c for c in safe_label if c.isalnum() or c == '_')
                        horizon_id = f"custom_{safe_label}"
                        
                        # Ensure unique ID
                        counter = 1
                        original_id = horizon_id
                        while horizon_id in custom_horizons:
                            horizon_id = f"{original_id}_{counter}"
                            counter += 1
                        
                        custom_horizons[horizon_id] = {
                            "name": horizon.label,
                            "start": horizon.start_time,
                            "end": horizon.end_time,
                            "color": color_to_hex(horizon.color)
                        }
                        
                print(f"CronoFilter: Found {len(custom_horizons)} enabled custom horizons for export")
    
    except Exception as e:
        print(f"CronoFilter: Error getting custom horizons: {e}")
    
    return custom_horizons

def apply_json_exporter_patch():
    """
    Apply the patch to JSONExporter to include context in exports.
    This patches the export_graphs method to include the context section.
    """
    try:
        # Import the JSONExporter class
        from ..s3Dgraphy.exporter.json_exporter import JSONExporter
        from ..s3Dgraphy.multigraph.multigraph import get_all_graph_ids, get_graph
        import json
        
        # Store the original export_graphs method
        _original_export_graphs = JSONExporter.export_graphs
        
        def enhanced_export_graphs(self, graph_ids: Optional[List[str]] = None) -> None:
            """
            Enhanced export_graphs method that includes context section with ONLY CronoFilter horizons
            """
            if graph_ids is None:
                graph_ids = get_all_graph_ids()
            
            # Get custom horizons from CronoFilter
            custom_horizons = get_cronofilter_horizons_as_dict()
            
            # Build the context section with ONLY custom horizons
            context = {}
            
            # Include custom horizons ONLY (no default epochs)
            if custom_horizons:
                context["absolute_time_Epochs"] = custom_horizons  # Only custom horizons
                print(f"CronoFilter: Using ONLY {len(custom_horizons)} custom horizons in export context")
            else:
                # If no custom horizons, don't include absolute_time_Epochs at all
                print("CronoFilter: No custom horizons found - context will be empty")
            
            # Create export data with context included
            export_data = {
                "version": "1.5",
                "context": context,  # Include ONLY custom horizons context
                "graphs": {}
            }
                
            # Process each graph
            for graph_id in graph_ids:
                graph = get_graph(graph_id)
                if graph and hasattr(graph, 'graph_id'):
                    actual_id = graph.graph_id
                    print(f"Exporting graph with ID: {actual_id}")
                    export_data["graphs"][actual_id] = self._process_graph(graph)
                    
            # Write the enhanced export data
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4, ensure_ascii=False)
                
            print(f"CronoFilter: Export completed with context section included")
        
        # Replace the export_graphs method
        JSONExporter.export_graphs = enhanced_export_graphs
        
        print("CronoFilter: Successfully patched JSONExporter.export_graphs method")
        return True
        
    except ImportError:
        print("CronoFilter: Could not import JSONExporter - patch not applied")
        return False
    except Exception as e:
        print(f"CronoFilter: Error patching JSONExporter: {e}")
        return False

def validate_patch():
    """
    Validate that the patch was applied correctly by checking if the method was replaced.
    """
    try:
        from ..s3Dgraphy.exporter.json_exporter import JSONExporter
        
        # Check if the method exists and has our enhanced functionality
        method = getattr(JSONExporter, 'export_graphs', None)
        if method and hasattr(method, '__name__'):
            if 'enhanced_export_graphs' in str(method):
                print("CronoFilter: Patch validation successful")
                return True
        
        print("CronoFilter: Patch validation failed - method not properly replaced")
        return False
        
    except Exception as e:
        print(f"CronoFilter: Patch validation error: {e}")
        return False

def get_context_preview() -> Dict[str, Any]:
    """
    Get a preview of what the context section will look like in the export.
    Now shows ONLY custom horizons (no default epochs).
    """
    try:
        # Get custom horizons
        custom_horizons = get_cronofilter_horizons_as_dict()
        
        # Build context with ONLY custom horizons
        context = {}
        if custom_horizons:
            context["absolute_time_Epochs"] = custom_horizons
        
        return context
        
    except Exception as e:
        print(f"CronoFilter: Error getting context preview: {e}")
        return {}

def print_context_summary():
    """
    Print a summary of the current context that will be exported.
    Now shows ONLY custom horizons (no default epochs).
    """
    context = get_context_preview()
    
    if "absolute_time_Epochs" in context:
        epochs = context["absolute_time_Epochs"]
        print(f"\nCronoFilter Context Summary:")
        print(f"Custom epochs: {len(epochs)}")
        
        if len(epochs) > 0:
            print("Custom epochs that will be exported:")
            for key, epoch in epochs.items():
                print(f"  - {epoch['name']} ({epoch['start']} to {epoch['end']})")
        else:
            print("No custom epochs defined - context will be empty")
    else:
        print("CronoFilter: No custom epochs found - context will be empty")

# Auto-initialization function
def initialize_integration():
    """
    Initialize the CronoFilter integration by applying the JSONExporter patch.
    """
    print("CronoFilter: Initializing direct integration...")
    
    if apply_json_exporter_patch():
        if validate_patch():
            print("CronoFilter: Integration successful - custom horizons will be included in exports")
            print_context_summary()
        else:
            print("CronoFilter: Integration validation failed")
    else:
        print("CronoFilter: Integration failed - patch could not be applied")

# Register with Blender's timer system for delayed initialization
def register_delayed_initialization():
    """
    Register the initialization to run after a short delay to ensure all modules are loaded.
    """
    def delayed_init():
        initialize_integration()
        return None  # Don't repeat
    
    # Use timer to delay initialization
    bpy.app.timers.register(delayed_init, first_interval=0.5)
    print("CronoFilter: Delayed initialization registered")